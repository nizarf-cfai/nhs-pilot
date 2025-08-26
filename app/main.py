

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
    return db_ops.get_dummy_patients_pool()