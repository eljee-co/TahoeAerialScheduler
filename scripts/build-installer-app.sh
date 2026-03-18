#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_PATH="${1:-${REPO_ROOT}/dist/Install Tahoe Aerial Scheduler.app}"
BUILD_ROOT="${REPO_ROOT}/dist/.installer-build"
PAYLOAD_ROOT="${BUILD_ROOT}/payload"
INSTALLER_SCRIPT_PATH="${BUILD_ROOT}/install-from-bundle.sh"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

main() {
  require_command osacompile
  require_command rsync

  rm -rf "${BUILD_ROOT}" "${OUTPUT_PATH}"
  mkdir -p "${PAYLOAD_ROOT}" "$(dirname "${OUTPUT_PATH}")"

  mkdir -p "${PAYLOAD_ROOT}/src" "${PAYLOAD_ROOT}/resources" "${PAYLOAD_ROOT}/scripts"
  install -m 644 "${REPO_ROOT}/src/scheduler.py" "${PAYLOAD_ROOT}/src/scheduler.py"
  install -m 644 "${REPO_ROOT}/src/TahoeAerialMenu.js" "${PAYLOAD_ROOT}/src/TahoeAerialMenu.js"
  install -m 644 "${REPO_ROOT}/resources/default-config.json" "${PAYLOAD_ROOT}/resources/default-config.json"
  install -m 755 "${REPO_ROOT}/scripts/install.sh" "${PAYLOAD_ROOT}/scripts/install.sh"
  install -m 755 "${REPO_ROOT}/scripts/uninstall.sh" "${PAYLOAD_ROOT}/scripts/uninstall.sh"

  cat > "${INSTALLER_SCRIPT_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_ROOT="${SCRIPT_DIR}/payload"
exec "${PAYLOAD_ROOT}/scripts/install.sh"
EOF
  chmod 755 "${INSTALLER_SCRIPT_PATH}"

  osacompile -o "${OUTPUT_PATH}" "${REPO_ROOT}/src/TahoeAerialInstaller.applescript"
  mkdir -p "${OUTPUT_PATH}/Contents/Resources/payload"
  rsync -a "${PAYLOAD_ROOT}/" "${OUTPUT_PATH}/Contents/Resources/payload/"
  install -m 755 "${INSTALLER_SCRIPT_PATH}" "${OUTPUT_PATH}/Contents/Resources/install-from-bundle.sh"
  rm -rf "${BUILD_ROOT}"

  cat <<EOF
Built installer app:
  ${OUTPUT_PATH}
EOF
}

main "$@"
