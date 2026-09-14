"""事件引擎纯函数层单元测试：条件求值、每日判定、可用性与冷却。"""
import json
import unittest

from config import (
    GIFT_TIERS,
    MOOD_LABEL_TTL_HOURS,
    SEEDS_DIR,
    WORK_HOURS,
    WORK_PAY,
)
from game import clock
from game.events import (
    EvalContext,
    availability,
    check_cost,
    compare,
    evaluate,
    mood_label_of,
    roll_chance,
)
from orm import EventDef


class FixedRng:
    """固定 random() 返回值，便于确定性验证概率判定。"""

    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def make_event(**overrides):
    fields = {
        "key": "test_event",
        "name": "测试事件",
        "category": "fixed",
        "trigger": {},
        "cost": {},
        "effects": {},
        "prompt_template": "",
        "once": False,
        "cooldown_minutes": 0,
        "priority": 0,
        "enabled": True,
    }
    fields.update(overrides)
    return EventDef(**fields)


def make_ctx(**overrides):
    fields = {
        "attrs": {"affection": 30.0, "trust": 20.0, "money": 100.0},
        "flags": {"story_done": True, "stage": 2},
        "game_day": 3,
        "month": 5,
        "day": 3,
        "hour": 20,
        "minute": 30,
        "period": "night",
        "absolute": 173280 + 2 * clock.DAY_MINUTES + 20 * 60 + 30,
        "minutes_since": {"story_done": 5000},
    }
    fields.update(overrides)
    return EvalContext(**fields)


class ClockExtensionTest(unittest.TestCase):
    def test_day_index(self):
        self.assertEqual(clock.day_index(0), 0)
        self.assertEqual(clock.day_index(clock.DAY_MINUTES), 1)
        self.assertEqual(clock.day_index(clock.DAY_MINUTES * 3 + 100), 3)

    def test_game_day_of(self):
        self.assertEqual(clock.game_day_of(0, {}), 1)
        self.assertEqual(clock.game_day_of(16 * 60 - 1, {}), 1)
        self.assertEqual(clock.game_day_of(16 * 60, {}), 2)
        self.assertEqual(clock.game_day_of(40 * 60, {}), 3)

    def test_day_starts_between(self):
        day = clock.DAY_MINUTES
        self.assertEqual(clock.day_starts_between(10, 5), [])
        self.assertEqual(clock.day_starts_between(10, day), [day])
        self.assertEqual(
            clock.day_starts_between(10, day * 2), [day, day * 2]
        )
        self.assertEqual(clock.day_starts_between(0, 10), [])

    def test_next_period_start(self):
        abs_now = clock.absolute_minutes(0, {})
        target = clock.next_period_start(abs_now, "night")
        self.assertEqual(clock.split(target)["period_key"], "night")
        self.assertGreater(target, abs_now)
        later = clock.next_period_start(target, "night")
        self.assertEqual(later - target, clock.DAY_MINUTES)
        self.assertIsNone(clock.next_period_start(abs_now, "nope"))


class CompareTest(unittest.TestCase):
    def test_numeric_and_string(self):
        self.assertTrue(compare(">=", 3, 3))
        self.assertTrue(compare(">", "3.5", 3))
        self.assertFalse(compare("<", 3, 3))
        self.assertTrue(compare("==", "night", "night"))
        self.assertTrue(compare("!=", 1, 2))
        self.assertTrue(compare("contains", ["a", "b"], "b"))
        self.assertTrue(compare("truthy", 1, None))
        self.assertFalse(compare("truthy", 0, None))


class EvaluateTest(unittest.TestCase):
    def test_attr(self):
        ctx = make_ctx()
        self.assertTrue(evaluate(
            {"type": "attr", "key": "affection", "op": ">=", "value": 30}, ctx
        ))
        self.assertFalse(evaluate(
            {"type": "attr", "key": "affection", "op": ">", "value": 30}, ctx
        ))
        self.assertTrue(evaluate(
            {"type": "attr", "key": "missing", "op": "<", "value": 1}, ctx
        ))

    def test_flag(self):
        ctx = make_ctx()
        self.assertTrue(evaluate({"type": "flag", "key": "story_done"}, ctx))
        self.assertTrue(evaluate(
            {"type": "flag", "key": "story_done", "value": True}, ctx
        ))
        self.assertFalse(evaluate(
            {"type": "flag", "key": "story_done", "value": False}, ctx
        ))
        self.assertTrue(evaluate(
            {"type": "flag", "key": "stage", "op": ">=", "value": 2}, ctx
        ))
        self.assertFalse(evaluate({"type": "flag", "key": "nope"}, ctx))

    def test_time_conditions(self):
        ctx = make_ctx()
        self.assertTrue(evaluate({"type": "period", "in": ["night"]}, ctx))
        self.assertFalse(evaluate({"type": "period", "in": ["morning"]}, ctx))
        self.assertTrue(evaluate(
            {"type": "game_day", "op": ">=", "value": 3}, ctx
        ))
        self.assertTrue(evaluate({"type": "hour", "op": ">=", "value": 20}, ctx))
        self.assertFalse(evaluate({"type": "hour", "op": "<", "value": 20}, ctx))
        self.assertTrue(evaluate({"type": "date", "month": 5, "day": 3}, ctx))
        self.assertFalse(evaluate({"type": "date", "month": 6}, ctx))
        self.assertTrue(evaluate(
            {"type": "date", "in": [{"month": 6}, {"day": 3}]}, ctx
        ))

    def test_groups(self):
        ctx = make_ctx()
        cond = {"all": [
            {"type": "attr", "key": "affection", "op": ">=", "value": 30},
            {"type": "period", "in": ["night"]},
        ]}
        self.assertTrue(evaluate(cond, ctx))
        self.assertTrue(evaluate({"any": [
            {"type": "attr", "key": "affection", "op": ">", "value": 99},
            {"type": "period", "in": ["night"]},
        ]}, ctx))
        self.assertFalse(evaluate({"any": [
            {"type": "attr", "key": "affection", "op": ">", "value": 99},
        ]}, ctx))
        self.assertTrue(evaluate({"not": {"type": "period", "in": ["noon"]}}, ctx))
        self.assertTrue(evaluate({}, ctx))
        self.assertTrue(evaluate(None, ctx))

    def test_since_event(self):
        ctx = make_ctx()
        self.assertTrue(evaluate(
            {"type": "since_event", "key": "story_done", "op": ">=", "value": 1000}, ctx
        ))
        self.assertFalse(evaluate(
            {"type": "since_event", "key": "story_done", "op": "<", "value": 1000}, ctx
        ))
        self.assertTrue(evaluate(
            {"type": "since_event", "key": "never", "op": ">=", "value": 1000}, ctx
        ))

    def test_chance(self):
        ctx = make_ctx()
        cond = {"chance": 0.5}
        self.assertTrue(evaluate(cond, ctx, rng=FixedRng(0.4)))
        self.assertFalse(evaluate(cond, ctx, rng=FixedRng(0.6)))
        self.assertFalse(evaluate({"chance": 0}, ctx, rng=FixedRng(0.0)))
        self.assertTrue(evaluate({"chance": 1}, ctx, rng=FixedRng(0.99)))
        # 固定事件不参与概率：allow_chance=False 时忽略 chance
        self.assertTrue(evaluate(cond, ctx, rng=FixedRng(0.99), allow_chance=False))

    def test_skip_types(self):
        ctx = make_ctx()
        cond = {"all": [
            {"type": "period", "in": ["morning"]},
            {"type": "attr", "key": "affection", "op": ">=", "value": 30},
        ]}
        self.assertFalse(evaluate(cond, ctx))
        self.assertTrue(evaluate(cond, ctx, skip_types={"period"}))

    def test_roll_chance(self):
        self.assertTrue(roll_chance({}, FixedRng(0.99)))
        self.assertTrue(roll_chance({"chance": 0.5}, FixedRng(0.4)))
        self.assertFalse(roll_chance({"chance": 0.5}, FixedRng(0.6)))
        self.assertFalse(roll_chance({"chance": 0}, FixedRng(0.0)))


class AvailabilityTest(unittest.TestCase):
    def test_disabled(self):
        event = make_event(enabled=False)
        ok, reason = availability(
            event, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "disabled")

    def test_once_used(self):
        event = make_event(once=True)
        ok, reason = availability(
            event, make_ctx(), triggered=True, minutes_since=None
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "used")

    def test_cooldown(self):
        event = make_event(cooldown_minutes=2880)
        ok, reason = availability(
            event, make_ctx(), triggered=True, minutes_since=100
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "cooldown")
        ok, reason = availability(
            event, make_ctx(), triggered=True, minutes_since=3000
        )
        self.assertTrue(ok, reason)

    def test_condition_locked(self):
        event = make_event(trigger={"type": "attr", "key": "trust", "op": ">=", "value": 99})
        ok, reason = availability(
            event, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "locked")

    def test_ok(self):
        event = make_event(trigger={"type": "period", "in": ["night"]})
        ok, reason = availability(
            event, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_chance_ignored_by_default(self):
        event = make_event(trigger={"chance": 0.5})
        ok, _ = availability(
            event, make_ctx(), triggered=False, minutes_since=None, rng=FixedRng(0.99)
        )
        self.assertTrue(ok)


class CostTest(unittest.TestCase):
    def test_cost_money(self):
        values = {"money": 100.0}
        self.assertTrue(check_cost(values, {"money": 80})[0])
        ok, reason = check_cost(values, {"money": 120})
        self.assertFalse(ok)
        self.assertEqual(reason, "insufficient_money")
        self.assertTrue(check_cost(values, {})[0])
        self.assertTrue(check_cost(values, None)[0])


class MoodLabelTest(unittest.TestCase):
    """心情短语的有效期判定。"""

    def test_missing_and_empty(self):
        self.assertEqual(mood_label_of({}, 1000), "")
        self.assertEqual(mood_label_of({"mood_label": "  "}, 1000), "")

    def test_fresh_and_expired(self):
        ttl = MOOD_LABEL_TTL_HOURS * 60
        flags = {"mood_label": "开心", "mood_label_at": 1000}
        self.assertEqual(mood_label_of(flags, 1000 + ttl), "开心")
        self.assertEqual(mood_label_of(flags, 1000 + ttl + 1), "")

    def test_legacy_without_timestamp_expires(self):
        self.assertEqual(mood_label_of({"mood_label": "开心"}, 1000), "")


class SeedBalanceTest(unittest.TestCase):
    """种子中的经济数值与 config 定稿参数保持一致，防止两处漂移。"""

    @classmethod
    def setUpClass(cls):
        path = SEEDS_DIR / "events.json"
        with open(path, encoding="utf-8") as f:
            cls.events = {item["key"]: item for item in json.load(f)}

    def test_work_values(self):
        event = self.events["work_convenience"]
        self.assertEqual(event["cost"]["time_minutes"], WORK_HOURS * 60)
        self.assertEqual(event["effects"]["attrs"]["money"], WORK_PAY)

    def test_gift_tiers(self):
        small = self.events["gift_small"]
        large = self.events["gift_large"]
        self.assertEqual(small["cost"]["money"], GIFT_TIERS["small"]["price"])
        self.assertEqual(
            small["effects"]["attrs"]["affection"], GIFT_TIERS["small"]["affection"]
        )
        self.assertEqual(large["cost"]["money"], GIFT_TIERS["large"]["price"])
        self.assertEqual(
            large["effects"]["attrs"]["affection"], GIFT_TIERS["large"]["affection"]
        )


if __name__ == "__main__":
    unittest.main()
