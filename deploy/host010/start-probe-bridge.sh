#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$HOME/proyectos/zunpy-host"
TARGET="$PWD/host010-bridge"
COMMIT="dc077ce65329f53c5cefb613748a0142b8a9f61f"
if [[ -e "$TARGET" || -L "$TARGET" ]]; then
    echo "Bridge directory already exists; refusing to overwrite." >&2
    exit 1
fi
WORK="$(mktemp -d "$PWD/.host010-stage.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
git -C api-source archive "$COMMIT" deploy/host010/mission_bridge.py deploy/host010/probe_hermes_acp.py |
    tar -x -C "$WORK" --strip-components=2
openssl rand -hex 32 > "$WORK/bridge-secret"
chmod 600 "$WORK/bridge-secret"
python3 - "$WORK" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for name in ("mission_bridge.py","probe_hermes_acp.py"):
    p=root/name
    compile(p.read_bytes(),str(p),"exec")
PY
mv -T --no-clobber "$WORK" "$TARGET"
test ! -e "$WORK"
trap - EXIT
echo "HOST-010.3 BRIDGE_STAGED: PASS"
exec python3 "$TARGET/mission_bridge.py"
