#!/usr/bin/env bash
# Disposable acceptance only. Never use the active PostgreSQL service.
set -euo pipefail
umask 077
cd "$HOME/proyectos/zunpy-host"
sudo -v
COMMIT="${1:?Pass the approved full candidate commit}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]
BASE="zunpy-jobs-api:125fe13"
sudo docker image inspect "$BASE" >/dev/null
git -C api-source fetch origin refs/heads/job005-order-recovery
test "$(git -C api-source rev-parse FETCH_HEAD)" = "$COMMIT"
WORK="$(mktemp -d)"
DB="zunpy-boot-test-db-$$"
API="zunpy-boot-test-api-$$"
IMAGE="zunpy-recovery-boot-test:${COMMIT:0:12}-$$"
cleanup() {
    sudo docker rm -fv "$API" "$DB" >/dev/null 2>&1 || true
    sudo docker image rm "$IMAGE" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT
mapfile -t FILES < <(git -C api-source ls-tree --name-only "$COMMIT" | grep -E '^render_.*\.(py|sh)$')
test "${#FILES[@]}" -gt 0
git -C api-source archive "$COMMIT" "${FILES[@]}" | tar -x -C "$WORK"
cat > "$WORK/Dockerfile" <<'EOF'
FROM zunpy-jobs-api:125fe13
WORKDIR /app
COPY render_*.py render_*.sh /app/
RUN cp render_internal.py app/api/routes/internal.py && \
    cp render_processing.py app/services/processing.py && \
    cp render_ocr.py app/services/ocr.py && \
    cp render_results.py app/services/results.py && \
    cp render_orders.py app/api/routes/orders.py && \
    cp render_paypal.py app/api/routes/paypal.py && \
    cp render_payments.py app/services/payments.py && \
    cp render_main.py app/main.py && \
    python -m compileall -q app && \
    bash -n render_start.sh
EOF
sudo docker build --network none --pull=false -t "$IMAGE" "$WORK"
echo "CANDIDATE_IMAGE_BUILD: PASS"
sudo docker run -d --name "$DB" --network none --pull never \
    --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=zunpy \
    -e POSTGRES_DB=zunpy_recovery_test postgres:16 >/dev/null
for i in $(seq 1 30); do
    if sudo docker exec "$DB" pg_isready -h 127.0.0.1 -U zunpy -d zunpy_recovery_test >/dev/null; then break; fi
    sleep 1
done
sudo docker exec "$DB" pg_isready -h 127.0.0.1 -U zunpy -d zunpy_recovery_test >/dev/null
URL="postgresql+psycopg://zunpy@127.0.0.1:5432/zunpy_recovery_test"
COMMON=(--network "container:$DB" -e "DATABASE_URL=$URL" -e PORT=10000)
sudo docker run --rm "${COMMON[@]}" --entrypoint python "$BASE" render_bootstrap_db.py
# Before explicit migration, candidate must fail startup, not silently migrate.
sudo docker run -d --name "$API" "${COMMON[@]}" --entrypoint bash "$IMAGE" render_start.sh >/dev/null
for i in $(seq 1 30); do
    test "$(sudo docker inspect --format '{{.State.Running}}' "$API")" = false && break
    sleep 1
done
test "$(sudo docker inspect --format '{{.State.Running}}' "$API")" = false
test "$(sudo docker inspect --format '{{.State.ExitCode}}' "$API")" != 0
sudo docker logs "$API" 2>&1 | grep -F 'Recovery schema missing; run explicit migration first.' >/dev/null
sudo docker rm "$API" >/dev/null
echo "MISSING_SCHEMA_STARTUP_REJECTED: PASS"
sudo docker run --rm "${COMMON[@]}" --entrypoint python "$IMAGE" render_migrate_recovery.py
sudo docker run --rm "${COMMON[@]}" --entrypoint python "$IMAGE" render_migrate_recovery.py
sudo docker run --rm "${COMMON[@]}" --entrypoint python "$IMAGE" render_migrate_recovery.py --check
echo "ADDITIVE_MIGRATION: PASS"
check_boot() {
    local image="$1" mode="$2"
    sudo docker run -d --name "$API" "${COMMON[@]}" --entrypoint bash "$image" render_start.sh >/dev/null
    for i in $(seq 1 60); do
        if sudo docker exec "$API" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:10000/openapi.json",timeout=2).close()' >/dev/null 2>&1; then break; fi
        if test "$(sudo docker inspect --format '{{.State.Running}}' "$API")" = false; then
            sudo docker logs "$API" >&2
            return 1
        fi
        sleep 1
    done
    sudo docker exec -i "$API" python - "$mode" <<'PY'
import json, sys, urllib.request, urllib.error
base = "http://127.0.0.1:10000"
with urllib.request.urlopen(base + "/openapi.json", timeout=5) as r:
    paths = json.load(r)["paths"]
assert "/v1/payments/paypal/order" in paths
if sys.argv[1] == "candidate":
    assert "/v1/recovery/request" in paths and "/v1/recovery/redeem" in paths
    for action, body in [
        ("request", {"order_id":"ZJ-RECOVERY-TEST","email":"buyer@example.com"}),
        ("redeem", {"order_id":"ZJ-RECOVERY-TEST","recovery_token":"x"*43}),
    ]:
        req = urllib.request.Request(base+"/v1/recovery/"+action,
            data=json.dumps(body).encode(), headers={"Content-Type":"application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=5).close()
        except urllib.error.HTTPError as exc:
            assert exc.code == 503 and exc.headers["Cache-Control"] == "no-store"
        else:
            raise AssertionError("Recovery unexpectedly enabled")
else:
    assert "/v1/recovery/request" not in paths
PY
    sudo docker rm -f "$API" >/dev/null
}
check_boot "$IMAGE" candidate
echo "CANDIDATE_BOOT_FAIL_CLOSED: PASS"
check_boot "$BASE" previous
echo "PREVIOUS_IMAGE_BOOT_COMPATIBILITY: PASS"
echo "JOB-005.2.21 CANDIDATE_STARTUP: PASS"
