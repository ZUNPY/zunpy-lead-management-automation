#!/usr/bin/env bash
set -euo pipefail

cat \
  deploy_parts/source.part-00 \
  deploy_parts/source.part-01 \
  deploy_parts/source.part-02 \
  deploy_parts/source.part-03 \
  deploy_parts/source.part-05 \
  deploy_parts/source.part-06 \
  deploy_parts/source.part-07 \
  | tr -d '\n\r' \
  | base64 -d > /tmp/zunpy-jobs-api-v0.5.zip

python -m zipfile -e /tmp/zunpy-jobs-api-v0.5.zip .
pip install -r requirements.txt
