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

cat > start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
python -c "from alembic.config import main; main(argv=['upgrade','head'])"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
EOF
