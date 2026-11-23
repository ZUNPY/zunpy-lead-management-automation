#!/usr/bin/env bash
set -euo pipefail

# Render's internal Postgres URL is commonly postgresql://..., while this
# project intentionally uses psycopg v3.
if [[ "${DATABASE_URL:-}" == postgresql://* ]]; then
  export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgresql://}"
elif [[ "${DATABASE_URL:-}" == postgres://* ]]; then
  export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgres://}"
fi

# Ensure the installed Alembic package wins over the local ./alembic
# migration directory when importing from Python.
python -c "import site,sys; [sys.path.insert(0,p) for p in reversed(site.getsitepackages())]; from alembic.config import main; main(argv=['upgrade','head'])"

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
