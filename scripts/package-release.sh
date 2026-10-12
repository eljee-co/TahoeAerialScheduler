#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

VERSION="${1:-}"

if [[ -z "${VERSION}" ]]; then
  echo "Usage: ./scripts/package-release.sh v0.1.0" >&2
  exit 1
fi
EXPECTED_VERSION="v$(tr -d '\n\r' < "${REPO_ROOT}/VERSION")"
if [[ "${VERSION}" != ci && "${VERSION}" != "${EXPECTED_VERSION}" ]]; then
  echo "Release tag must match VERSION (${EXPECTED_VERSION}), or be ci for a test build." >&2
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

(
  cd "${REPO_ROOT}/dist"
  shasum -a 256 "TahoeAerialScheduler-${VERSION}.dmg" > "TahoeAerialScheduler-${VERSION}.dmg.sha256"
)
"${TAHOE_BUILD_PYTHON:-python3}" - "${REPO_ROOT}" "${VERSION}" <<'PY'
import hashlib, json, plistlib, sys
from datetime import datetime, timezone
from pathlib import Path
root, tag = Path(sys.argv[1]), sys.argv[2]
dist = root / "dist"
dmg = dist / f"TahoeAerialScheduler-{tag}.dmg"
with (dist / "Install Tahoe Aerial Scheduler.app/Contents/Info.plist").open("rb") as handle:
    info = plistlib.load(handle)
receipt = {
    "version": info["CFBundleShortVersionString"], "tag": tag,
    "commit": info["TahoeAerialBuildCommit"],
    "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "artifact": dmg.name, "sha256": hashlib.sha256(dmg.read_bytes()).hexdigest(),
}
(dist / f"TahoeAerialScheduler-{tag}.build.json").write_text(json.dumps(receipt, indent=2) + "\n")
PY

echo "Created end-user release artifact:"
echo "  ${DMG_PATH}"
