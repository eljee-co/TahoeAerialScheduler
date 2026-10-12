#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

verification_started="$(date +%s)"
release_tag="${1:-ci}"
export TAHOE_BUILD_PYTHON="${TAHOE_BUILD_PYTHON:-python3}"

for script in scripts/*.sh; do
  bash -n "${script}"
done
"${TAHOE_BUILD_PYTHON}" -m py_compile src/scheduler.py scripts/stamp-app.py
"${TAHOE_BUILD_PYTHON}" -m unittest discover -s tests
node --test tests/test_menu.js
node --check src/TahoeAerialMenu.js
./scripts/build-menu-app.sh
./scripts/package-release.sh "${release_tag}"
codesign --verify --strict "dist/Tahoe Aerial Menu.app"
codesign --verify --strict "dist/Install Tahoe Aerial Scheduler.app"
hdiutil verify "dist/TahoeAerialScheduler-${release_tag}.dmg" >/dev/null
"${TAHOE_BUILD_PYTHON}" - "${REPO_ROOT}" "${release_tag}" "${verification_started}" <<'PY'
import json, plistlib, subprocess, sys, time
from pathlib import Path
root, tag = Path(sys.argv[1]), sys.argv[2]
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
version = (root / "VERSION").read_text().strip()
installer = root / "dist/Install Tahoe Aerial Scheduler.app"
for app in (installer, root / "dist/Tahoe Aerial Menu.app"):
    with (app / "Contents/Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    assert info["CFBundleShortVersionString"] == version
    assert info["TahoeAerialBuildCommit"] == commit
payload = installer / "Contents/Resources/payload"
for name in ("scheduler.py", "TahoeAerialMenu.js"):
    assert (payload / "src" / name).read_bytes() == (root / "src" / name).read_bytes()
assert (payload / "VERSION").read_text().strip() == version
assert (payload / "BUILD_COMMIT").read_text().strip() == commit
report = {"commit": commit, "version": version, "tag": tag, "result": "passed",
          "duration_seconds": round(time.time() - int(sys.argv[3]), 2),
          "checks": ["shell and Python syntax", "scheduler regression tests", "menu behavior tests",
                     "menu and installer compilation and signatures", "DMG integrity", "packaged source and version identity"]}
(root / "dist/verification.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"Verification passed for {commit[:12]} ({version}) in {report['duration_seconds']} seconds.")
PY
