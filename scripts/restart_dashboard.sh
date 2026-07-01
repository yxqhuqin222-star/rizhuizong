#!/bin/zsh
set -euo pipefail

service="gui/$(id -u)/com.kityhello.rizhuizong-dashboard"
python_bin="/Users/kityhello/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
health_url="http://127.0.0.1:8766/api/health"
response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

old_pid="$(launchctl print "$service" 2>/dev/null | awk '$1 == "pid" {print $3; exit}')"
launchctl kickstart -k "$service"

for attempt in {1..20}; do
  if /usr/bin/curl --silent --show-error --max-time 2 "$health_url" >"$response_file" 2>/dev/null; then
    if "$python_bin" - "$response_file" "$old_pid" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    payload = json.load(response)

old_pid = sys.argv[2]
required = {"health", "reload-demo", "reload-target"}
capabilities = set(payload.get("capabilities", []))
if payload.get("ok") is not True or not required.issubset(capabilities):
    raise SystemExit(1)
if old_pid and str(payload.get("pid")) == old_pid:
    raise SystemExit(1)
print(
    f"dashboard ready: pid={payload['pid']} "
    f"started_at={payload['started_at']}"
)
PY
    then
      exit 0
    fi
  fi
  sleep 0.5
done

echo "dashboard restart failed: health check did not pass" >&2
exit 1
