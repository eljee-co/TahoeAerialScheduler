# Releasing Tahoe Aerial Scheduler

This file is intentionally kept in the repo as a maintainer checklist for future GitHub releases.

## Before The First Public Release

- Add screenshots or a short screen recording
- Confirm the installer works on a second Mac or a clean user account
- Confirm the missing-download prompt behaves correctly when Tahoe Aerials are not downloaded yet
- Decide whether you want to keep the current `com.eljee...` launch-agent labels or rename them before publishing

## Current License

The project is now licensed under MIT.

## Release Checklist

1. Update the source in `src/` and test with:

```bash
./scripts/install.sh
```

2. Verify:

- the menu bar item appears
- a missing-download prompt appears if Tahoe clips are not yet downloaded
- `Open Wallpaper Settings` opens the Wallpaper settings page
- changing a slot from the menu updates the config
- changing a slot's start time works
- the scheduler applies the correct current clip
- reinstalling preserves `config.json`
- the installed copy includes `~/Library/Application Support/TahoeAerialScheduler/uninstall.sh`

3. Build the installer app and DMG:

```bash
./scripts/package-release.sh v0.1.0
```

4. Create a GitHub release and upload:

- `dist/TahoeAerialScheduler-v0.1.0.dmg`

5. In the GitHub release notes, tell users:

- this is a per-user installer
- the release artifact is a DMG with a double-click installer app
- if Tahoe Aerials are missing, the app will prompt the user to open Wallpaper settings and download them
- the installer is not signed/notarized yet, so macOS may require right-click `Open` the first time
- a brief grey flash during switching is a known limitation

## Suggested README Additions Before Publishing

- one screenshot of the menu bar item
- one screenshot of the submenu
- a short explanation of the grey flash limitation
- a note on the macOS version you tested against

## Future Improvements

- replace the JXA menu app with a native SwiftUI menu bar app
- add a friendlier settings window
- add signed and notarized release artifacts
- add an icon for the app bundle itself
