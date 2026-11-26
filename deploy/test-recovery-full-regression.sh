#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/proyectos/zunpy-host"
COMMIT="d227e0aec076c3b3d36d4d84c2e84a90f0d2efcd"
WORK="$(mktemp -d)"
DB="zunpy-recovery-regression-$$"
RELAY="$PWD/recovery-relay/socket"
SECRET="$PWD/.recovery-webhook-sandbox-secret"
cleanup() {
    sudo docker rm -f "$DB" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT
git -C api-source cat-file -e "$COMMIT^{commit}"
git -C api-source archive "$COMMIT" \
    $(git -C api-source ls-tree --name-only "$COMMIT" | grep -E '^render_.*\.(py|sh)$') \
    tests_job005 | tar -x -C "$WORK"
sudo docker run -d --name "$DB" --network none \
    --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -e POSTGRES_USER=zunpy -e POSTGRES_DB=zunpy_recovery_test postgres:16 >/dev/null
for i in $(seq 1 60); do
    if sudo docker exec "$DB" pg_isready -h 127.0.0.1 -U zunpy -d zunpy_recovery_test >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
sudo docker exec "$DB" pg_isready -h 127.0.0.1 -U zunpy -d zunpy_recovery_test
sudo docker run --rm --network "container:$DB" \
    -e TEST_RECOVERY_DATABASE_URL="postgresql+psycopg://zunpy@127.0.0.1:5432/zunpy_recovery_test" \
    -e TEST_RECOVERY_SOCKET=/relay/recovery.sock \
    -v "$WORK:/candidate:ro" -v "$RELAY:/relay:ro" \
    -v "$SECRET:/run/zunpy-recovery-secret:ro" \
    --entrypoint python zunpy-jobs-api:125fe13 -B -c '
import unittest
suite = unittest.defaultTestLoader.discover("/candidate/tests_job005")
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
assert result.testsRun == 49, result.testsRun
assert not result.skipped, result.skipped
print("JOB-005.2.35 FULL_REGRESSION: PASS")
'
