# Tahoe Aerial Scheduler

Tahoe Aerial Scheduler keeps Apple's native Tahoe Aerial motion and changes the active Tahoe clip on a daily schedule.

This project is aimed at people who want:

- native Apple Tahoe Aerial wallpapers
- automatic time-based switching
- a lightweight menu bar control for changing time blocks and clips
- a setup flow that detects missing Tahoe downloads and points the user to Wallpaper settings

## Current Status

This is a GitHub-shareable source project for the working prototype we built locally. It is suitable for technical Mac users who are comfortable running an install script.

It is not yet a polished signed/notarized consumer app, and it relies on macOS's current internal wallpaper store format.

The maintainer docs in `docs/RELEASING.md` are intentionally kept in the repo so future releases stay repeatable instead of living only in chat history.

## Features

- Uses native Apple Tahoe Aerials, not still-image dynamic wallpapers
- Schedules different Tahoe clips at different times of day
- Keeps a simple menu bar companion for editing clip assignments and start times
- Preserves your existing `config.json` on reinstall
- Installs per-user without touching system-wide locations beyond your own login session

## Requirements

- macOS with the Tahoe Aerials available
- Python 3
- `osacompile` available on the Mac

If the Tahoe Aerials are not downloaded yet, the installer and menu app will detect that and prompt the user to open Wallpaper settings.

## Important Limitation

The wallpaper may briefly flash grey during clip changes.

That appears to be caused by macOS reloading `WallpaperAgent` when the native Aerial changes. With the current approach, the tradeoff is:

- true native Aerial behavior
- a brief transition flash

## License

This project is licensed under the MIT License. That means people can use, modify, and share it pretty freely, while keeping the standard no-warranty disclaimer in place.

## Install

### End-User Install

The intended release artifact for end users is a DMG containing a double-click installer app.

End-user flow:

- download the DMG from GitHub Releases
- open it
- double-click `Install Tahoe Aerial Scheduler.app`
- if Tahoe clips are missing, click `Open Wallpaper Settings` in the prompt and download them there

Because the app is not signed or notarized yet, macOS may warn the first time. If that happens, right-click the installer app and choose `Open`.

### Developer Install

From the repo root:

```bash
./scripts/install.sh
```

This installs the runtime files to:

- `~/Library/Application Support/TahoeAerialScheduler`
- `~/Applications/Tahoe Aerial Menu.app`
- `~/Library/LaunchAgents/com.eljee.tahoe-aerial-scheduler.plist`
- `~/Library/LaunchAgents/com.eljee.tahoe-aerial-menu.plist`

## Uninstall

Keep your config:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/uninstall.sh"
```

Remove everything:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/uninstall.sh" --purge
```

## Development Workflow

Edit:

- `src/scheduler.py`
- `src/TahoeAerialMenu.js`
- `resources/default-config.json`

Then reinstall over the current prototype:

```bash
./scripts/install.sh
```

If you just want to compile the menu app artifact:

```bash
./scripts/build-menu-app.sh
```

## Project Layout

- `src/scheduler.py`
  - core scheduler and wallpaper-store update logic
- `src/TahoeAerialMenu.js`
  - menu bar companion app
- `resources/default-config.json`
  - default Tahoe schedule and asset map
- `scripts/install.sh`
  - installs the runtime, menu app, and launch agents
- `scripts/uninstall.sh`
  - removes the app and launch agents
- `scripts/build-menu-app.sh`
  - builds the menu app into `dist/`
- `scripts/build-installer-app.sh`
  - builds the double-click installer app into `dist/`
- `scripts/package-release.sh`
  - creates the end-user DMG release artifact
- `docs/RELEASING.md`
  - GitHub release checklist

## Current Default Schedule

- `05:00` to `09:00` -> `Tahoe Morning`
- `09:00` to `17:00` -> `Tahoe Day`
- `17:00` to `20:00` -> `Tahoe Evening`
- `20:00` to `05:00` -> `Tahoe Night`

## Commands After Install

Show current status:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/run-scheduler.sh" status
```

Show schedule:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/run-scheduler.sh" show-schedule
```

Apply the current block immediately:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/run-scheduler.sh" apply
```

Change the clip assigned to a slot:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/run-scheduler.sh" set-slot 17:00 tahoe_evening
```

Change the start time of a slot:

```bash
"$HOME/Library/Application Support/TahoeAerialScheduler/run-scheduler.sh" set-start-time 17:00 18:30
```

## Release Path

The cleanest v1 release path is:

1. Keep this repo as the source of truth.
2. Test `./scripts/install.sh` on at least one clean user account or second Mac.
3. Push a version tag like `v0.1.0` to trigger the automated GitHub Release workflow.
4. Optionally add screenshots or a short demo GIF.

If you want to build the DMG locally before tagging, you can still run:

```bash
./scripts/package-release.sh v0.1.0
```

For the full checklist, see [docs/RELEASING.md](docs/RELEASING.md).

## Automated Releases

Pushing a tag that starts with `v` now triggers the release workflow in `.github/workflows/release.yml`.

Example:

```bash
git tag v0.1.1
git push origin v0.1.1
```

That workflow builds `TahoeAerialScheduler-v0.1.1.dmg`, creates a GitHub Release if needed, and attaches the DMG automatically.

## Contributing

If you want to improve the project, see [CONTRIBUTING.md](CONTRIBUTING.md).
