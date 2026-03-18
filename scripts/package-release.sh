#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

VERSION="${1:-}"

if [[ -z "${VERSION}" ]]; then
  echo "Usage: ./scripts/package-release.sh v0.1.0" >&2
  exit 1
fi

INSTALLER_APP_PATH="${REPO_ROOT}/dist/Install Tahoe Aerial Scheduler.app"
DMG_STAGING_DIR="${REPO_ROOT}/dist/.dmg-staging-${VERSION}"
DMG_PATH="${REPO_ROOT}/dist/TahoeAerialScheduler-${VERSION}.dmg"

rm -rf "${DMG_STAGING_DIR}" "${DMG_PATH}" "${INSTALLER_APP_PATH}"
mkdir -p "${REPO_ROOT}/dist"

"${REPO_ROOT}/scripts/build-installer-app.sh" "${INSTALLER_APP_PATH}"

mkdir -p "${DMG_STAGING_DIR}"
cp -R "${INSTALLER_APP_PATH}" "${DMG_STAGING_DIR}/"
install -m 644 "${REPO_ROOT}/resources/dmg-readme.txt" "${DMG_STAGING_DIR}/Read Me.txt"

hdiutil create \
  -volname "Tahoe Aerial Scheduler" \
  -srcfolder "${DMG_STAGING_DIR}" \
  -format UDZO \
  -ov \
  "${DMG_PATH}" >/dev/null

rm -rf "${DMG_STAGING_DIR}"

echo "Created end-user release artifact:"
echo "  ${DMG_PATH}"
