#!/usr/bin/env bash
# Install a dedicated local SANDBOX relay. Never edit the existing API,
# n8n, proxy, compose configuration or production recovery settings.
set -euo pipefail
umask 077
ROOT="$HOME/proyectos/zunpy-host/recovery-relay"
NAME="zunpy-recovery-relay"
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
        listen unix:/relay/recovery.sock;
        client_max_body_size 4k;
        client_header_timeout 5s;
        client_body_timeout 5s;
        location = /webhook/zunpy-job005-recovery-sandbox {
            limit_except POST { deny all; }
            proxy_connect_timeout 3s;
            proxy_read_timeout 30s;
            proxy_pass_request_headers off;
            proxy_set_header Host 127.0.0.1:5678;
            proxy_set_header Content-Type $http_content_type;
            proxy_set_header X-ZUNPY-Recovery-Auth $http_x_zunpy_recovery_auth;
            proxy_pass http://127.0.0.1:5678/webhook/zunpy-job005-recovery-sandbox;
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
    -c 'rm -f /relay/recovery.sock; exec nginx -g "daemon off;"' >/dev/null
created=1
sudo docker start "$NAME" >/dev/null
for i in $(seq 1 20); do
    test -S "$ROOT/socket/recovery.sock" && break
    sleep 1
done
test -S "$ROOT/socket/recovery.sock"
test "$(stat -c '%a' "$ROOT/socket")" = 700
test "$(stat -c '%u' "$ROOT/socket")" = "$UID_HOST"
test "$(sudo docker inspect --format '{{.State.Running}}' "$NAME")" = true
echo "PERSISTENT_SANDBOX_RELAY: INSTALLED"
