# Releasing Tahoe Aerial Scheduler

This file is intentionally kept in the repo as a maintainer checklist for future GitHub releases.

## Before The First Public Release

- Add screenshots or a short screen recording
- Confirm the installer works on a second Mac or a clean user account
- Confirm the missing-download prompt appears only when the current scheduled Tahoe Aerial is not downloaded yet
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
- a missing-download prompt appears if the current scheduled Tahoe clip is not yet downloaded
- missing future Tahoe clips do not prompt until their schedule block is active
- `Open Wallpaper Settings` opens the Wallpaper settings page
- changing a slot from the menu updates the config
- changing a slot's start time works
- the scheduler applies the correct current clip
- scheduled clip changes preserve native Aerial lock-screen video behavior
- a brief grey flash during switching is still treated as a known limitation
- reinstalling preserves `config.json`
- the installed copy includes `~/Library/Application Support/TahoeAerialScheduler/uninstall.sh`

3. Build the installer app and DMG:

```bash
./scripts/package-release.sh v0.1.0
```

4. Push the release tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

5. Confirm GitHub Actions created the release and attached:

- `dist/TahoeAerialScheduler-v0.1.0.dmg`

6. In the GitHub release notes, tell users:

- this is a per-user installer
- the release artifact is a DMG with a double-click installer app
- if the current scheduled Tahoe Aerial is missing, the app will prompt the user to open Wallpaper settings and download it
- the installer is not signed/notarized yet, so macOS may require right-click `Open` the first time
- a brief grey flash during switching is a known limitation

## Manual Fallback

If the automated release workflow fails for any reason, you can still:

1. run `./scripts/package-release.sh v0.1.0`
2. create the GitHub Release manually
3. upload `dist/TahoeAerialScheduler-v0.1.0.dmg`

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
