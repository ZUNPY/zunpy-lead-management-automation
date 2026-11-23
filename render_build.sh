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

python -m pip install -r requirements.txt

python - <<'PY'
import fastapi
import sqlalchemy
import psycopg
import boto3
import pypdf
import uvicorn

print("runtime_dependencies_ok")
print("sqlalchemy", sqlalchemy.__version__)
print("psycopg", psycopg.__version__)
PY
