import os
from io import BytesIO

import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pypdf import PdfReader, PdfWriter

app = FastAPI(title="ZUNPY Jobs API Bootstrap", version="0.2.0")

BUCKET_ENV = "R2_BUCKET_NAME"
UPLOAD_KEY = "uploads/e2e/bootstrap-test.pdf"
SOURCE_KEY = "source/e2e/bootstrap-test.pdf"
MARKER_KEY = "results/e2e-bootstrap-completed.txt"


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


def bucket_name():
    bucket = os.getenv(BUCKET_ENV, "")
    if not bucket:
        raise RuntimeError("R2 bucket is not configured")
    return bucket


def make_pdf():
    out = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(out)
    return out.getvalue()


def already_completed(client, bucket):
    result = client.list_objects_v2(Bucket=bucket, Prefix=MARKER_KEY, MaxKeys=1)
    return any(obj.get("Key") == MARKER_KEY for obj in result.get("Contents", []))


@app.get("/health")
def health():
    return {"status": "ok", "service": "zunpy-jobs-api-bootstrap", "version": "0.2.0"}


@app.get("/storage-health")
def storage_health():
    try:
        client = r2_client()
        client.list_objects_v2(Bucket=bucket_name(), MaxKeys=1)
        return {"status": "ok", "storage": "reachable"}
    except Exception:
        raise HTTPException(status_code=503, detail="R2 storage is not reachable")


@app.get("/storage-e2e/pdf")
def storage_e2e_pdf():
    return Response(content=make_pdf(), media_type="application/pdf")


@app.get("/storage-e2e/presign")
def storage_e2e_presign():
    try:
        client = r2_client()
        bucket = bucket_name()

        if already_completed(client, bucket):
            return {"status": "already_completed"}

        cors = {
            "CORSRules": [
                {
                    "AllowedOrigins": [
                        "https://zunpyai.com",
                        "https://www.zunpyai.com",
                        "https://zunpy-jobs-api.onrender.com",
                    ],
                    "AllowedMethods": ["PUT", "GET", "HEAD"],
                    "AllowedHeaders": ["Content-Type"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        }

        cors_status = "configured"
        try:
            client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors)
        except Exception:
            cors_status = "could_not_configure"

        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": UPLOAD_KEY,
                "ContentType": "application/pdf",
            },
            ExpiresIn=300,
        )
        return {
            "status": "ready",
            "cors": cors_status,
            "upload_url": url,
        }
    except Exception:
        raise HTTPException(status_code=503, detail="Could not prepare R2 E2E test")


@app.get("/storage-e2e/verify")
def storage_e2e_verify():
    client = r2_client()
    bucket = bucket_name()

    if already_completed(client, bucket):
        return {"status": "ok", "result": "already_completed"}

    stages = []
    try:
        head = client.head_object(Bucket=bucket, Key=UPLOAD_KEY)
        if head.get("ContentType") != "application/pdf":
            raise RuntimeError("unexpected content type")
        if int(head.get("ContentLength", 0)) <= 0:
            raise RuntimeError("empty upload")
        stages.append("upload_present")

        uploaded = client.get_object(Bucket=bucket, Key=UPLOAD_KEY)["Body"].read()
        reader = PdfReader(BytesIO(uploaded))
        if len(reader.pages) < 1:
            raise RuntimeError("invalid PDF")
        stages.append("pdf_valid")

        client.copy_object(
            Bucket=bucket,
            Key=SOURCE_KEY,
            CopySource={"Bucket": bucket, "Key": UPLOAD_KEY},
            ContentType="application/pdf",
            MetadataDirective="REPLACE",
        )
        stages.append("copied_to_source")

        source = client.get_object(Bucket=bucket, Key=SOURCE_KEY)["Body"].read()
        source_reader = PdfReader(BytesIO(source))
        if len(source_reader.pages) != len(reader.pages):
            raise RuntimeError("source verification failed")
        stages.append("source_verified")

        client.delete_object(Bucket=bucket, Key=UPLOAD_KEY)
        client.delete_object(Bucket=bucket, Key=SOURCE_KEY)
        stages.append("test_objects_deleted")

        client.put_object(
            Bucket=bucket,
            Key=MARKER_KEY,
            Body=b"JOB-001 R2 E2E bootstrap completed successfully\n",
            ContentType="text/plain",
        )
        stages.append("completion_marker_written")

        return {
            "status": "ok",
            "result": "r2_e2e_verified",
            "stages": stages,
            "marker": MARKER_KEY,
        }
    except Exception:
        for key in (UPLOAD_KEY, SOURCE_KEY):
            try:
                client.delete_object(Bucket=bucket, Key=key)
            except Exception:
                pass
        raise HTTPException(
            status_code=503,
            detail={"result": "r2_e2e_failed", "completed_stages": stages},
        )


@app.get("/storage-e2e", response_class=HTMLResponse)
def storage_e2e_page():
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZUNPY R2 E2E</title>
<style>
body{font-family:system-ui,sans-serif;max-width:760px;margin:48px auto;padding:0 20px;background:#0b0f14;color:#eef6ff}
.card{border:1px solid #28445a;border-radius:16px;padding:24px;background:#111923}
h1{margin-top:0} pre{white-space:pre-wrap;background:#071018;padding:16px;border-radius:12px}
.ok{color:#59e391}.bad{color:#ff7b7b}
</style>
</head>
<body>
<div class="card">
<h1>ZUNPY JOB-001 · R2 E2E</h1>
<p>Testing browser → presigned R2 upload → PDF validation → secure copy → verification → cleanup.</p>
<pre id="out">Starting…</pre>
</div>
<script>
const out = document.getElementById('out');
function show(v, ok=true){out.textContent = typeof v === 'string' ? v : JSON.stringify(v,null,2); out.className = ok ? 'ok' : 'bad';}
(async()=>{
  try{
    const p = await fetch('/storage-e2e/presign').then(r=>r.json());
    if(p.status === 'already_completed'){show({status:'ok',result:'already_completed'}); return;}
    if(!p.upload_url) throw new Error('No presigned upload URL returned');

    const pdf = await fetch('/storage-e2e/pdf').then(r=>r.blob());
    const put = await fetch(p.upload_url, {
      method:'PUT',
      headers:{'Content-Type':'application/pdf'},
      body:pdf
    });
    if(!put.ok) throw new Error('R2 PUT failed: HTTP '+put.status);

    const verifyResp = await fetch('/storage-e2e/verify');
    const verify = await verifyResp.json();
    if(!verifyResp.ok) throw new Error(JSON.stringify(verify));
    show({cors:p.cors,...verify});
  }catch(e){
    show({status:'failed',error:String(e)}, false);
  }
})();
</script>
</body>
</html>"""
