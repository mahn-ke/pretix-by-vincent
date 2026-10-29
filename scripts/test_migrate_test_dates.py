import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from migrate_test_dates import TOUR_SHIFT, localized, migrate_schedule, rewrite_text, shift_wall_time


class MigrationTests(unittest.TestCase):
    def test_explicit_category_and_short_dates(self):
        for old_day, target in ((26, 1), (27, 2), (28, 3), (29, 4)):
            self.assertEqual(rewrite_text(f"({old_day}.12.2026)"), f"({target:02d}.11.2026)")
            self.assertEqual(rewrite_text(f"({old_day}.12.)"), f"({target:02d}.11.)")
        self.assertEqual(rewrite_text("2025-12-27; 27.12.2025; 11:30"), "2025-12-27; 27.12.2025; 11:30")

    def test_localization_and_idempotency(self):
        original = {"en": "Day 1 (27.12.)", "de-informal": "Tag 1 (27.12.2026)"}
        changed = localized(original)
        self.assertEqual(changed["en"], "Day 1 (02.11.)")
        self.assertEqual(localized(changed), changed)

    def test_time_and_deadline_preservation(self):
        berlin = ZoneInfo("Europe/Berlin")
        value = datetime(2026, 12, 27, 11, 30, tzinfo=berlin)
        self.assertEqual(shift_wall_time(value, TOUR_SHIFT, berlin), datetime(2026, 11, 2, 11, 30, tzinfo=berlin))
        deadline = datetime(2026, 12, 17, 23, 59, tzinfo=berlin)
        self.assertEqual(shift_wall_time(deadline, TOUR_SHIFT, berlin), datetime(2026, 10, 23, 23, 59, tzinfo=berlin))
        self.assertIsNone(shift_wall_time(None, timedelta(days=1), berlin))

    def test_supplementary_schedule(self):
        original = {"schedule": {"conference": {
            "start": "2026-12-26", "end": "2026-12-30", "daysCount": 5,
            "days": [
                {"date": "2026-12-26", "rooms": {"Tour": [{"date": "2026-12-26T12:25:00+01:00", "start": "12:25"}]}},
                {"date": "2026-12-30", "rooms": {"Tour": []}},
            ],
        }}}
        result = migrate_schedule(original)["schedule"]["conference"]
        self.assertEqual(result["start"], "2026-11-01")
        self.assertEqual(result["end"], "2026-11-04")
        self.assertEqual(len(result["days"]), 1)
        self.assertEqual(result["days"][0]["rooms"]["Tour"][0]["date"], "2026-11-01T12:25:00+01:00")
        self.assertEqual(original["schedule"]["conference"]["days"][0]["date"], "2026-12-26")


if __name__ == "__main__":
    unittest.main()
