

import json
import datetime
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
def process_drugs(request: DrugRequest):
    """
    Process a list of drugs sent in the request payload.
    """
    process_id ="process-" + str(uuid.uuid5(uuid.NAMESPACE_DNS, str(datetime.now())))
    # For demo, just echo back the drugs with a flag
    patient_pool = db_ops.get_dummy_patients_pool()
    matched_drugs = [drug for drug in request.drug_list if drug.lower() in ["paracetamol", "ibuprofen", "acetaminophen"]]
    
    return {
        "drug_flag": len(matched_drugs) > 0,
        "drug_list": matched_drugs
    }
