# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
