import os
from google.cloud import storage
import json
from google.cloud.sql.connector import Connector
import pg8000  # PostgreSQL driver
import traceback
import app.config as config

connector = Connector()

def get_pg_connection():
    return connector.connect(
        config.DB_CONNECTION_NAME,
        "pg8000",
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME
    )
    

def write_status(file_name :str, value :dict):
    write_or_update_json_to_gcs(config.BUCKET, f"status/{file_name}", value)

def write_text_to_gcs(blob_name: str, text_content: str):
    bucket_name = config.BUCKET
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        blob.upload_from_string(text_content, content_type="text/plain")
        
        print(f"✅ Successfully wrote text to gs://{bucket_name}/{blob_name}")
    
    except Exception as e:
        print(f"❌ Error writing text to GCS: {e}")
        
def write_json_to_gcs(blob_name: str, json_data: dict | list):
    bucket_name = config.BUCKET
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Serialize the dictionary to a JSON formatted string
        # Using `indent=2` makes the JSON file human-readable
        json_string = json.dumps(json_data, indent=2)

        blob.upload_from_string(json_string, content_type="application/json")
        
        print(f"✅ Successfully wrote JSON to gs://{bucket_name}/{blob_name}")

    except Exception as e:
        print(f"❌ Error writing JSON to GCS: {e}")
        err = traceback.print_exc()
        return str(err)
        
def read_text_from_gcs(blob_name: str) -> str:
    bucket_name = config.BUCKET
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Download the blob's content as a string
        text_content = blob.download_as_text()
        
        print(f"✅ Successfully read text from gs://{bucket_name}/{blob_name}")
        return text_content
    
    except Exception as e:
        print(f"❌ Error reading text from GCS: {e}")
        return ""
    
def read_json_from_gcs(blob_name: str) -> dict | list:
    bucket_name = config.BUCKET
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Download the blob's content as a string
        json_string = blob.download_as_text()
        
        # Deserialize the JSON string into a Python object
        json_data = json.loads(json_string)
        
        print(f"✅ Successfully read JSON from gs://{bucket_name}/{blob_name}")
        return json_data
    
    except Exception as e:
        print(f"❌ Error reading JSON from GCS: {e}")
        return None
    
    
def write_or_update_json_to_gcs(blob_name: str, update_data: dict):
    bucket_name = config.BUCKET
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Try to download existing JSON content
        if blob.exists():
            current_data = json.loads(blob.download_as_string())
        else:
            current_data = {}

        # Update non-empty values only
        for key, value in update_data.items():
            if value != "":
                current_data[key] = value

        # Upload updated JSON
        blob.upload_from_string(
            json.dumps(current_data, indent=2),
            content_type="application/json"
        )

    except Exception as e:
        return str(e)