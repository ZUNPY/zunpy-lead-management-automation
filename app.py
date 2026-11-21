import os
import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException

app = FastAPI(title="ZUNPY Jobs API Bootstrap", version="0.1.0")

def r2_client():
    endpoint = os.getenv("R2_ENDPOINT_URL", "")
    access = os.getenv("R2_ACCESS_KEY_ID", "")
    secret = os.getenv("R2_SECRET_ACCESS_KEY", "")
    if not all([endpoint, access, secret]):
        raise RuntimeError("R2 credentials are not configured")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )

@app.get("/health")
def health():
    return {"status": "ok", "service": "zunpy-jobs-api-bootstrap"}

@app.get("/storage-health")
def storage_health():
    bucket = os.getenv("R2_BUCKET_NAME", "")
    if not bucket:
        raise HTTPException(status_code=503, detail="R2 bucket is not configured")
    try:
        r2_client().list_objects_v2(Bucket=bucket, MaxKeys=1)
        return {"status": "ok", "storage": "reachable"}
    except Exception:
        raise HTTPException(status_code=503, detail="R2 storage is not reachable")
