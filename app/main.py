from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from google.cloud import storage
from pydantic import BaseModel
from typing import Any
import json
import datetime
# from app.discovery import PubMedCT
import app.discovery as discovery
import app.doc_process as doc_process
import os
from typing import List
from google.cloud import storage

from vertexai.language_models import TextEmbeddingModel
from google.cloud import aiplatform
from concurrent.futures import ThreadPoolExecutor
import math
import requests
import threading
import pandas as pd
import traceback
from psycopg2.extras import execute_values
import uuid
import google.auth
import google.auth.transport.requests
import requests
import app.gcs_operation as gcs_operation

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on Cloud Run!"}

@app.get("/echo/{text}")
def echo(text: str):
    return {"echo": text}

