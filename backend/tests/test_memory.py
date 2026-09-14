"""记忆系统纯函数层单元测试：总结解析、去重合并、检索排序、时间线与注入块。"""
import unittest
from datetime import datetime
from types import SimpleNamespace

from game import memory
from game.prompt import _memory_block


class ParseSummaryTest(unittest.TestCase):
    def test_plain_array(self):
        entries = memory.parse_summary(
            '[{"kind":"event","content":"她学会了做饭。","importance":4}]'
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "event")
        self.assertEqual(entries[0]["importance"], 4)

    def test_code_fence(self):
        raw = '```json\n[{"kind":"promise","content":"约定一起看海。","importance":7}]\n```'
        entries = memory.parse_summary(raw)
        self.assertEqual(entries[0]["kind"], "promise")

    def test_text_around(self):
        raw = '整理结果如下：[{"kind":"fact","content":"她19岁。","importance":5}] 完毕'
        entries = memory.parse_summary(raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content"], "她19岁。")

    def test_invalid_kind_and_importance(self):
        entries = memory.parse_summary(
            '[{"kind":"misc","content":"x","importance":99},'
            '{"kind":"fact","content":"y","importance":"3"}]'
        )
        self.assertEqual(entries[0]["kind"], "fact")
        self.assertEqual(entries[0]["importance"], 10)
        self.assertEqual(entries[1]["importance"], 3)

    def test_skip_invalid_items(self):
        entries = memory.parse_summary('[null, {"content":""}, {"content":"ok"}]')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content"], "ok")

    def test_empty_and_invalid(self):
        self.assertIsNone(memory.parse_summary(""))
        self.assertIsNone(memory.parse_summary("没有内容"))
        self.assertIsNone(memory.parse_summary('{"a":1}'))
        self.assertEqual(memory.parse_summary("[]"), [])

    def test_truncate_long_content(self):
        long_text = "长" * 500
        entries = memory.parse_summary('[{"content":"' + long_text + '"}]')
        self.assertEqual(len(entries[0]["content"]), 300)


class MergeEntriesTest(unittest.TestCase):
    def test_dedupe_existing_and_inner(self):
        entries = [
            {"kind": "fact", "content": "A", "importance": 5},
            {"kind": "fact", "content": "B", "importance": 5},
            {"kind": "fact", "content": "A", "importance": 5},
        ]
        new, skipped = memory.merge_entries(entries, {"B"})
        self.assertEqual([e["content"] for e in new], ["A"])
        self.assertEqual(skipped, 2)

    def test_empty(self):
        new, skipped = memory.merge_entries(None, None)
        self.assertEqual(new, [])
        self.assertEqual(skipped, 0)


class ScoreTest(unittest.TestCase):
    def test_recency_boost(self):
        fresh = memory.memory_score(5, 0)
        old = memory.memory_score(5, 24 * 365)
        self.assertGreater(fresh, old)
        self.assertAlmostEqual(old, 5.0, places=1)

    def test_importance(self):
        self.assertGreater(memory.memory_score(8, 1000), memory.memory_score(4, 1000))


class SelectMemoriesTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, 12, 0, 0)

    def test_core_reserved_over_budget(self):
        items = [
            {"id": 1, "kind": "relationship", "content": "核心" * 20,
             "importance": 3, "created_at": self.now},
            {"id": 2, "kind": "fact", "content": "普通", "importance": 2,
             "created_at": self.now},
        ]
        selected = memory.select_memories(items, budget=60, now=self.now)
        ids = [x["id"] for x in selected]
        self.assertIn(1, ids)
        self.assertNotIn(2, ids)

    def test_budget_fill(self):
        items = [
            {"id": i, "kind": "event", "content": "x" * 10, "importance": 5,
             "created_at": self.now}
            for i in range(10)
        ]
        selected = memory.select_memories(items, budget=100, now=self.now)
        self.assertGreater(len(selected), 0)
        self.assertLess(len(selected), 10)

    def test_skip_empty_content(self):
        items = [{"id": 1, "kind": "fact", "content": "  ", "importance": 9,
                  "created_at": self.now}]
        self.assertEqual(memory.select_memories(items, now=self.now), [])


class TimelineTest(unittest.TestCase):
    @staticmethod
    def message(mid, role, content, at):
        return SimpleNamespace(id=mid, role=role, content=content, game_minutes_at=at)

    @staticmethod
    def log(lid, name, content, at):
        return SimpleNamespace(
            id=lid, meta={"name": name}, content=content, game_minutes_at=at
        )

    def test_order_and_labels(self):
        lines = memory.timeline_lines(
            [self.message(2, "assistant", "你好", 20), self.message(1, "user", "嗨", 10)],
            [self.log(9, "楼下的猫", "猫蹭了她的手", 30)],
        )
        self.assertEqual(lines[0], "[玩家] 嗨")
        self.assertEqual(lines[1], "[角色] 你好")
        self.assertIn("楼下的猫", lines[2])

    def test_clip_keeps_recent(self):
        lines = ["a" * 10, "b" * 10, "c" * 10]
        kept = memory.clip_lines(lines, budget=25)
        self.assertEqual(kept, ["b" * 10, "c" * 10])

    def test_clip_small_budget(self):
        self.assertEqual(memory.clip_lines(["x" * 100], budget=10), [])


class SummaryMessagesTest(unittest.TestCase):
    def test_includes_existing_and_timeline(self):
        save = SimpleNamespace()
        messages = [
            SimpleNamespace(id=1, role="user", content="今天下雨", game_minutes_at=5)
        ]
        logs = [
            SimpleNamespace(
                id=1, meta={"name": "午后的雨"}, content="下雨了", game_minutes_at=6
            )
        ]
        existing = [SimpleNamespace(kind="fact", content="她怕黑。")]
        out = memory.build_summary_messages(save, messages, logs, existing)
        self.assertEqual(out[0]["role"], "system")
        self.assertIn("JSON", out[0]["content"])
        self.assertIn("已有记忆", out[1]["content"])
        self.assertIn("她怕黑", out[1]["content"])
        self.assertIn("[玩家] 今天下雨", out[1]["content"])


class MemoryBlockTest(unittest.TestCase):
    def test_block(self):
        text = _memory_block([
            {"kind": "relationship", "content": "她开始依赖玩家。", "importance": 8},
            {"kind": "fact", "content": "她怕黑。", "importance": 4},
        ])
        self.assertIn("# 长期记忆", text)
        self.assertIn("[关系] 她开始依赖玩家。", text)
        self.assertIn("[事实] 她怕黑。", text)

    def test_empty(self):
        self.assertEqual(_memory_block([]), "")
        self.assertEqual(_memory_block([{"content": ""}]), "")


if __name__ == "__main__":
    unittest.main()
