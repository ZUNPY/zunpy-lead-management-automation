#!/usr/bin/env bash
set -euo pipefail

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
  | base64 -d > /tmp/zunpy-jobs-api-v0.5.zip

python -m zipfile -e /tmp/zunpy-jobs-api-v0.5.zip .
python -m pip install -r requirements.txt
python -m pip install "alembic>=1.13,<2"

ALEMBIC_BIN="$(dirname "$(command -v python)")/alembic"
test -x "$ALEMBIC_BIN"
"$ALEMBIC_BIN" --version
