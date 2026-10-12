# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.4] - 2026-10-12

- Restore the active desktop when macOS falls back to a default or image wallpaper, including display and Space overrides
- Recover a stuck Aerial player even when the saved clip already matches the schedule
- Stop the old player before reloading the wallpaper agent and verify playback after changes
- Distinguish verified playback, mismatches, unavailable inspection, and missing downloads; retry failed recovery with a cooldown
- Show the playing clip separately from the scheduled clip, with a restore action and diagnostics log in the menu
- Write settings and state atomically, serialize edits and recovery, and correctly convert Apple's UTC timestamps
- Keep timestamped diagnostics and a bounded recent log history; avoid minute-by-minute state rewrites and routine log spam
- Reinstall with the wall-clock minute schedule while preserving existing clip assignments and start times
- Stage and version the menu app before replacing the installed copy
- Run the same regression, compilation, and packaging checks locally and on GitHub
- Publish new versions automatically after a VERSION bump reaches main and passes verification, with release notes, checksums, source identity, and immutable published assets

## [0.1.3] - 2026-05-27

- Avoid repeated visible wallpaper reloads when the current Tahoe slot is already active but macOS wallpaper metadata is stale
- Prompt for missing Tahoe downloads only when the current scheduled clip is missing
- Check the schedule on wall-clock minute boundaries so wallpaper changes happen at the configured minute instead of up to one minute after the LaunchAgent was loaded

## [0.1.2] - 2026-04-26

- Refresh the active wallpaper slot when the macOS wallpaper store timestamp is stale
- Convert the legacy linked wallpaper store entry from shuffle/default mode to the selected Tahoe Aerial asset
- Check the live Aerial player process so stale Day video playback is detected during the Morning slot
- Add scheduler regression tests for the morning slot boundary

## [0.1.0] - 2026-03-18

- Added the repo source tree for the Tahoe scheduler and menu app
- Added installer, uninstaller, build, and release packaging scripts
- Added default Tahoe schedule config
- Added maintainer release docs and public repo metadata
