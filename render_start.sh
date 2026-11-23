#!/usr/bin/env bash
set -euo pipefail

if [[ "${DATABASE_URL:-}" == postgresql://* ]]; then
  export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgresql://}"
elif [[ "${DATABASE_URL:-}" == postgres://* ]]; then
  export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgres://}"
fi

python render_bootstrap_db.py
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
