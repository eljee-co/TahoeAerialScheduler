#!/usr/bin/env bash
set -euo pipefail

APP_SUPPORT_DIR="${HOME}/Library/Application Support/TahoeAerialScheduler"
APPLICATIONS_DIR="${HOME}/Applications"
MENU_APP_PATH="${APPLICATIONS_DIR}/Tahoe Aerial Menu.app"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
SCHEDULER_LABEL="com.eljee.tahoe-aerial-scheduler"
MENU_LABEL="com.eljee.tahoe-aerial-menu"
SCHEDULER_PLIST="${LAUNCH_AGENTS_DIR}/${SCHEDULER_LABEL}.plist"
MENU_PLIST="${LAUNCH_AGENTS_DIR}/${MENU_LABEL}.plist"

KEEP_CONFIG=1

if [[ "${1:-}" == "--purge" ]]; then
  KEEP_CONFIG=0
fi

bootout_if_loaded() {
  local label="$1"
  local plist_path="$2"
  launchctl bootout "gui/$(id -u)" "${plist_path}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
}

main() {
  local backup_config=""

  if [[ "${KEEP_CONFIG}" -eq 1 && -f "${APP_SUPPORT_DIR}/config.json" ]]; then
    backup_config="$(mktemp)"
    cp "${APP_SUPPORT_DIR}/config.json" "${backup_config}"
  fi

  bootout_if_loaded "${SCHEDULER_LABEL}" "${SCHEDULER_PLIST}"
  bootout_if_loaded "${MENU_LABEL}" "${MENU_PLIST}"

  rm -f "${SCHEDULER_PLIST}" "${MENU_PLIST}"
  rm -rf "${MENU_APP_PATH}"
  rm -rf "${APP_SUPPORT_DIR}"

  if [[ -n "${backup_config}" && -f "${backup_config}" ]]; then
    mkdir -p "${APP_SUPPORT_DIR}"
    mv "${backup_config}" "${APP_SUPPORT_DIR}/config.json"
  fi

  if [[ "${KEEP_CONFIG}" -eq 1 ]]; then
    echo "Tahoe Aerial Scheduler removed. config.json was preserved."
  else
    echo "Tahoe Aerial Scheduler fully removed."
  fi
}

main "$@"

