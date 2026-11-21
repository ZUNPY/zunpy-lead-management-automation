#!/usr/bin/env bash
set -euo pipefail
python -m zipfile -e zunpy-jobs-api-source.zip .
pip install -r requirements.txt
