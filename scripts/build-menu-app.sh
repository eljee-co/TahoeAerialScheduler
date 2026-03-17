#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_PATH="${1:-${REPO_ROOT}/dist/Tahoe Aerial Menu.app}"

if ! command -v osacompile >/dev/null 2>&1; then
  echo "Missing required command: osacompile" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUTPUT_PATH}")"
rm -rf "${OUTPUT_PATH}"
osacompile -l JavaScript -o "${OUTPUT_PATH}" "${REPO_ROOT}/src/TahoeAerialMenu.js"

cat <<EOF
Built menu app:
  ${OUTPUT_PATH}

Note:
  The built app expects the runtime files to be installed in:
  ${HOME}/Library/Application Support/TahoeAerialScheduler
EOF

