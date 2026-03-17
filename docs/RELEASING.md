# Releasing Tahoe Aerial Scheduler

## Before The First Public Release

- Choose a license
- Add screenshots or a short screen recording
- Confirm the installer works on a second Mac or a clean user account
- Confirm all four Tahoe Aerials are downloaded before install
- Decide whether you want to keep the current `com.eljee...` launch-agent labels or rename them before publishing

## Release Checklist

1. Update the source in `src/` and test with:

```bash
./scripts/install.sh
```

2. Verify:

- the menu bar item appears
- changing a slot from the menu updates the config
- changing a slot's start time works
- the scheduler applies the correct current clip
- reinstalling preserves `config.json`

3. Build the release archive:

```bash
./scripts/package-release.sh v0.1.0
```

4. Create a GitHub release and upload:

- `dist/TahoeAerialScheduler-v0.1.0.zip`

5. In the GitHub release notes, tell users:

- this is a per-user installer
- Tahoe Aerials must already be downloaded in System Settings
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

