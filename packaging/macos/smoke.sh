#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "usage: smoke.sh DSH-Forge.dmg" >&2
  exit 2
fi

dmg="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
mount_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/dsh-forge-mount.XXXXXX")"
state_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/dsh-forge-state.XXXXXX")"
port=39090
pid=""

cleanup() {
  if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi
  hdiutil detach "$mount_root" -force >/dev/null 2>&1 || true
  rmdir "$mount_root" 2>/dev/null || true
  rm -rf -- "$state_root"
}
trap cleanup EXIT

hdiutil attach -readonly -nobrowse -mountpoint "$mount_root" "$dmg" >/dev/null
executable="$mount_root/DSH Forge.app/Contents/MacOS/DSH Forge"
if [[ ! -x "$executable" ]]; then
  echo "The disk image does not contain an executable DSH Forge.app" >&2
  exit 1
fi

"$executable" --no-desktop --no-sync-catalog --port "$port" --state-dir "$state_root" &
pid="$!"
for _ in {1..30}; do
  if curl --fail --silent "http://127.0.0.1:$port/api/v1/status" > "$state_root/status.json"; then
    break
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "DSH Forge stopped before its loopback API became ready" >&2
    exit 1
  fi
  sleep 1
done

python3 - "$state_root/status.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    raise SystemExit("The packaged loopback API did not become ready")
status = json.loads(path.read_text(encoding="utf-8"))
application = status.get("application", {})
if application.get("platform") != "macos" or application.get("packaged") is not True:
    raise SystemExit("The packaged macOS runtime status is incorrect")
if status.get("mode") != "live-local-sidecar":
    raise SystemExit("The local sidecar did not report live mode")
PY

codesign --verify --deep --strict --verbose=2 "$mount_root/DSH Forge.app"
spctl --assess --type execute --verbose=2 "$mount_root/DSH Forge.app"
echo "The signed macOS application and loopback API passed the smoke test."
