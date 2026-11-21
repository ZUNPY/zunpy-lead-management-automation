# ZUNPY Jobs API Bootstrap

Temporary deployment branch used only to validate the real Cloudflare R2 connection before deploying the full JOB-001 API.

Render settings:
- Build command: `bash build.sh`
- Start command: `bash start.sh`

Required environment variables:
- `R2_ENDPOINT_URL`
- `R2_BUCKET_NAME`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Endpoints:
- `/health`
- `/storage-health`

No payments, uploads, customer documents, or database writes are enabled in this bootstrap.
