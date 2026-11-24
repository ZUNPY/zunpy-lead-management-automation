#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
SRC_DIR="$TMP_DIR/src"
ZIP_FILE="$TMP_DIR/zunpy-jobs-api-v0.5.zip"
mkdir -p "$SRC_DIR"

cat \
  deploy_parts/source.part-00 \
  deploy_parts/fix-01a \
  deploy_parts/fix-01b \
  deploy_parts/source.part-02 \
  deploy_parts/fix-03a \
  deploy_parts/fix-03b \
  deploy_parts/fix-04a \
  deploy_parts/fix-04b1 \
  deploy_parts/fix-04b2 \
  deploy_parts/source.part-05 \
  deploy_parts/source.part-06 \
  deploy_parts/source.part-07 \
  | tr -d '\n\r' \
  | base64 -d > "$ZIP_FILE"

python -m zipfile -e "$ZIP_FILE" "$SRC_DIR"

rm -rf app alembic scripts
cp -a "$SRC_DIR/app" ./app
cp -a "$SRC_DIR/alembic" ./alembic
cp -a "$SRC_DIR/scripts" ./scripts
cp "$SRC_DIR/alembic.ini" ./alembic.ini
cp "$SRC_DIR/requirements.txt" ./requirements.txt
cp render_internal.py ./app/api/routes/internal.py
cp render_processing.py ./app/services/processing.py
cp render_ocr.py ./app/services/ocr.py
cp render_results.py ./app/services/results.py
cp render_orders.py ./app/api/routes/orders.py
cp render_paypal.py ./app/api/routes/paypal.py
cp render_payments.py ./app/services/payments.py

python -m pip install -r requirements.txt
python -m pip install "rapidocr==3.10.0" "onnxruntime==1.32.0" "pypdfium2==5.15.2"
python -m compileall -q app
python - <<'PY'
from PIL import Image, ImageDraw, ImageFont
from app.services.ocr import _engine

image = Image.new("RGB", (640, 160), "white")
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()
draw.text((24, 50), "Supplier: ZUNPY TEST 123", fill="black", font=font)
result = _engine()(image, use_cls=False)
texts = list(getattr(result, "txts", []) or [])
if not texts:
    raise SystemExit("ocr_runtime_check_failed")
print("ocr_runtime_check_ok", texts[:3])
PY

python - <<'PY'
import fastapi
import sqlalchemy
import psycopg
import boto3
import pypdf
import pypdfium2
import rapidocr
import onnxruntime
import uvicorn

print("runtime_dependencies_ok")
print("sqlalchemy", sqlalchemy.__version__)
print("psycopg", psycopg.__version__)
print("rapidocr", rapidocr.__version__ if hasattr(rapidocr, "__version__") else "ok")
print("onnxruntime", onnxruntime.__version__)
PY
