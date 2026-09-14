"""场景引擎纯函数层单元测试：进入可用性、轮数边界、场景块与记忆内容。"""
import unittest

from game.events import EvalContext
from game.scenes import (
    brief,
    memory_content,
    public_active,
    scene_availability,
    scene_block,
    should_finish,
)
from orm import SceneDef


def make_scene(**overrides):
    fields = {
        "key": "test_scene",
        "name": "测试场景",
        "category": "story",
        "enter_trigger": {},
        "enter_cost": {},
        "scene_prompt": "",
        "goal": "",
        "min_turns": 3,
        "max_turns": 12,
        "exit": {},
        "effects": {},
        "next_scenes": [],
        "once": False,
        "cooldown_minutes": 0,
        "priority": 0,
        "enabled": True,
    }
    fields.update(overrides)
    return SceneDef(**fields)


def make_ctx(**overrides):
    fields = {
        "attrs": {"affection": 30.0, "trust": 20.0, "money": 100.0},
        "flags": {},
        "game_day": 3,
        "month": 5,
        "day": 3,
        "hour": 20,
        "minute": 30,
        "period": "night",
        "absolute": 173280 + 2 * 1440 + 20 * 60 + 30,
        "minutes_since": {},
    }
    fields.update(overrides)
    return EvalContext(**fields)


class SceneAvailabilityTest(unittest.TestCase):
    def test_disabled(self):
        scene = make_scene(enabled=False)
        ok, reason = scene_availability(
            scene, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "disabled")

    def test_once_used(self):
        scene = make_scene(once=True)
        ok, reason = scene_availability(
            scene, make_ctx(), triggered=True, minutes_since=None
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "used")

    def test_cooldown(self):
        scene = make_scene(cooldown_minutes=2880)
        ok, reason = scene_availability(
            scene, make_ctx(), triggered=True, minutes_since=100
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "cooldown")
        ok, _ = scene_availability(
            scene, make_ctx(), triggered=True, minutes_since=3000
        )
        self.assertTrue(ok)

    def test_condition_locked(self):
        scene = make_scene(
            enter_trigger={"type": "attr", "key": "trust", "op": ">=", "value": 99}
        )
        ok, reason = scene_availability(
            scene, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "locked")

    def test_flag_condition(self):
        scene = make_scene(
            enter_trigger={
                "type": "flag", "key": "scene_unlocked:care_fever"
            }
        )
        ctx = make_ctx(flags={"scene_unlocked:care_fever": True})
        ok, reason = scene_availability(
            scene, ctx, triggered=False, minutes_since=None
        )
        self.assertTrue(ok, reason)
        ok, _ = scene_availability(
            scene, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertFalse(ok)

    def test_ok(self):
        scene = make_scene(
            enter_trigger={"type": "period", "in": ["night"]}
        )
        ok, reason = scene_availability(
            scene, make_ctx(), triggered=False, minutes_since=None
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


class ShouldFinishTest(unittest.TestCase):
    def test_ai_end_rejected_within_min_turns(self):
        scene = make_scene(min_turns=3, max_turns=12)
        self.assertIsNone(should_finish(scene, 2, ai_end=True, exit_met=False))
        self.assertEqual(
            should_finish(scene, 3, ai_end=True, exit_met=False), "ai"
        )

    def test_exit_condition(self):
        scene = make_scene(min_turns=3, max_turns=12)
        self.assertEqual(
            should_finish(scene, 1, ai_end=False, exit_met=True), "exit"
        )
        self.assertIsNone(should_finish(scene, 5, ai_end=False, exit_met=False))

    def test_max_turns_forced(self):
        scene = make_scene(min_turns=3, max_turns=4)
        self.assertIsNone(should_finish(scene, 4, ai_end=False, exit_met=False))
        self.assertEqual(
            should_finish(scene, 5, ai_end=False, exit_met=False), "max_turns"
        )

    def test_ai_end_takes_priority_over_max(self):
        scene = make_scene(min_turns=3, max_turns=4)
        self.assertEqual(
            should_finish(scene, 5, ai_end=True, exit_met=False), "ai"
        )

    def test_zero_min_turns(self):
        scene = make_scene(min_turns=0, max_turns=12)
        self.assertEqual(
            should_finish(scene, 1, ai_end=True, exit_met=False), "ai"
        )


class SceneBlockTest(unittest.TestCase):
    def make_active(self, **overrides):
        active = {
            "key": "talk_rainy_night",
            "name": "雨夜谈心",
            "goal": "说出心里话",
            "prompt": "夜里下雨。",
            "turns": 2,
            "min_turns": 3,
            "max_turns": 12,
        }
        active.update(overrides)
        return active

    def test_block_content(self):
        text = scene_block(self.make_active())
        self.assertIn("雨夜谈心", text)
        self.assertIn("说出心里话", text)
        self.assertIn("第 3 轮", text)
        self.assertNotIn('"action":"end"', text)

    def test_finale_instruction_at_max(self):
        text = scene_block(self.make_active(turns=12))
        self.assertIn("收尾", text)
        self.assertIn('"action":"end"', text)

    def test_prompt_budget(self):
        text = scene_block(self.make_active(prompt="很长" * 1000))
        self.assertIn("…", text)
        self.assertLess(text.count("很长"), 1000)

    def test_missing_fields(self):
        text = scene_block({"key": "k", "turns": 0})
        self.assertIn("场景", text)
        self.assertIn("第 1 轮", text)


class MemoryContentTest(unittest.TestCase):
    def test_with_summary(self):
        scene = make_scene(name="雨夜谈心")
        self.assertEqual(
            memory_content(scene, "她说出了心事"), "【雨夜谈心】她说出了心事"
        )

    def test_fallback_goal(self):
        scene = make_scene(name="雨夜谈心", goal="说出心里话")
        text = memory_content(scene, "  ")
        self.assertIn("说出心里话", text)
        self.assertTrue(text.startswith("【雨夜谈心】"))

    def test_fallback_empty(self):
        scene = make_scene(name="雨夜谈心", goal="")
        self.assertEqual(memory_content(scene, ""), "【雨夜谈心】这一幕结束了。")


class ActiveViewTest(unittest.TestCase):
    def test_public_active_strips_prompt(self):
        active = {
            "key": "k",
            "name": "n",
            "goal": "g",
            "prompt": "场景设定原文",
            "turns": 2,
            "min_turns": 3,
            "max_turns": 12,
            "started_game_minutes": 100,
        }
        out = public_active(active)
        self.assertNotIn("prompt", out)
        self.assertEqual(out["turns"], 2)
        self.assertEqual(out["max_turns"], 12)
        self.assertIsNone(public_active(None))

    def test_brief(self):
        entry = {
            "key": "k",
            "name": "n",
            "goal": "g",
            "turns": 1,
            "reason": "ai",
            "summary": "s",
            "log_id": 5,
            "message": {"id": 1},
        }
        out = brief(entry)
        self.assertNotIn("message", out)
        self.assertEqual(out["reason"], "ai")
        self.assertIsNone(brief(None))


if __name__ == "__main__":
    unittest.main()
