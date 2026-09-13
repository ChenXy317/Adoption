"""game/ 纯函数层最小单元测试：时钟换算、条件边界、标签解析、属性钳制。"""
import unittest

from game import clock
from game.attributes import apply_deltas, clamp, phase_of
from game.tags import StateTagStripper, parse_state
from orm import AttributeDef


def make_def(key, name="属性", lo=0, hi=100, default=0, ai_editable=True):
    return AttributeDef(
        key=key, name=name, min=lo, max=hi, default_value=default,
        ai_editable=ai_editable, enabled=True,
    )


class ClockTest(unittest.TestCase):
    def test_default_start_offset(self):
        self.assertEqual(clock.start_offset({}), 173280)

    def test_absolute_and_split(self):
        abs_min = clock.absolute_minutes(0, {})
        d = clock.split(abs_min)
        self.assertEqual((d["month"], d["day"], d["hour"]), (5, 1, 8))
        self.assertEqual(d["period_key"], "morning")

    def test_advance_across_day(self):
        abs_min = clock.absolute_minutes(16 * 60, {})
        d = clock.split(abs_min)
        self.assertEqual((d["day"], d["hour"]), (2, 0))
        self.assertEqual(d["period_key"], "late_night")

    def test_period_boundaries(self):
        cases = {
            0: "late_night",
            299: "late_night",
            300: "dawn",
            479: "dawn",
            480: "morning",
            659: "morning",
            660: "noon",
            779: "noon",
            780: "afternoon",
            1019: "afternoon",
            1020: "evening",
            1139: "evening",
            1140: "night",
            1319: "night",
            1320: "late_night",
            1439: "late_night",
        }
        for minute, expected in cases.items():
            self.assertEqual(clock.period_of(minute)[0], expected, minute)

    def test_labels(self):
        abs_min = clock.absolute_minutes(0, {})
        self.assertEqual(clock.time_label(abs_min), "5 月 1 日 · 上午")
        self.assertEqual(clock.full_label(abs_min), "5 月 1 日 · 上午 08:00")

    def test_custom_calendar(self):
        settings = {"calendar": {"month": 12, "day": 30, "hour": 23, "minute": 30}}
        d = clock.split(clock.absolute_minutes(0, settings))
        self.assertEqual((d["month"], d["day"], d["hour"], d["minute"]), (12, 30, 23, 30))
        d2 = clock.split(clock.absolute_minutes(31, settings))
        self.assertEqual((d2["month"], d2["day"], d2["hour"]), (1, 1, 0))


class AttributesTest(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(120, 0, 100), 100)
        self.assertEqual(clamp(-5, 0, 100), 0)

    def test_apply_deltas_caps_and_skips(self):
        defs = {
            "affection": make_def("affection"),
            "money": make_def("money", "金钱", lo=0, hi=10**9, default=2000, ai_editable=False),
        }
        values = {"affection": 50.0, "money": 2000.0}
        new_values, changes = apply_deltas(
            defs, values, {"affection": 999, "money": 100, "unknown": 5}
        )
        self.assertEqual(new_values["affection"], 70.0)
        self.assertEqual(new_values["money"], 2000.0)
        self.assertEqual([c["key"] for c in changes], ["affection"])

    def test_apply_deltas_min_max(self):
        defs = {"mood": make_def("mood", hi=60)}
        new_values, _ = apply_deltas(defs, {"mood": 55.0}, {"mood": 20})
        self.assertEqual(new_values["mood"], 60.0)
        new_values, _ = apply_deltas(defs, {"mood": 5.0}, {"mood": -20})
        self.assertEqual(new_values["mood"], 0.0)

    def test_phase_of(self):
        self.assertEqual(phase_of({"affection": 95, "trust": 95, "dependence": 95}), "依恋")
        self.assertEqual(phase_of({"affection": 0, "trust": 0, "dependence": 0}), "陌生")


class TagsTest(unittest.TestCase):
    def test_strip_simple(self):
        s = StateTagStripper()
        text = '你好。\n<<<STATE {"attrs":{}} STATE>>>'
        visible = s.feed(text) + s.flush()
        self.assertEqual(visible.strip(), "你好。")
        self.assertTrue(s.tag_found)
        self.assertEqual(parse_state(s.state_raw), {"attrs": {}})

    def test_strip_across_chunks(self):
        s = StateTagStripper()
        out = ""
        for piece in ["前半", "段<<<STA", 'TE {"attrs":{"affection":2},', '"time":{"advance_minutes":5}} STATE', ">>>尾巴"]:
            out += s.feed(piece)
        out += s.flush()
        self.assertEqual(out, "前半段尾巴")
        self.assertEqual(
            parse_state(s.state_raw),
            {"attrs": {"affection": 2}, "time": {"advance_minutes": 5}},
        )

    def test_partial_marker_held(self):
        s = StateTagStripper()
        out = s.feed("普通文本 <<")
        self.assertEqual(out, "普通文本 ")
        out += s.feed("ST")
        self.assertEqual(out, "普通文本 <<ST")

    def test_invalid_json(self):
        self.assertIsNone(parse_state("{broken"))
        self.assertIsNone(parse_state(""))
        self.assertIsNone(parse_state("[1,2]"))

    def test_fenced_json(self):
        self.assertEqual(parse_state("```json\n{\"attrs\":{}}\n```"), {"attrs": {}})

    def test_unclosed_tag_dropped(self):
        s = StateTagStripper()
        out = s.feed("正文<<<STATE {\"attrs\":")
        out += s.flush()
        self.assertEqual(out, "正文")
        self.assertFalse(s.tag_found)


if __name__ == "__main__":
    unittest.main()
