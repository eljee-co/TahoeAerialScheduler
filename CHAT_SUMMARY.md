# Tahoe Aerial Scheduler Chat Summary

## What We Built

We built a native macOS Tahoe Aerial scheduler that keeps Apple's Tahoe Aerial motion and switches clips on a time schedule.

The current prototype has two main parts:

- `scheduler.py`
  - Python script that updates macOS's wallpaper store plists so the active wallpaper stays a native Apple Aerial.
- `TahoeAerialMenu.js`
  - A small menu bar app written in JXA that lets you change schedule slots and start times without editing JSON by hand.

## Why It Works This Way

The main requirement was to keep the real native Aerial behavior, including the moving wallpaper and screen saver feel, instead of switching to still-image dynamic wallpapers.

Because macOS does not provide a built-in "use this Aerial at this time of day" scheduler, the solution works by:

1. Updating the native wallpaper store files:
   - `~/Library/Application Support/com.apple.wallpaper/Store/Index_v2.plist`
   - `~/Library/Application Support/com.apple.wallpaper/Store/Index.plist`
2. Restarting `WallpaperAgent` so macOS applies the new Aerial.

We discovered that updating only `Index_v2.plist` was not enough. That caused a grey flicker and a snap-back to the previous scene. Updating both stores fixed the reversion bug.

## Current Installed Paths

The working installed version currently lives here:

- Scheduler source:
  - `~/Library/Application Support/TahoeAerialScheduler/scheduler.py`
- Menu source:
  - `~/Library/Application Support/TahoeAerialScheduler/TahoeAerialMenu.js`
- Config:
  - `~/Library/Application Support/TahoeAerialScheduler/config.json`
- State:
  - `~/Library/Application Support/TahoeAerialScheduler/state.json`
- Logs:
  - `~/Library/Application Support/TahoeAerialScheduler/scheduler.log`
  - `~/Library/Application Support/TahoeAerialScheduler/menu-ui.log`
  - `~/Library/Application Support/TahoeAerialScheduler/menu-launch.log`
- Compiled menu app:
  - `~/Applications/Tahoe Aerial Menu.app`
- Launch agents:
  - `~/Library/LaunchAgents/com.eljee.tahoe-aerial-scheduler.plist`
  - `~/Library/LaunchAgents/com.eljee.tahoe-aerial-menu.plist`

## Tahoe Assets In Use

The prototype is wired to these native Tahoe Aerial assets:

- `Tahoe Night`
- `Tahoe Morning`
- `Tahoe Day`
- `Tahoe Evening`

Asset IDs currently used by the scheduler:

- `tahoe_night` -> `CF6347E2-4F81-4410-8892-4830991B6C5A`
- `tahoe_morning` -> `B2FC91ED-6891-4DEB-85A1-268B2B4160B6`
- `tahoe_day` -> `4C108785-A7BA-422E-9C79-B0129F1D5550`
- `tahoe_evening` -> `52ACB9B8-75FC-4516-BC60-4550CFF3B661`

## Schedule We Set Up

The intended schedule was:

- `20:00` to `05:00` -> `Tahoe Night`
- `05:00` to `09:00` -> `Tahoe Morning`
- `09:00` to `17:00` -> `Tahoe Day`
- `17:00` to `20:00` -> `Tahoe Evening`

During menu testing, the `17:00` slot was temporarily changed more than once. At last inspection, the live `config.json` had:

- `05:00` -> `tahoe_morning`
- `09:00` -> `tahoe_day`
- `17:00` -> `tahoe_morning`
- `20:00` -> `tahoe_night`

So the `17:00` block may still currently be set to `Tahoe Morning` even though its `period` is still `evening`.

## Menu Bar Design Decisions

The menu bar companion went through a few iterations. The current design intent is:

- Icon-only menu bar item, no extra `Tahoe` text beside the icon
- Menu bar icon follows the current time period, not the selected clip
- Top-level menu items show only time ranges, not `Morning`, `Day`, `Evening`, or `Night`
- Clip names inside submenus keep the full Tahoe names:
  - `Tahoe Morning`
  - `Tahoe Day`
  - `Tahoe Evening`
  - `Tahoe Night`
- `Tahoe Night` should appear at the bottom of the submenu list
- `Open Config` stays
- The extra clutter items were removed:
  - `Sync Wallpaper To Current Time`
  - `Current block`
  - `Next change`
  - `Refresh Menu`
  - `Open Scheduler Folder`

## Bugs We Hit And Fixed

### Wallpaper Switching Bug

Problem:

- The wallpaper briefly went grey and then snapped back to the previous scene.

Cause:

- Only one wallpaper store plist was being updated.

Fix:

- Update both `Index_v2.plist` and `Index.plist`, then restart `WallpaperAgent`.

### JXA Menu Bar Errors

We hit repeated JXA bridge errors:

- `TypeError: Object is not a function (-2700)`

These came from several Cocoa bridge quirks in JXA, including:

- selector naming differences
- properties being treated like functions
- `separatorItem` behavior
- `representedObject` access
- object init patterns like `.alloc.init`

Those were iteratively fixed until the menu bar app launched and rendered properly.

## Known Limitation

There is still a brief grey flash during wallpaper switching.

Our current understanding is:

- This is likely caused by macOS tearing down and reloading the wallpaper surface when `WallpaperAgent` reapplies the native Aerial.
- With this native-plist-switching approach, we likely keep the true Aerial behavior but also keep that brief flash.
- A smoother transition would probably require a more custom wallpaper-rendering approach, which would move away from the native Apple Aerial pipeline.

## Why This Is Not Yet "Release-Ready"

Right now this is a good personal prototype, but not a clean shareable project yet. Main reasons:

- source of truth lives in `~/Library/Application Support/...` instead of a proper project repo
- launch agents use your personal machine paths
- the menu app is built ad hoc with `osacompile`
- there is no proper install script, uninstall script, or release packaging flow
- there is no GitHub-ready README, screenshots, or release notes structure
- there is no license choice yet

## Clean Path To Make It Releasable

The simplest releasable v1 is:

1. Create a proper repo folder and make that the source of truth.
2. Move or copy in:
   - `scheduler.py`
   - `TahoeAerialMenu.js`
   - default config
   - build/install scripts
3. Add:
   - `scripts/install.sh`
   - `scripts/uninstall.sh`
   - `scripts/build-menu-app.sh`
   - launch agent templates
   - `README.md`
   - `docs/RELEASING.md`
   - `.gitignore`
4. Make install scripts generate machine-specific paths at install time instead of hardcoding your personal paths into the repo.
5. Package a release ZIP for GitHub releases.

That would already make it shareable for technically comfortable Mac users.

## Longer-Term Better Version

If we want a more polished public release, the next stronger step would be:

- keep the scheduling logic
- replace the JXA menu bar app with a small native SwiftUI menu bar app

That would likely give:

- fewer fragile JXA bridge bugs
- better dialogs and settings UI
- easier packaging and signing later
- a more professional app structure for wider distribution

## Useful Commands From The Current Prototype

Show schedule:

```bash
"/Library/Frameworks/Python.framework/Versions/Current/bin/python3" "$HOME/Library/Application Support/TahoeAerialScheduler/scheduler.py" show-schedule
```

Show status:

```bash
"/Library/Frameworks/Python.framework/Versions/Current/bin/python3" "$HOME/Library/Application Support/TahoeAerialScheduler/scheduler.py" status
```

Apply current schedule:

```bash
"/Library/Frameworks/Python.framework/Versions/Current/bin/python3" "$HOME/Library/Application Support/TahoeAerialScheduler/scheduler.py" apply
```

Change a slot's clip:

```bash
"/Library/Frameworks/Python.framework/Versions/Current/bin/python3" "$HOME/Library/Application Support/TahoeAerialScheduler/scheduler.py" set-slot 17:00 tahoe_evening
```

Change a slot's start time:

```bash
"/Library/Frameworks/Python.framework/Versions/Current/bin/python3" "$HOME/Library/Application Support/TahoeAerialScheduler/scheduler.py" set-start-time 17:00 18:30
```

## Suggested Next Step

Use this folder as the new workspace and turn it into the actual repo source of truth. From there, the next build task is to copy the working installed prototype into this project folder and wrap it with proper install, uninstall, and packaging scripts.
