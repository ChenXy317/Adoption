"""开场阶段种子与摘要。"""
import unittest

from game import openings


class OpeningSeedTest(unittest.TestCase):
    def test_default_exists(self):
        item = openings.get("")
        self.assertIsNotNone(item)
        self.assertEqual(item["key"], "rain_night")
        self.assertTrue(str(item.get("system") or "").strip())
        self.assertEqual(openings.calendar_of(item)["hour"], 22)

    def test_unknown_returns_none(self):
        self.assertIsNone(openings.get("not_a_real_opening"))

    def test_public_list_hides_system(self):
        items = openings.public_list()
        keys = [item["key"] for item in items]
        self.assertEqual(
            keys, ["rain_night", "first_morning", "few_days", "settling_in"]
        )
        for item in items:
            self.assertNotIn("system", item)
            self.assertNotIn("persona_overlay", item)
            self.assertTrue(item["blurb"])
            self.assertTrue(item["time_label"])
            self.assertTrue(item["phase"])

    def test_later_start_is_familiar(self):
        item = openings.get("settling_in")
        snap = openings.snapshot(item)
        self.assertEqual(snap["key"], "settling_in")
        self.assertIn("噩梦", snap["system"])
        self.assertIn("daily_life", snap["persona_overlay"])
        self.assertGreater(int(item.get("game_minutes") or 0), 8000)
        self.assertEqual(openings.public_list()[-1]["phase"], "熟悉")


if __name__ == "__main__":
    unittest.main()
