#!/usr/bin/env bash
# Install a separate private recovery MAIL relay while its workflow is unpublished.
# Do not edit existing API, n8n, sandbox relay, proxy or compose services.
set -euo pipefail
umask 077
ROOT="$HOME/proyectos/zunpy-host/recovery-mail-relay"
NAME="zunpy-recovery-mail-relay"
IMAGE="$(sudo docker image inspect --format '{{.Id}}' nginx:stable-alpine)"
UID_HOST="$(id -u)"
GID_HOST="$(id -g)"
test "$UID_HOST" != 0
test ! -e "$ROOT"
if sudo docker container inspect "$NAME" >/dev/null 2>&1; then
    echo "Relay already exists; refusing to replace it." >&2
    exit 1
fi

mkdir -m 700 "$ROOT"
created=0
cleanup() {
    rc=$?
    if [ "$rc" -ne 0 ]; then
        if [ "$created" = 1 ]; then
            sudo docker rm -f "$NAME" >/dev/null 2>&1 || true
        fi
        rm -rf -- "$ROOT"
    fi
}
trap cleanup EXIT
mkdir -m 700 "$ROOT/socket"
openssl rand -hex 32 > "$ROOT/header-secret"
chmod 600 "$ROOT/header-secret"
test "$(wc -c < "$ROOT/header-secret")" = 65
cat > "$ROOT/nginx.conf" <<'EOF'
worker_processes 1;
pid /tmp/nginx.pid;
error_log /dev/null crit;
events { worker_connections 32; }
http {
    access_log off;
    client_body_temp_path /tmp/client_body;
    proxy_temp_path /tmp/proxy;
    fastcgi_temp_path /tmp/fastcgi;
    uwsgi_temp_path /tmp/uwsgi;
    scgi_temp_path /tmp/scgi;
    server {
        listen unix:/relay/mail.sock;
        client_max_body_size 4k;
        client_header_timeout 5s;
        client_body_timeout 5s;
        location = /webhook/zunpy-job005-recovery-mail {
            limit_except POST { deny all; }
            proxy_connect_timeout 3s;
            proxy_read_timeout 30s;
            proxy_pass_request_headers off;
            proxy_set_header Host 127.0.0.1:5678;
            proxy_set_header Content-Type $http_content_type;
            proxy_set_header X-ZUNPY-Recovery-Auth $http_x_zunpy_recovery_auth;
            proxy_pass http://127.0.0.1:5678/webhook/zunpy-job005-recovery-mail;
        }
        location / { return 404; }
    }
}
EOF
# The socket directory is private even when nginx creates a mode-0666 socket.
# Only explicitly mounted clients with the owning UID (or privileged root)
# can enter it. No TCP listeners are configured.
sudo docker create --name "$NAME" --network host \
    --restart unless-stopped --user "$UID_HOST:$GID_HOST" \
    --cap-drop ALL --security-opt no-new-privileges:true \
    --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,mode=1777,size=16m \
    --pids-limit 64 --memory 128m \
    --mount "type=bind,src=$ROOT/socket,dst=/relay" \
    --mount "type=bind,src=$ROOT/nginx.conf,dst=/etc/nginx/nginx.conf,readonly" \
    --entrypoint /bin/sh "$IMAGE" \
    -c 'rm -f /relay/mail.sock; exec nginx -g "daemon off;"' >/dev/null
created=1
sudo docker start "$NAME" >/dev/null
for i in $(seq 1 20); do
    test -S "$ROOT/socket/mail.sock" && break
    sleep 1
done
test -S "$ROOT/socket/mail.sock"
test "$(stat -c '%a' "$ROOT/socket")" = 700
test "$(stat -c '%u' "$ROOT/socket")" = "$UID_HOST"
test "$(sudo docker inspect --format '{{.State.Running}}' "$NAME")" = true
test "$(stat -c '%a' "$ROOT/header-secret")" = 600
# Verify actual socket reachability with no credentials and no recipient.
# Expected 404 because the mail workflow is not published. A 403 is also
# fail-closed but indicates the webhook may have been published: stop.
python3 - "$ROOT/socket/mail.sock" <<'PY'
import http.client, socket, sys
class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect(sys.argv[1])
def check(method, path, expected):
    conn = UnixHTTP("localhost", timeout=5)
    try:
        conn.request(method, path, body=b"{}", headers={"Content-Type":"application/json"})
        with conn.getresponse() as response:
            if response.status != expected:
                raise SystemExit(f"Unexpected HTTP status: {response.status}, expected {expected}")
    finally:
        conn.close()
check("POST", "/webhook/zunpy-job005-recovery-sandbox", 404)
check("GET", "/webhook/zunpy-job005-recovery-mail", 403)
check("POST", "/webhook/zunpy-job005-recovery-mail", 404)
print("MAIL_RELAY_ISOLATION: PASS")
PY
echo "DEDICATED_MAIL_SECRET: CREATED (0600; not displayed)"
echo "JOB-005.2.28 MAIL_RELAY_INSTALLED: PASS"
