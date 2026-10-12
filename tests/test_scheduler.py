import sys
import json
import os
import plistlib
import subprocess
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scheduler


class SchedulerSlotTests(unittest.TestCase):
    def test_0823_uses_morning_slot(self):
        slot = scheduler.slot_for_now(
            scheduler.DEFAULT_CONFIG,
            datetime(2026, 4, 26, 8, 23),
        )

        self.assertEqual(slot.start, "05:00")
        self.assertEqual(slot.asset_key, "tahoe_morning")

    def test_slot_start_wraps_to_previous_day_after_midnight(self):
        slot = scheduler.slot_for_now(
            scheduler.DEFAULT_CONFIG,
            datetime(2026, 4, 26, 1, 0),
        )

        self.assertEqual(
            scheduler.slot_started_at(datetime(2026, 4, 26, 1, 0), slot),
            datetime(2026, 4, 25, 20, 0),
        )

    def test_stale_active_store_refreshes_for_current_slot(self):
        slot = scheduler.slot_for_now(
            scheduler.DEFAULT_CONFIG,
            datetime(2026, 4, 26, 8, 23),
        )

        self.assertTrue(
            scheduler.active_store_needs_refresh(
                slot,
                datetime(2026, 4, 26, 8, 23),
                datetime(2026, 4, 26, 4, 59),
            )
        )
        self.assertFalse(
            scheduler.active_store_needs_refresh(
                slot,
                datetime(2026, 4, 26, 8, 23),
                datetime(2026, 4, 26, 5, 1),
            )
        )

    def test_state_refresh_guard_accepts_current_slot_refresh(self):
        current = datetime(2026, 4, 26, 8, 23)
        slot = scheduler.slot_for_now(scheduler.DEFAULT_CONFIG, current)

        self.assertTrue(
            scheduler.state_refreshed_current_slot(
                slot,
                current,
                "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
                {
                    "last_applied_asset_id": "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
                    "last_applied_at": "2026-04-26T08:22:00",
                },
            )
        )

    def test_state_refresh_guard_rejects_previous_slot_refresh(self):
        current = datetime(2026, 4, 26, 8, 23)
        slot = scheduler.slot_for_now(scheduler.DEFAULT_CONFIG, current)

        self.assertFalse(
            scheduler.state_refreshed_current_slot(
                slot,
                current,
                "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
                {
                    "last_applied_asset_id": "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
                    "last_applied_at": "2026-04-26T04:59:00",
                },
            )
        )

    def test_state_refresh_guard_rejects_other_asset(self):
        current = datetime(2026, 4, 26, 8, 23)
        slot = scheduler.slot_for_now(scheduler.DEFAULT_CONFIG, current)

        self.assertFalse(
            scheduler.state_refreshed_current_slot(
                slot,
                current,
                "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
                {
                    "last_applied_asset_id": "4C108785-A7BA-422E-9C79-B0129F1D5550",
                    "last_applied_at": "2026-04-26T08:22:00",
                },
            )
        )

    def test_asset_id_from_video_path(self):
        self.assertEqual(
            scheduler.asset_id_from_video_path(
                str(
                    scheduler.AERIAL_VIDEOS_DIR
                    / "B2FC91ED-6891-4DEB-85A1-268B2B4160B6.mov"
                )
            ),
            "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
        )
        self.assertIsNone(scheduler.asset_id_from_video_path("/tmp/not-a-video.txt"))

    def test_current_missing_assets_ignores_missing_future_slot(self):
        original_videos_dir = scheduler.AERIAL_VIDEOS_DIR

        with TemporaryDirectory() as temp_dir:
            scheduler.AERIAL_VIDEOS_DIR = Path(temp_dir)
            current_asset = scheduler.asset_from_key(
                scheduler.DEFAULT_CONFIG,
                "tahoe_morning",
            )
            scheduler.asset_video_path(current_asset["asset_id"]).write_bytes(b"downloaded video")

            try:
                self.assertEqual(
                    scheduler.current_missing_assets(
                        scheduler.DEFAULT_CONFIG,
                        datetime(2026, 4, 26, 8, 23),
                    ),
                    [],
                )
                self.assertTrue(scheduler.missing_assets(scheduler.DEFAULT_CONFIG))
            finally:
                scheduler.AERIAL_VIDEOS_DIR = original_videos_dir

    def test_current_missing_assets_reports_current_slot(self):
        original_videos_dir = scheduler.AERIAL_VIDEOS_DIR

        with TemporaryDirectory() as temp_dir:
            scheduler.AERIAL_VIDEOS_DIR = Path(temp_dir)

            try:
                missing = scheduler.current_missing_assets(
                    scheduler.DEFAULT_CONFIG,
                    datetime(2026, 4, 26, 8, 23),
                )
            finally:
                scheduler.AERIAL_VIDEOS_DIR = original_videos_dir

        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["asset_key"], "tahoe_morning")

    def test_legacy_default_choice_can_be_converted_to_aerial_asset(self):
        container = {
            "Content": {
                "Choices": [
                    {
                        "Provider": "default",
                        "Files": ["old"],
                        "Configuration": b"",
                    }
                ],
                "EncodedOptionValues": b"stale-shuffle-setting",
            }
        }

        changed = scheduler.update_content_container(
            container,
            "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
            datetime(2026, 4, 26, 8, 23),
            allow_provider_conversion=True,
        )

        choice = container["Content"]["Choices"][0]
        self.assertTrue(changed)
        self.assertEqual(choice["Provider"], scheduler.AERIAL_PROVIDER)
        self.assertEqual(
            scheduler.decode_asset_id(choice),
            "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
        )
        self.assertEqual(choice["Files"], [])
        self.assertNotIn("EncodedOptionValues", container["Content"])

    def test_legacy_image_choice_can_be_repaired_to_aerial_asset(self):
        container = {
            "Content": {
                "Choices": [
                    {
                        "Provider": "com.apple.wallpaper.choice.image",
                        "Files": ["/tmp/static-transition.png"],
                    }
                ],
                "EncodedOptionValues": b"stale-image-setting",
            }
        }

        changed = scheduler.update_content_container(
            container,
            "4C108785-A7BA-422E-9C79-B0129F1D5550",
            datetime(2026, 4, 26, 8, 23),
            allow_provider_conversion=True,
        )

        choice = container["Content"]["Choices"][0]
        self.assertTrue(changed)
        self.assertEqual(choice["Provider"], scheduler.AERIAL_PROVIDER)
        self.assertEqual(
            scheduler.decode_asset_id(choice),
            "4C108785-A7BA-422E-9C79-B0129F1D5550",
        )
        self.assertEqual(choice["Files"], [])
        self.assertNotIn("EncodedOptionValues", container["Content"])

    def test_nested_space_desktop_choice_can_be_repaired(self):
        store = {
            "Spaces": {
                "space-id": {
                    "Default": {
                        "Desktop": {
                            "Content": {
                                "Choices": [
                                    {
                                        "Provider": "com.apple.wallpaper.choice.image",
                                        "Files": [],
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }

        changed = scheduler.update_store_sections(
            store,
            "4C108785-A7BA-422E-9C79-B0129F1D5550",
            datetime(2026, 4, 26, 8, 23),
            allow_provider_conversion=True,
        )

        choice = store["Spaces"]["space-id"]["Default"]["Desktop"]["Content"][
            "Choices"
        ][0]
        self.assertTrue(changed)
        self.assertEqual(choice["Provider"], scheduler.AERIAL_PROVIDER)
        self.assertEqual(
            scheduler.decode_asset_id(choice),
            "4C108785-A7BA-422E-9C79-B0129F1D5550",
        )

    def test_legacy_shuffle_options_are_removed_when_asset_already_matches(self):
        container = {
            "Content": {
                "Choices": [
                    {
                        "Provider": scheduler.AERIAL_PROVIDER,
                        "Files": [],
                        "Configuration": scheduler.configuration_blob(
                            "B2FC91ED-6891-4DEB-85A1-268B2B4160B6"
                        ),
                    }
                ],
                "EncodedOptionValues": b"stale-shuffle-setting",
            }
        }

        changed = scheduler.update_content_container(
            container,
            "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
            datetime(2026, 4, 26, 8, 23),
            allow_provider_conversion=True,
        )

        self.assertTrue(changed)
        self.assertNotIn("EncodedOptionValues", container["Content"])

    def test_legacy_asset_id_accepts_idle_store_shape(self):
        original_load_plist = scheduler.load_plist

        def fake_load_plist(path):
            return {
                "AllSpacesAndDisplays": {
                    "Type": "idle",
                    "Idle": {
                        "Content": {
                            "Choices": [
                                {
                                    "Provider": scheduler.AERIAL_PROVIDER,
                                    "Files": [],
                                    "Configuration": scheduler.configuration_blob(
                                        "4C108785-A7BA-422E-9C79-B0129F1D5550"
                                    ),
                                }
                            ]
                        }
                    },
                }
            }

        scheduler.load_plist = fake_load_plist
        try:
            self.assertEqual(
                scheduler.legacy_asset_id(),
                "4C108785-A7BA-422E-9C79-B0129F1D5550",
            )
        finally:
            scheduler.load_plist = original_load_plist


class SchedulerRecoveryTests(unittest.TestCase):
    now = datetime(2026, 10, 12, 15, 0)
    desired_id = scheduler.DEFAULT_ASSETS["tahoe_day"]["asset_id"]
    other_id = "6511D2B5-E185-4886-9505-B4004E920D27"

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(
            scheduler, APP_DIR=self.root, CONFIG_PATH=self.root / "config.json",
            STATE_PATH=self.root / "state.json", LOG_PATH=self.root / "scheduler.log",
            MENU_LOG_PATH=self.root / "menu-ui.log", LIVE_PLIST=self.root / "Index_v2.plist",
            LEGACY_PLIST=self.root / "Index.plist", AERIAL_VIDEOS_DIR=self.root / "videos",
        )
        self.paths.start()
        self.addCleanup(self.paths.stop)
        scheduler.AERIAL_VIDEOS_DIR.mkdir()
        for asset in scheduler.DEFAULT_ASSETS.values():
            scheduler.asset_video_path(asset["asset_id"]).write_bytes(b"downloaded video")
        scheduler.write_json(scheduler.CONFIG_PATH, scheduler.DEFAULT_CONFIG)
        test = self

        class ClockMeta(type):
            def __instancecheck__(cls, value):
                return isinstance(value, datetime)

        class Clock(datetime, metaclass=ClockMeta):
            @classmethod
            def now(cls, tz=None):
                return test.now.astimezone(tz) if tz else test.now

        self.clock = patch.object(scheduler, "datetime", Clock)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.player = patch.object(scheduler, "observe_playback", return_value=scheduler.Playback((self.desired_id,)))
        self.observe = self.player.start()
        self.addCleanup(self.player.stop)
        self.restart_patch = patch.object(scheduler, "restart_wallpaper_agent")
        self.restart = self.restart_patch.start()
        self.addCleanup(self.restart_patch.stop)
        self.verify_patch = patch.object(scheduler, "verify_playback", return_value=(scheduler.Playback((self.desired_id,)), True))
        self.verify = self.verify_patch.start()
        self.addCleanup(self.verify_patch.stop)
        self.stores()

    def container(self, asset_id=None, provider=None):
        return {
            "LastSet": self.now.astimezone(timezone.utc).replace(tzinfo=None),
            "Content": {"Choices": [{
                "Provider": provider or scheduler.AERIAL_PROVIDER,
                "Files": [],
                "Configuration": scheduler.configuration_blob(asset_id or self.desired_id),
            }], "Shuffle": "$null"},
        }

    def stores(self, provider=None, asset_id=None):
        live = {"AllSpacesAndDisplays": {"Desktop": self.container(asset_id, provider)}}
        legacy = {"AllSpacesAndDisplays": {"Idle": self.container()}}
        scheduler.LIVE_PLIST.write_bytes(plistlib.dumps(live))
        scheduler.LEGACY_PLIST.write_bytes(plistlib.dumps(legacy))

    def healthy_state(self):
        return {
            "last_applied_asset": "tahoe_day", "last_applied_asset_id": self.desired_id,
            "last_applied_at": self.now.astimezone().isoformat(),
            "last_verified_at": self.now.astimezone().isoformat(),
            "last_verified_asset_id": self.desired_id,
            "health": "verified", "last_error": None, "version": scheduler.app_version(),
        }

    def test_repairs_live_default_and_image_fallbacks(self):
        for provider in ("default", "com.apple.wallpaper.choice.image"):
            with self.subTest(provider=provider):
                self.stores(provider=provider)
                self.observe.return_value = scheduler.Playback((self.other_id,))
                self.assertEqual(scheduler.apply_current_schedule(force=True, quiet=True), 0)
                self.assertEqual(scheduler.current_asset_id(), self.desired_id)
                self.assertTrue(scheduler.desktop_store_matches(self.desired_id))
                self.assertEqual(scheduler.read_state()["health"], "verified")
        self.assertEqual(self.restart.call_count, 2)

    def test_correct_store_still_restarts_a_stuck_player(self):
        scheduler.write_state(self.healthy_state())
        self.observe.return_value = scheduler.Playback((self.other_id,))
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_called_once()
        self.assertEqual(scheduler.read_state()["last_applied_asset_id"], self.desired_id)

    def test_unchanged_store_is_not_an_error(self):
        self.assertFalse(scheduler.write_store(self.desired_id, self.now))

    def test_unsupported_live_provider_cannot_report_legacy_only_success(self):
        self.stores(provider="unknown.provider")
        before = scheduler.LEGACY_PLIST.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "not supported"):
            scheduler.write_store(self.desired_id, self.now)
        self.assertEqual(scheduler.LEGACY_PLIST.read_bytes(), before)

    def test_healthy_minute_checks_do_not_restart_rewrite_or_log(self):
        scheduler.write_state(self.healthy_state())
        state = scheduler.STATE_PATH.read_bytes()
        stat = scheduler.STATE_PATH.stat().st_mtime_ns
        for _ in range(3):
            self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_not_called()
        self.assertEqual(scheduler.STATE_PATH.read_bytes(), state)
        self.assertEqual(scheduler.STATE_PATH.stat().st_mtime_ns, stat)
        self.assertFalse(scheduler.LOG_PATH.exists())

    def test_new_version_observation_preserves_last_application_time(self):
        state = self.healthy_state()
        state["version"] = "0.1.3"
        state["last_applied_at"] = (self.now - timedelta(hours=2)).isoformat()
        scheduler.write_state(state)
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.assertEqual(scheduler.read_state()["last_applied_at"], state["last_applied_at"])
        self.restart.assert_not_called()

    def test_unknown_playback_is_not_claimed_as_verified(self):
        scheduler.write_state(self.healthy_state())
        self.observe.return_value = scheduler.Playback(available=False, reason="Inspection unavailable.")
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_not_called()
        self.assertEqual(scheduler.read_state()["health"], "unverified")
        self.assertEqual(scheduler.build_info()["playback"]["status"], "unverified")

    def test_player_missing_is_recovered_without_a_false_success(self):
        self.observe.return_value = scheduler.Playback(reason="Player is not running.")
        self.verify.return_value = (self.observe.return_value, True)
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        state = scheduler.read_state()
        self.assertEqual(state["health"], "unverified")
        self.assertNotIn("last_applied_asset_id", state)
        self.now += timedelta(minutes=1)
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_called_once()

    def test_failed_verification_is_logged_and_does_not_advance_success(self):
        self.observe.return_value = scheduler.Playback((self.other_id,))
        self.verify.return_value = (self.observe.return_value, True)
        self.assertEqual(scheduler.main(["scheduler.py", "apply", "--quiet"]), 1)
        state = scheduler.read_state()
        self.assertEqual(state["health"], "error")
        self.assertNotIn("last_applied_asset_id", state)
        self.assertIn("not yet confirmed", scheduler.LOG_PATH.read_text())

    def test_failed_recovery_backs_off_but_new_asset_and_manual_repair_can_retry(self):
        state = {"health": "error", "last_attempt_asset_id": self.desired_id,
                 "last_attempt_at": self.now.isoformat()}
        scheduler.write_state(state)
        self.observe.return_value = scheduler.Playback((self.other_id,))
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 1)
        self.restart.assert_not_called()
        self.assertFalse(scheduler.recovery_attempt_is_recent(state, self.other_id, self.now))
        self.assertEqual(scheduler.apply_current_schedule(force=True, quiet=True), 0)
        self.restart.assert_called_once()

    def test_successful_attempt_does_not_delay_repair_of_new_drift(self):
        state = dict(self.healthy_state(), last_attempt_asset_id=self.desired_id, last_attempt_at=self.now.isoformat())
        scheduler.write_state(state)
        self.observe.return_value = scheduler.Playback((self.other_id,))
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_called_once()

    def test_actual_clip_is_reported_separately_from_scheduled_clip(self):
        self.observe.return_value = scheduler.Playback((scheduler.DEFAULT_ASSETS["tahoe_night"]["asset_id"],))
        info = scheduler.build_info()
        self.assertEqual(info["current_slot"]["label"], "Tahoe Day")
        self.assertEqual(info["playback"]["label"], "Tahoe Night")
        self.assertEqual(info["playback"]["status"], "mismatch")

    def test_nested_display_override_is_detected_and_repaired(self):
        store = scheduler.load_plist(scheduler.LIVE_PLIST)
        store["Displays"] = {"external": {"Desktop": self.container(self.other_id)}}
        scheduler.LIVE_PLIST.write_bytes(plistlib.dumps(store))
        self.assertFalse(scheduler.desktop_store_matches(self.desired_id))
        scheduler.write_store(self.desired_id, self.now)
        self.assertTrue(scheduler.desktop_store_matches(self.desired_id))

    def test_legacy_desktop_fallback_is_detected_even_with_a_matching_cached_player(self):
        store = scheduler.load_plist(scheduler.LEGACY_PLIST)
        store["AllSpacesAndDisplays"]["Desktop"] = self.container(provider="com.apple.wallpaper.choice.image")
        scheduler.LEGACY_PLIST.write_bytes(plistlib.dumps(store))
        scheduler.write_state(self.healthy_state())
        self.assertFalse(scheduler.desktop_store_matches(self.desired_id))
        self.assertEqual(scheduler.build_info()["playback"]["status"], "mismatch")
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_called_once()
        self.assertTrue(scheduler.desktop_store_matches(self.desired_id))

    def test_idle_saver_drift_does_not_restart_a_healthy_desktop(self):
        store = scheduler.load_plist(scheduler.LEGACY_PLIST)
        store["AllSpacesAndDisplays"]["Idle"] = self.container(self.other_id)
        scheduler.LEGACY_PLIST.write_bytes(plistlib.dumps(store))
        scheduler.write_state(self.healthy_state())
        self.assertTrue(scheduler.desktop_store_matches(self.desired_id))
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.restart.assert_not_called()

    def test_shuffle_is_disabled_and_duplicate_choices_removed(self):
        container = self.container(self.other_id)
        container["Content"]["Choices"].append(self.container()["Content"]["Choices"][0])
        container["Content"]["Shuffle"] = {"Enabled": True}
        scheduler.update_content_container(container, self.desired_id, self.now)
        self.assertEqual(len(container["Content"]["Choices"]), 1)
        self.assertEqual(container["Content"]["Shuffle"], "$null")

    def test_failed_atomic_write_preserves_valid_original(self):
        scheduler.write_state({"health": "verified"})
        before = scheduler.STATE_PATH.read_bytes()
        with patch.object(scheduler.os, "fsync", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                scheduler.write_state({"health": "error"})
        self.assertEqual(scheduler.STATE_PATH.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".state.json.*")), [])

    def test_log_rotation_retains_a_bounded_history_with_timestamps(self):
        with patch.object(scheduler, "LOG_MAX_BYTES", 80), patch.object(scheduler, "LOG_BACKUPS", 2):
            for index in range(8):
                scheduler.log_event(f"Recovery event {index}: " + "x" * 80)
        logs = list(self.root.glob("scheduler.log*"))
        self.assertEqual(len(logs), 3)
        self.assertIn("Recovery event 7", scheduler.LOG_PATH.read_text())
        self.assertIn("2026-10-12T15:00:00", scheduler.LOG_PATH.read_text())

    def test_old_large_logs_are_trimmed_when_archived(self):
        scheduler.LOG_PATH.write_text("An old event\n" * 1000)
        with patch.object(scheduler, "LOG_MAX_BYTES", 256):
            scheduler.log_event("Latest event")
        archived = self.root / "scheduler.log.1"
        self.assertLessEqual(archived.stat().st_size, 256)
        self.assertTrue(archived.read_text().startswith("An old event"))

    def test_empty_download_is_not_reported_as_ready(self):
        scheduler.asset_video_path(self.desired_id).write_bytes(b"")
        self.assertEqual(scheduler.current_missing_assets(scheduler.DEFAULT_CONFIG, self.now)[0]["asset_id"], self.desired_id)

    def test_verification_waits_for_the_replacement_player(self):
        self.verify_patch.stop()
        self.observe.side_effect = [scheduler.Playback((self.other_id,)), scheduler.Playback((self.desired_id,))]
        with patch.object(scheduler.time, "sleep"):
            playback, matches = scheduler.verify_playback(self.desired_id)
        self.assertTrue(matches)
        self.assertEqual(playback.asset_ids, (self.desired_id,))

    def test_corrupt_state_can_be_recovered(self):
        scheduler.STATE_PATH.write_text('{"partial":')
        self.assertEqual(scheduler.read_state(), {})
        self.assertEqual(scheduler.apply_current_schedule(quiet=True), 0)
        self.assertEqual(scheduler.read_state()["health"], "verified")

    def test_empty_schedule_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            scheduler.validate_config(dict(scheduler.DEFAULT_CONFIG, schedule=[]))

    def test_timestamps_round_trip_in_new_zealand_timezone(self):
        original_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Pacific/Auckland"
            time.tzset()
            self.stores(asset_id=self.other_id)
            scheduler.write_store(self.desired_id, self.now)
            stored = scheduler.load_plist(scheduler.LIVE_PLIST)["AllSpacesAndDisplays"]["Desktop"]["LastSet"]
            self.assertEqual(stored.hour, 2)
            with patch.object(scheduler, "datetime", datetime):
                self.assertEqual(scheduler.active_desktop_last_set_at(), self.now)
            self.assertEqual(scheduler.parse_state_timestamp("2026-10-12T02:00:00+00:00"), self.now)
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()


class PlaybackInspectionTests(unittest.TestCase):
    def test_process_permission_error_is_distinguished_from_idle(self):
        with patch.object(scheduler.subprocess, "run", return_value=subprocess.CompletedProcess([], 3, "", "Denied")):
            self.assertFalse(scheduler.observe_playback().available)
        with patch.object(scheduler.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")):
            idle = scheduler.observe_playback()
            self.assertTrue(idle.available)
            self.assertEqual(idle.asset_ids, ())

    def test_every_player_is_inspected_so_one_correct_display_cannot_hide_another(self):
        ids = [scheduler.DEFAULT_ASSETS["tahoe_day"]["asset_id"], scheduler.DEFAULT_ASSETS["tahoe_night"]["asset_id"]]
        results = [subprocess.CompletedProcess([], 0, "100\n101\n", "")]
        results.extend(subprocess.CompletedProcess([], 0, "n" + str(scheduler.asset_video_path(asset_id)), "") for asset_id in ids)
        with patch.object(scheduler.subprocess, "run", side_effect=results):
            playback = scheduler.observe_playback()
        self.assertEqual(playback.asset_ids, tuple(ids))
        self.assertEqual(scheduler.playback_status(ids[0], playback, True), "mismatch")

    def test_restart_stops_old_player_before_starting_new_agent(self):
        with patch.object(scheduler.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            scheduler.restart_wallpaper_agent()
        self.assertEqual(run.call_args_list[0].args[0][0:2], ["/usr/bin/killall", scheduler.AERIAL_EXTENSION_PROCESS])
        self.assertEqual(run.call_args_list[1].args[0][0:3], ["/bin/launchctl", "kickstart", "-k"])


if __name__ == "__main__":
    unittest.main()
