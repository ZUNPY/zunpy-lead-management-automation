#!/usr/bin/env bash
set -euo pipefail

ALEMBIC_BIN="$(dirname "$(command -v python)")/alembic"
"$ALEMBIC_BIN" upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
