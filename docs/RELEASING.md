# Releasing Tahoe Aerial Scheduler

## Normal release flow

1. Finish the change on a branch, bump the stable `major.minor.patch` value in `VERSION`, and add the matching dated section to `CHANGELOG.md`.
2. Commit the final source, then run `./scripts/verify.sh v$(cat VERSION)` on that commit. This runs the regression tests, checks syntax, compiles both apps, verifies their local signatures and the disk image, and records the commit and measured duration.
3. Reinstall with `./scripts/install.sh`. Confirm the playing clip matches the schedule and the menu reports verified playback. Keep the user's existing schedule and clip assignments.
4. Open a pull request and wait for GitHub's full verification. Inspect `dist/verification.json` and the tested installer attached to the workflow.
5. After the version bump reaches `main`, the release workflow independently runs the same verification before creating and publishing the release.

The workflow attaches the disk image, its SHA-256 (Secure Hash Algorithm, 256-bit) checksum, the version/source build receipt, and the verification report. It reads the release notes from `CHANGELOG.md`. App bundles and the installed runtime carry the same version and source commit.

Published releases are immutable. A reused version tag that points at another commit fails validation. Rerunning the workflow for the same published version keeps its files unchanged. Failed publication may leave a draft; inspect its tag, commit and uploaded files before deciding how to resume it. Never blindly overwrite published assets or retry a partial upload.

GitHub Actions dependencies are pinned to verified commits. Dependabot proposes weekly grouped action updates through pull requests; those changes go through the same verification. A dependency update does not publish another app version unless `VERSION` is bumped.

## Live Mac verification

- The menu shows the actual `Playing` clip and the separate `Scheduled` clip.
- A wrong or unverified background produces a clear status, rather than a false success.
- `Restore Scheduled Background` retries recovery immediately; already healthy playback does not reload.
- A fallback to a default or still image and a stuck Aerial player recover to the intended clip.
- A failed recovery preserves its error and waits five minutes before another automatic reload.
- Scheduled switches keep native Aerial behavior; a brief fallback flash remains possible during renderer reloads.
- The current missing clip prompts for a download; missing future clips do not interrupt the user.
- Editing times and clip assignments works, and reinstalling preserves `config.json`.
- The installed launch agent checks on named minute boundaries.
- Healthy checks preserve the application timestamp and avoid routine log spam.
- A reinstall leaves one menu process and includes `uninstall.sh`.

Record the tested commit, macOS version, duration and observations. Reuse evidence only while source, base, environment and relevant configuration are unchanged. Test a clean user account or second Mac before describing the installer as broadly validated.

## Manual fallback

An existing tag can be released through the workflow's manual dispatch. Its `VERSION` must match the requested tag. Leaving the tag blank uses the workflow's current branch and VERSION.

To build locally:

```bash
./scripts/verify.sh "v$(cat VERSION)"
```

Review the resulting `dist/TahoeAerialScheduler-v*.dmg`, checksum, build receipt and verification report before manually creating a release. Keep the release tag tied to that exact tested commit, and do not replace previously published files.

## Notes users need

- Installation is per-user and requires Python 3.10 or newer.
- The download contains a double-click installer app.
- Only the current scheduled clip prompts for a missing download.
- The apps use local signatures for bundle integrity but are not signed with a Developer ID or notarized; macOS may require right-click > Open.
- Switching native Aerials may briefly show a fallback background.
- The scheduler relies on macOS's internal wallpaper format; a new macOS release still needs live compatibility verification.

## Remaining release work

- Test a clean user account or second Mac.
- Add screenshots or a short demonstration.
- Add Developer ID signing and notarization when the maintainer is ready to configure them.
