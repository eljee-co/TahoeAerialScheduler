import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory


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
            scheduler.asset_video_path(current_asset["asset_id"]).touch()

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


if __name__ == "__main__":
    unittest.main()
