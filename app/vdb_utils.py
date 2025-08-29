import os
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document
from google.cloud import storage
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import json
import app.config as config
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

# === CONFIG ===
BUCKET = config.BUCKET
VECTOR_DB_NAME = "vector_app_db"
GCS_PATH = f"vector_store/{VECTOR_DB_NAME}"
VDB_PATH = f"./vector_db/{VECTOR_DB_NAME}/chroma"
COLLECTION = "cloud_vdb"
import tempfile
# === SINGLETON STATE ===
_embeddings = None
_vector_store = None

# === GCS: DOWNLOAD VECTOR STORE ===
def download_from_gcs():
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET)
        blobs = list(bucket.list_blobs(prefix=f"{GCS_PATH}/"))

        if not blobs:
            print(f"📭 No vector DB found in GCS path: {GCS_PATH}")
            return False

        os.makedirs(VDB_PATH, exist_ok=True)

        for blob in blobs:
            rel_path = blob.name[len(f"{GCS_PATH}/"):]
            if not rel_path:  # skip prefix directory itself
                continue
            dest_path = os.path.join(VDB_PATH, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            print(f"📥 Downloading {blob.name} → {dest_path}")
            blob.download_to_filename(dest_path)

        return True
    except Exception as e:
        print(f"[download_from_gcs] Error: {e}")
        return False

# === GCS: PUSH VECTOR STORE ===
def push_to_gcs():
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET)

        for root, _, files in os.walk(VDB_PATH):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, VDB_PATH)
                blob = bucket.blob(f"{GCS_PATH}/{rel_path}")
                blob.upload_from_filename(full_path)
                print(f"📤 Uploaded {rel_path} to GCS")
    except Exception as e:
        print(f"[push_to_gcs] Error: {e}")

# === EMBEDDING INIT (Singleton) ===
# def get_embeddings():
#     global _embeddings
#     if _embeddings is None:
#         _embeddings = OpenAIEmbeddings(
#             model="text-embedding-3-large",
#         )
#     return _embeddings


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
        )
    return _embeddings
# === VECTOR STORE INIT (Singleton) ===
def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = Chroma(
            collection_name=COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=VDB_PATH
        )
    return _vector_store

# === RETRIEVER (with optional GCS download trigger) ===
def get_retriever():
    download_from_gcs()
    return get_vector_store().as_retriever()

# === ADD DOCUMENT TO VECTOR DB ===
def add_to_vectorstore(doc_id: str, text: str = None, gcs_path: str = None):
    if text is None and gcs_path:
        client = storage.Client()
        bucket = client.bucket(BUCKET)
        blob = bucket.blob(gcs_path)

        _, ext = os.path.splitext(gcs_path)
        ext = ext.lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            blob.download_to_filename(tmp.name)
            tmp_path = tmp.name

        if ext == ".pdf":
            loader = PyPDFLoader(tmp_path)
        elif ext == ".txt":
            loader = TextLoader(tmp_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        docs = loader.load()
        text = "\n\n".join([doc.page_content for doc in docs])

    if not text:
        raise ValueError("No text found for embedding")

    doc = Document(
        page_content=text,
        metadata={"source": gcs_path or "manual", "doc_id": doc_id}
    )

    vector_store = get_vector_store()

    # 🧼 Optional: delete old version if exists
    try:
        vector_store.delete(ids=[doc_id])
    except Exception as e:
        print(f"⚠️ Warning: could not delete old doc_id {doc_id}: {e}")

    vector_store.add_documents([doc], ids=[doc_id])  # ✅ assign known ID
    vector_store.persist()
    print(f"✅ Added doc: {doc_id}")
    
# === CREATE EMPTY VECTOR STORE LOCALLY ===
def create_empty_vectorstore():
    os.makedirs(VDB_PATH, exist_ok=True)
    Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=VDB_PATH
    ).persist()
    print("📦 Created empty vector store locally")

def add_json_to_vectorstore(doc_id: str, json_obj: dict = None, gcs_path: str = None):
    if json_obj is None and gcs_path:
        # Load JSON from GCS
        client = storage.Client()
        bucket = client.bucket(BUCKET)
        blob = bucket.blob(gcs_path)

        _, ext = os.path.splitext(gcs_path)
        ext = ext.lower()

        if ext != ".json":
            raise ValueError(f"Unsupported file type for JSON loader: {ext}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            blob.download_to_filename(tmp.name)
            tmp_path = tmp.name

        with open(tmp_path, "r", encoding="utf-8") as f:
            json_obj = json.load(f)

    if not json_obj:
        raise ValueError("No JSON content found for embedding")

    # Convert JSON to readable text
    text = json.dumps(json_obj, indent=2, ensure_ascii=False)

    doc = Document(
        page_content=text,
        metadata={"source": gcs_path or "manual", "doc_id": doc_id}
    )

    vector_store = get_vector_store()
    vector_store.add_documents([doc], ids=[doc_id])  # assuming vector DB supports ids
    vector_store.persist()
    print(f"✅ Added JSON doc: {doc_id}")
