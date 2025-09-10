

import json
from datetime import datetime
import traceback
import os
import math
import pandas as pd
import uuid
import requests

from typing import List, Dict, Any
from pydantic import BaseModel
import asyncio
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from google.cloud import storage
import google.auth
import google.auth.transport.requests
import threading
import app.gcs_operation as gcs_operation
import app.db_ops as db_ops
from app.vdb_utils import (
    get_retriever,
    push_to_gcs,
    add_to_vectorstore,
    download_from_gcs,
    create_empty_vectorstore,
    add_json_to_vectorstore
)


app = FastAPI()
# Lazy init — global retriever and lock
retriever = None
retriever_lock = threading.Lock()

class AddDocRequest(BaseModel):
    doc_id: str
    gcs_path: str = None
    text_content: str = None  # optional if using gcs_path
    json_obj: dict = None  # optional if using gcs_path

class QueryRequest(BaseModel):
    q: str

class JobRun(BaseModel):
    args: List[str]  # e.g., "CTgov"
    

class DrugRequest(BaseModel):
    drug_list: List[str]

class PatientRequest(BaseModel):
    process_id: str
    patient_id: str

class ProcessRequest(BaseModel):
    process_id: str

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on Cloud Run!"}

@app.get("/echo/{text}")
def echo(text: str):
    return {"echo": text}

@app.on_event("startup")
async def startup_load_vector_db():
    """Trigger vector DB loading in background on Cloud Run boot."""

    async def _background_load():
        global retriever
        with retriever_lock:
            try:
                print("🔄 Loading vector DB on startup...")
                if not download_from_gcs():
                    print("📭 No vector DB found in GCS. Creating new one.")
                    create_empty_vectorstore()
                retriever = get_retriever()
                print("✅ Vector DB loaded on startup.")
            except Exception as e:
                print(f"❌ Startup vector DB load failed: {e}")

    asyncio.create_task(_background_load())



@app.get("/load_vector_db/")
def load_vector_db():
    """
    Manually triggers loading the vector DB from GCS.
    If not found, creates a new empty one.
    """
    global retriever
    with retriever_lock:
        try:
            print("🔄 Loading vector DB from GCS...")
            if not download_from_gcs():
                print("📭 No existing vector DB found in GCS. Creating empty vector DB...")
                create_empty_vectorstore()
            retriever = get_retriever()
            print("✅ Vector DB loaded and retriever is ready.")
            return {"status": "loaded"}
        except Exception as e:
            print(f"❌ Error loading vector DB: {e}")
            return {"status": "error", "message": str(e)}

def ensure_vectorstore_loaded():
    global retriever
    with retriever_lock:
        if retriever is None:
            raise RuntimeError("Vector DB not loaded. Please call /load_vector_db/ first.")

@app.post("/query")
def query_vector(payload: QueryRequest):
    ensure_vectorstore_loaded()
    docs = retriever.invoke(payload.q)
    
    result = []
    for doc in docs:
        res_str = ""
        res_str += f"Source : {doc.metadata.get('source')}\n"
        res_str += f"Content : {doc.page_content}\n\n"
        result.append(res_str)
    
    return result

@app.post("/add-doc/")
def add_document(payload: AddDocRequest):
    ensure_vectorstore_loaded()
    add_to_vectorstore(payload.doc_id,payload.text_content , payload.gcs_path)
    push_to_gcs()
    return {"status": "added", "id": payload.doc_id}


@app.post("/add-json/")
def add_document(payload: AddDocRequest):
    try:
        ensure_vectorstore_loaded()
        add_json_to_vectorstore(
            doc_id = payload.doc_id,
            json_obj = payload.json_obj , 
            gcs_path = payload.gcs_path
            )
        push_to_gcs()
        return {"status": "added", "id": payload.doc_id}
    except:
        err = traceback.print_exc()
        return {"status": str(err), "id": payload.doc_id}
    


@app.get("/dummy_patients", response_model=List[Dict])
def get_dummy_patients():
    """
    Fetch all dummy patients from the database.
    """
    results = []
    try:
        # return db_ops.get_dummy_patients_pool()
        patient_list = gcs_operation.list_gcs_children('gs://nhs_pilot/dummy_patients2')

        for p in patient_list:
            print("Patient item :",p)
            rec = {
                    "patient_id" : p.split('/')[-1],
                    "patient_bucket_path" : p
                }
            patient_profile = gcs_operation.read_json_from_gcs(f"{p}/patient_profile.json")
            if patient_profile:
                rec['name'] = patient_profile.get('name','')
                rec['sex'] = patient_profile.get('sex','')
                rec['birth_date'] = patient_profile.get('birth_date','')
                rec['age_years'] = patient_profile.get('age_years','')
                rec['phone'] = patient_profile.get('phone','')
                rec['email'] = patient_profile.get('email','')
                rec['city'] = patient_profile.get('city','')
                rec['state_province'] = patient_profile.get('state_province','')
                rec['country'] = patient_profile.get('country','')

            results.append(rec)
        return results

    except Exception as e:
        error = traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/process")
def process_drugs(payload: DrugRequest):
    """
    Process a list of drugs sent in the request payload.
    """
    process_id ="process-" + str(uuid.uuid5(uuid.NAMESPACE_DNS, str(datetime.now())))
    # For demo, just echo back the drugs with a flag
    patient_pool = db_ops.get_dummy_patients_pool()
    drug_watch = {
        "drug_list" : payload.drug_list
    }
    
    for p in patient_pool:
        p['process_id'] = process_id
        p['drug_watch'] = payload.drug_list

    gcs_operation.write_json_to_gcs(f"process/{process_id}/patient_pool.json", patient_pool)
    gcs_operation.write_json_to_gcs(f"process/{process_id}/drug_watch.json", drug_watch)

    trigger_cloud_run_job(
            project_id = "medforce-pilot-backend",
            region='europe-west1',
            job_name = 'job-runner',
            args=["run_process", f"process_id={process_id}"]
            # args = payload.args
        )
    
    return {
        "process_id": process_id,
        "drug_list": drug_watch
    }

@app.post("/get_patient")
def process_drugs(payload: PatientRequest):
    """
    Process a list of drugs sent in the request payload.
    """
    process_id = payload.process_id
    patient_id = payload.patient_id

    data = gcs_operation.read_json_from_gcs(f"process/{process_id}/patients/{patient_id}/{patient_id}.json")
    return data

@app.post("/get_process_patients")
def process_drugs(payload: ProcessRequest):
    """
    Process a list of drugs sent in the request payload.
    """
    process_id = payload.process_id

    data = gcs_operation.read_json_from_gcs(f"process/{process_id}/patient_pool.json")
    return data


def trigger_cloud_run_job(
    project_id: str,
    region: str,
    job_name: str,
    args: list[str] = None,
):
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    url = (
        f"https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/"
        f"namespaces/{project_id}/jobs/{job_name}:run"
    )

    payload = {}
    if args:
        payload = {
            "overrides": {
                "containerOverrides": [
                    {
                        "args": args  # MUST be a list like ["clinical", "drug_name=Ivacaftor"]
                    }
                ]
            }
        }

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()


@app.post("/run-job/")
def process_job(payload : JobRun):
    try:
        trigger_cloud_run_job(
            project_id = "genevest-backend",
            region='europe-west1',
            job_name = 'genevest-job-run',
            # args=["discovery", "source=GUNCR", "keyword=neurology"]
            args = payload.args
        )
        return {
            "status":"success"
        }
    except:
        err = traceback.print_exc()
        return {
            "status":str(err)
        }
    



