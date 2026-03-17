# Tahoe Aerial Scheduler Chat Summary

## Current Project State

This folder is now the source-of-truth project for turning the Tahoe wallpaper prototype into release-ready software.

The working installed copy on this Mac currently lives in:

- `~/Library/Application Support/TahoeAerialScheduler`
- `~/Applications/Tahoe Aerial Menu.app`
- `~/Library/LaunchAgents/com.eljee.tahoe-aerial-scheduler.plist`
- `~/Library/LaunchAgents/com.eljee.tahoe-aerial-menu.plist`

## What The Prototype Does

- Keeps Apple's native Tahoe Aerial motion
- Switches between Tahoe clips on a time schedule
- Uses a menu bar helper to edit slot assignments and start times

The current Tahoe assets wired into the scheduler are:

- `Tahoe Morning`
- `Tahoe Day`
- `Tahoe Evening`
- `Tahoe Night`

## Current Technical Approach

The scheduler works by updating both of these wallpaper store files:

- `~/Library/Application Support/com.apple.wallpaper/Store/Index_v2.plist`
- `~/Library/Application Support/com.apple.wallpaper/Store/Index.plist`

Then it restarts `WallpaperAgent` so macOS applies the chosen native Aerial.

We discovered that changing only one plist caused the wallpaper to flicker grey and then revert. Updating both fixed the reversion bug.

## Menu Bar Decisions So Far

- icon-only menu bar item
- icon follows the current time period, not the assigned clip
- top-level items show only the time ranges
- submenu items keep full names like `Tahoe Morning`
- `Tahoe Night` is listed last in the submenu
- `Open Config` stays

## Known Limitation

There is still a brief grey flash during wallpaper switches.

Current best understanding:

- it is caused by macOS reloading the native wallpaper surface during the Aerial handoff
- keeping true native Aerial behavior likely means keeping that brief flash

## Repo Work Completed

This folder now contains:

- `src/scheduler.py`
- `src/TahoeAerialMenu.js`
- `resources/default-config.json`
- `scripts/install.sh`
- `scripts/uninstall.sh`
- `scripts/build-menu-app.sh`
- `scripts/package-release.sh`
- `README.md`
- `docs/RELEASING.md`

## Release Direction

The current release-ready v1 plan is:

1. Keep this repo as the source of truth.
2. Use `./scripts/install.sh` to install or update the runtime on a Mac.
3. Use `./scripts/package-release.sh v0.1.0` to build a GitHub release zip.
4. Add screenshots, choose a license, and publish.

## Most Recent Validation

The repo-backed installer has already been run successfully on this Mac.

Validated:

- shell scripts pass `bash -n`
- `src/scheduler.py` passes `python3 -m py_compile`
- `src/TahoeAerialMenu.js` compiles with `osacompile`
- install script successfully rebuilt the live installed version
- release archive created successfully in `dist/`

## Notes For The Next Session

- check whether the current live `17:00` slot should remain `Tahoe Morning` or be put back to `Tahoe Evening`
- decide on the final launch-agent label namespace before public release
- choose a license before publishing to GitHub
