

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

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from google.cloud import storage
import google.auth
import google.auth.transport.requests

import app.gcs_operation as gcs_operation
import app.db_ops as db_ops

app = FastAPI()

class JobRun(BaseModel):
    args: List[str]  # e.g., "CTgov"
    

class DrugRequest(BaseModel):
    drug_list: List[str]


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on Cloud Run!"}

@app.get("/echo/{text}")
def echo(text: str):
    return {"echo": text}



@app.get("/dummy_patients", response_model=List[Dict])
def get_dummy_patients():
    """
    Fetch all dummy patients from the database.
    """
    try:
        return db_ops.get_dummy_patients_pool()
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
    



