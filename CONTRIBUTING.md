# Contributing

Thanks for helping improve Tahoe Aerial Scheduler.

## Local Setup

1. Clone the repo on a Mac that has the Tahoe Aerials available.
2. Make sure the Tahoe Aerials have already been downloaded once in `System Settings > Wallpaper`.
3. Install Python 3 if needed.
4. Run:

```bash
./scripts/install.sh
```

That installs the live runtime into:

- `~/Library/Application Support/TahoeAerialScheduler`
- `~/Applications/Tahoe Aerial Menu.app`

## Development Loop

Edit:

- `src/scheduler.py`
- `src/TahoeAerialMenu.js`
- `resources/default-config.json`

Then reinstall:

```bash
./scripts/install.sh
```

## Quick Checks

Validate shell scripts:

```bash
bash -n scripts/install.sh
bash -n scripts/uninstall.sh
bash -n scripts/build-menu-app.sh
bash -n scripts/package-release.sh
```

Validate the scheduler:

```bash
python3 -m py_compile src/scheduler.py
```

Compile the menu app:

```bash
./scripts/build-menu-app.sh
```

## What To Mention In Pull Requests

- what changed
- how you tested it
- whether you tested on a clean user account or only on an existing install
- whether the change affects the menu bar app, scheduler, installer, or release flow

