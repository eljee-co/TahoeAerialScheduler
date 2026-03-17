#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

APP_SUPPORT_DIR="${HOME}/Library/Application Support/TahoeAerialScheduler"
APPLICATIONS_DIR="${HOME}/Applications"
MENU_APP_PATH="${APPLICATIONS_DIR}/Tahoe Aerial Menu.app"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
SCHEDULER_LABEL="com.eljee.tahoe-aerial-scheduler"
MENU_LABEL="com.eljee.tahoe-aerial-menu"
SCHEDULER_PLIST="${LAUNCH_AGENTS_DIR}/${SCHEDULER_LABEL}.plist"
MENU_PLIST="${LAUNCH_AGENTS_DIR}/${MENU_LABEL}.plist"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

detect_python() {
  if [[ -x /Library/Frameworks/Python.framework/Versions/Current/bin/python3 ]]; then
    printf '%s\n' /Library/Frameworks/Python.framework/Versions/Current/bin/python3
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  echo "Could not find python3. Install Python 3 and try again." >&2
  exit 1
}

bootout_if_loaded() {
  local label="$1"
  local plist_path="$2"
  launchctl bootout "gui/$(id -u)" "${plist_path}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
}

write_scheduler_runner() {
  local python_path="$1"

  cat > "${APP_SUPPORT_DIR}/run-scheduler.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export TAHOE_AERIAL_APP_DIR="${APP_SUPPORT_DIR}"
exec "${python_path}" "${APP_SUPPORT_DIR}/scheduler.py" "\$@"
EOF
  chmod 755 "${APP_SUPPORT_DIR}/run-scheduler.sh"
}

write_scheduler_plist() {
  cat > "${SCHEDULER_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${SCHEDULER_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${APP_SUPPORT_DIR}/run-scheduler.sh</string>
    <string>apply</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>WatchPaths</key>
  <array>
    <string>${APP_SUPPORT_DIR}/config.json</string>
  </array>
  <key>StandardOutPath</key>
  <string>${APP_SUPPORT_DIR}/scheduler.log</string>
  <key>StandardErrorPath</key>
  <string>${APP_SUPPORT_DIR}/scheduler.log</string>
</dict>
</plist>
EOF
}

write_menu_plist() {
  cat > "${MENU_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${MENU_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>${MENU_APP_PATH}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${APP_SUPPORT_DIR}/menu-launch.log</string>
  <key>StandardErrorPath</key>
  <string>${APP_SUPPORT_DIR}/menu-launch.log</string>
</dict>
</plist>
EOF
}

main() {
  require_command osacompile
  require_command launchctl

  local python_path
  python_path="$(detect_python)"

  mkdir -p "${APP_SUPPORT_DIR}" "${APPLICATIONS_DIR}" "${LAUNCH_AGENTS_DIR}"

  install -m 755 "${REPO_ROOT}/src/scheduler.py" "${APP_SUPPORT_DIR}/scheduler.py"
  install -m 644 "${REPO_ROOT}/src/TahoeAerialMenu.js" "${APP_SUPPORT_DIR}/TahoeAerialMenu.js"

  if [[ ! -f "${APP_SUPPORT_DIR}/config.json" ]]; then
    install -m 644 "${REPO_ROOT}/resources/default-config.json" "${APP_SUPPORT_DIR}/config.json"
  fi

  write_scheduler_runner "${python_path}"

  rm -rf "${MENU_APP_PATH}"
  osacompile -l JavaScript -o "${MENU_APP_PATH}" "${APP_SUPPORT_DIR}/TahoeAerialMenu.js"

  write_scheduler_plist
  write_menu_plist

  bootout_if_loaded "${SCHEDULER_LABEL}" "${SCHEDULER_PLIST}"
  bootout_if_loaded "${MENU_LABEL}" "${MENU_PLIST}"

  launchctl bootstrap "gui/$(id -u)" "${SCHEDULER_PLIST}"
  launchctl bootstrap "gui/$(id -u)" "${MENU_PLIST}"
  launchctl kickstart -k "gui/$(id -u)/${SCHEDULER_LABEL}" >/dev/null 2>&1 || true

  "${APP_SUPPORT_DIR}/run-scheduler.sh" apply >/dev/null 2>&1 || true
  open -n "${MENU_APP_PATH}" >/dev/null 2>&1 || true

  cat <<EOF
Installed Tahoe Aerial Scheduler.

App support:
  ${APP_SUPPORT_DIR}

Menu app:
  ${MENU_APP_PATH}

Launch agents:
  ${SCHEDULER_PLIST}
  ${MENU_PLIST}

Config:
  ${APP_SUPPORT_DIR}/config.json
EOF
}

main "$@"

