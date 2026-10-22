#!/usr/bin/env bash
# Install the pinned Linux x64 experiment binary, without replacing injected OpenCode.
set -euo pipefail
for tool in curl python3 oc; do
  command -v "$tool" >/dev/null || { echo "Missing $tool; use the workshop Dev Space." >&2; exit 1; }
done
[[ "$(uname -s)/$(uname -m)" == Linux/x86_64 ]] || {
  echo 'This experiment installer targets the existing Linux x64 Dev Space.' >&2
  exit 1
}
[[ -n "${OPENAI_BASE_URL:-}" && -n "${OPENAI_API_KEY:-}" ]] || {
  echo 'Open the workshop Dev Space with its injected MaaS configuration first.' >&2
  exit 1
}
oc whoami >/dev/null
target="$HOME/.local/share/rosa-companion/opencode2"
if [[ -x "$target" && "$("$target" --version)" == 'opencode v2.1.2' ]]; then
  echo 'OpenCode 2.1.2 is already installed for this experiment.'
  exit 0
fi
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT
curl -fsSL --max-time 180 \
  https://registry.npmjs.org/@opencode/cli-linux-x64/-/cli-linux-x64-2.1.2.tgz \
  -o "$archive"
python3 - "$archive" "$target" <<'PY'
import base64, hashlib, pathlib, sys, tarfile
source, target = map(pathlib.Path, sys.argv[1:])
expected = 'O8/8JT8SNmMReDmpYDsm04KmkrQQ2dzaKgaw06zCoUfh50ARGHs58E6zCh16GIUyEL8abrdSe268K5/ExE89Gw=='
if base64.b64encode(hashlib.sha512(source.read_bytes()).digest()).decode() != expected:
    raise SystemExit('OpenCode package integrity check failed.')
target.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(source) as archive:
    binary = archive.extractfile('package/bin/opencode').read()
temporary = target.with_suffix('.tmp')
temporary.write_bytes(binary)
temporary.chmod(0o755)
temporary.replace(target)
print('Installed verified OpenCode 2.1.2 for the companion experiment.')
PY
