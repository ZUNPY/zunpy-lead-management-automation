#!/usr/bin/env bash
set -euo pipefail

python -c "from alembic.config import main; main(argv=['upgrade','head'])"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
