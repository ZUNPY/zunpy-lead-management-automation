#!/usr/bin/env bash
# Real-browser acceptance with disposable PostgreSQL and a synthetic order.
# The only host-published port is loopback. No payment or mail routes exposed.
set -euo pipefail
umask 077
cd "$HOME/proyectos/zunpy-host"
sudo -v
BACKEND="${1:?backend commit required}"
WEB="4f160a6c63d07b35b15e21a08c3928addee828e1"
[[ "$BACKEND" =~ ^[0-9a-f]{40}$ ]]
git -C api-source fetch origin refs/heads/job005-order-recovery
test "$(git -C api-source rev-parse FETCH_HEAD)" = "$BACKEND"
git -C api-source fetch origin refs/heads/website-job005-recovery
test "$(git -C api-source rev-parse FETCH_HEAD)" = "$WEB"

WORK="$(mktemp -d)"
DB="zunpy-browser-db-$$"
API="zunpy-browser-api-$$"
NET="zunpy-browser-net-$$"
cleanup() {
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "BROWSER_ACCEPTANCE: FAILED (exit $rc)" >&2
        sudo docker logs --tail 60 "$API" >&2 || true
    fi
    sudo docker rm -fv "$API" "$DB" >/dev/null 2>&1 || true
    sudo docker network rm "$NET" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT
mkdir "$WORK/code" "$WORK/web" "$WORK/exchange"
git -C api-source archive "$BACKEND" render_bootstrap_db.py \
    render_migrate_recovery.py render_recovery.py render_recovery_limits.py \
    render_recovery_routes.py render_public_recovery.py render_sensitive_http.py \
    render_orders.py | tar -x -C "$WORK/code"
git -C api-source archive "$WEB" jobs.html jobs.js | tar -x -C "$WORK/web"
python3 - "$WORK/web/jobs.js" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = 'const API = "https://zunpy-jobs-api.onrender.com/v1";'
assert s.count(old) == 1
p.write_text(s.replace(old, 'const API = location.origin + "/v1";'))
PY
cat > "$WORK/code/browser_acceptance.py" <<'PY'
import os
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Order, OrderStatus
from app.schemas.order import OrderStatusResponse
from app.security.tokens import hash_token, utcnow
from render_orders import order_status
from render_public_recovery import router, PublicRecoveryConfig, get_public_recovery_config

ORDER = "ZJ-RECOVERY-TEST"
EMAIL = "buyer@example.com"
OLD = "fictional-original-access"
EXCHANGE = Path("/exchange")
engine = create_engine(get_settings().database_url)
with Session(engine) as db, db.begin():
    now = utcnow()
    for oid in (ORDER, "ZJ-PREFLIGHT-TEST"):
        db.add(Order(order_id=oid, customer_email=EMAIL,
        status=OrderStatus.WAITING_UPLOAD, payment_provider="paypal",
        payment_reference="PAYPAL:"+oid, amount_cents=2900,
        currency="EUR", max_documents=1, access_token_hash=hash_token(OLD),
        access_expires_at=now+timedelta(days=1),
        upload_expires_at=now+timedelta(hours=1)))

def capture_delivery(delivery):
    assert delivery.order_id in (ORDER, "ZJ-PREFLIGHT-TEST") and delivery.recipient == EMAIL
    link = "http://127.0.0.1:18765/jobs.html#" + urlencode({
        "order": delivery.order_id, "recovery": delivery.raw_token})
    p = EXCHANGE / ("link" if delivery.order_id == ORDER else "preflight-link")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(link + "\n")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
config = PublicRecoveryConfig(secrets.token_bytes(32), capture_delivery)
app.dependency_overrides[get_public_recovery_config] = lambda: config
def sandbox_db():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = sandbox_db
app.include_router(router, prefix="/v1")
app.get("/v1/orders/{order_id}/status", response_model=OrderStatusResponse)(order_status)

@app.get("/jobs.html")
def page():
    return FileResponse("/web/jobs.html", headers={"Cache-Control":"no-store"})

@app.get("/jobs.js")
def js():
    return FileResponse("/web/jobs.js", media_type="application/javascript",
                        headers={"Cache-Control":"no-store"})

@app.middleware("http")
async def observe(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/v1/"):
        print("SANDBOX_HTTP", request.method, response.status_code, flush=True)
    if request.url.path == f"/v1/orders/{ORDER}/status" and response.status_code == 200:
        (EXCHANGE / "browser_status_ok").touch(mode=0o600)
    return response
PY

BASE="zunpy-jobs-api:125fe13"
sudo docker network create "$NET" >/dev/null
sudo docker run -d --name "$DB" --network "$NET" --pull never \
    -p 127.0.0.1:18765:10000 --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=zunpy \
    -e POSTGRES_DB=zunpy_recovery_test postgres:16 >/dev/null
for i in $(seq 1 30); do
    if sudo docker exec "$DB" pg_isready -h 127.0.0.1 -U zunpy -d zunpy_recovery_test >/dev/null; then break; fi
    sleep 1
done
sudo docker exec "$DB" pg_isready -h 127.0.0.1 -U zunpy -d zunpy_recovery_test >/dev/null
COMMON=(--network "container:$DB" --pull never
    -e DATABASE_URL=postgresql+psycopg://zunpy@127.0.0.1:5432/zunpy_recovery_test
    -e PYTHONPATH=/candidate:/app -v "$WORK/code:/candidate:ro")
sudo docker run --rm "${COMMON[@]}" --entrypoint python "$BASE" -m render_bootstrap_db
sudo docker run --rm "${COMMON[@]}" --entrypoint python "$BASE" -m render_migrate_recovery
sudo docker run -d --name "$API" "${COMMON[@]}" \
    -v "$WORK/web:/web:ro" -v "$WORK/exchange:/exchange" \
    --entrypoint python "$BASE" -m uvicorn browser_acceptance:app \
    --host 0.0.0.0 --port 10000 --no-proxy-headers --no-access-log >/dev/null
for i in $(seq 1 30); do
    if curl -fsS --max-time 2 http://127.0.0.1:18765/jobs.html >/dev/null; then break; fi
    sleep 1
done
curl -fsS --max-time 5 http://127.0.0.1:18765/jobs.html >/dev/null
# Verify the real HTTP service and delivery callback before asking the
# operator to interact. Use a distinct synthetic order to preserve quotas.
HTTP="$(curl -sS --max-time 15 -o /dev/null -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d '{"order_id":"ZJ-PREFLIGHT-TEST","email":"buyer@example.com"}' \
    http://127.0.0.1:18765/v1/recovery/request)"
echo "PREFLIGHT_HTTP: $HTTP"
test "$HTTP" = 202
for i in $(seq 1 10); do sudo test -s "$WORK/exchange/preflight-link" && break; sleep 1; done
sudo test -s "$WORK/exchange/preflight-link" || { echo "PREFLIGHT_DELIVERY: FAIL" >&2; exit 1; }
echo "PREFLIGHT_DELIVERY: PASS"
echo "BROWSER_SANDBOX_READY: PASS"
echo "Open http://127.0.0.1:18765/jobs.html in your browser."
echo "Request recovery: ZJ-RECOVERY-TEST / buyer@example.com"
read -r -p "After requesting recovery, press Enter here: " _
for i in $(seq 1 10); do sudo test -s "$WORK/exchange/link" && break; sleep 1; done
if ! sudo test -s "$WORK/exchange/link"; then
    echo "BROWSER_REQUEST: FAIL — no link generated; HTTP evidence follows." >&2
    exit 1
fi
echo "RECOVERY_LINK_GENERATED: PASS"
sudo cat "$WORK/exchange/link"
echo "Open the link in a new browser tab. Confirm Restore access."
read -r -p "After the recovered order and PDF upload appear, press Enter here: " _
sudo docker exec -i "$API" python - <<'PY'
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import urllib.request, urllib.error
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models import Order
from app.security.tokens import verify_token
from render_recovery import recovery_tokens

assert Path("/exchange/browser_status_ok").exists(), "No successful browser order status"
link = Path("/exchange/link").read_text().strip()
token = parse_qs(urlsplit(link).fragment)["recovery"][0]
engine = create_engine(get_settings().database_url)
with Session(engine) as db:
    order = db.get(Order, "ZJ-RECOVERY-TEST")
    row = db.execute(select(recovery_tokens).where(
        recovery_tokens.c.order_id == order.order_id)).mappings().one()
    assert row["consumed_at"] is not None, "Token not redeemed"
    assert not verify_token("fictional-original-access", order.access_token_hash)
print("BROWSER_REDEEM_AND_ORDER_STATUS: PASS")
req = urllib.request.Request("http://127.0.0.1:10000/v1/recovery/redeem",
    data=json.dumps({"order_id":"ZJ-RECOVERY-TEST","recovery_token":token}).encode(),
    headers={"Content-Type":"application/json"}, method="POST")
try:
    urllib.request.urlopen(req, timeout=5).close()
except urllib.error.HTTPError as e:
    assert e.code == 400
else:
    raise AssertionError("Replay accepted")
print("BROWSER_LINK_REPLAY_REJECTED: PASS")
PY
echo "JOB-005.2.24 REAL_BROWSER_RECOVERY: PASS"
