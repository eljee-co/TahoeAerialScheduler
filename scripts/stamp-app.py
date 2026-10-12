#!/usr/bin/env python3
"""Give compiled AppleScript apps the same version and source identity."""

import plistlib
import re
import subprocess
import sys
from pathlib import Path


def build_commit(root: Path) -> str:
    receipt = root / "BUILD_COMMIT"
    if receipt.exists():
        return receipt.read_text().strip()
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    app_path, kind = sys.argv[1:]
    root = Path(__file__).resolve().parent.parent
    version = (root / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("VERSION must contain a stable major.minor.patch version.")
    path = Path(app_path) / "Contents" / "Info.plist"
    with path.open("rb") as handle:
        info = plistlib.load(handle)
    info.update(CFBundleShortVersionString=version, CFBundleVersion=version,
                CFBundleIdentifier=f"com.eljee.tahoe-aerial-{kind}",
                TahoeAerialBuildCommit=build_commit(root))
    if kind == "menu":
        info["LSUIElement"] = True
    with path.open("wb") as handle:
        plistlib.dump(info, handle)


if __name__ == "__main__":
    main()
