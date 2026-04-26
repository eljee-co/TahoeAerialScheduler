import sys
import unittest
from datetime import datetime
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
