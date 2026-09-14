"""数据库集成测试：结算流水线、场景生命周期、记忆任务与接口兜底路径。

依赖 MySQL 与 MYSQL_PASSWORD（与现有测试一致），使用独立的 <库名>_test 数据库，
不会影响正式数据；测试结束自动删除该库。
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock
from urllib.parse import quote_plus

import pymysql
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import routes.advance as advance_route
import routes.chat as chat_route
import routes.events as events_route
import routes.scenes as scenes_route
import routes.state as state_route
from config import (
    MYSQL_CHARSET,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)
from db import Base
from game import clock, events, memory, scenes
from helpers import load_attr_values
from orm import (
    AttributeDef,
    AttributeValue,
    CatalogModel,
    Character,
    EventDef,
    EventLog,
    Memory,
    MemoryJob,
    Message,
    Provider,
    Save,
    SceneDef,
    SceneLog,
)
from schemas import AdvanceIn, SceneEndIn, SceneEnterIn

TEST_DATABASE = f"{MYSQL_DATABASE}_test"


def _make_engine(database: str):
    url = (
        f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{database}?charset={MYSQL_CHARSET}"
    )
    return create_engine(url, pool_pre_ping=True)


def _create_test_database() -> None:
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset=MYSQL_CHARSET,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{TEST_DATABASE}` "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def _drop_test_database() -> None:
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset=MYSQL_CHARSET,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{TEST_DATABASE}`")
        conn.commit()
    finally:
        conn.close()


class SettlementIntegrationTest(unittest.TestCase):
    """服务层与路由层结算逻辑的数据库级验证。"""

    @classmethod
    def setUpClass(cls):
        _create_test_database()
        cls.engine = _make_engine(TEST_DATABASE)
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(
            bind=cls.engine, autoflush=False, expire_on_commit=False
        )
        cls._original_factories = {
            memory: memory.SessionLocal,
            chat_route: chat_route.SessionLocal,
        }
        memory.SessionLocal = cls.Session
        chat_route.SessionLocal = cls.Session

    @classmethod
    def tearDownClass(cls):
        for module, factory in cls._original_factories.items():
            module.SessionLocal = factory
        cls.engine.dispose()
        _drop_test_database()

    def setUp(self):
        self.sessions: list = []
        session = self._session()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()

    def tearDown(self):
        for session in self.sessions:
            session.close()

    # ── 辅助 ──

    def _session(self):
        session = self.Session()
        self.sessions.append(session)
        return session

    @staticmethod
    def _defs(session) -> list[AttributeDef]:
        defs = [
            AttributeDef(
                key="affection", name="好感度", category="stat", min=0, max=100,
                default_value=10, ai_editable=True, enabled=True, sort=10,
            ),
            AttributeDef(
                key="trust", name="信任", category="stat", min=0, max=100,
                default_value=10, ai_editable=True, enabled=True, sort=20,
            ),
            AttributeDef(
                key="mood", name="心情", category="stat", min=0, max=100,
                default_value=60,
                tick_rule={"mode": "regress", "target": 50, "rate_per_hour": 0.5},
                ai_editable=True, enabled=True, sort=30,
            ),
            AttributeDef(
                key="vigilance", name="警戒", category="stat", min=0, max=100,
                default_value=30,
                tick_rule={"mode": "decay", "amount_per_hour": 1},
                ai_editable=True, enabled=True, sort=40,
            ),
            AttributeDef(
                key="dependence", name="依赖", category="stat", min=0, max=100,
                default_value=0, ai_editable=True, enabled=True, sort=45,
            ),
            AttributeDef(
                key="money", name="金钱", category="resource", min=0, max=10**9,
                default_value=2000, ai_editable=False, enabled=True, sort=50,
            ),
        ]
        for item in defs:
            session.add(item)
        session.flush()
        return defs

    def _save(self, session, defs, model_key: str = ""):
        character = Character(
            name="测试角色", age=19, relation="测试", persona={}, freeform=""
        )
        session.add(character)
        session.flush()
        save = Save(
            character_id=character.id,
            name="测试档",
            model_key=model_key,
            settings={},
            game_minutes=0,
            last_summarized_message_id=0,
        )
        session.add(save)
        session.flush()
        for item in defs:
            session.add(
                AttributeValue(
                    save_id=save.id, attr_key=item.key, value=item.default_value
                )
            )
        session.commit()
        return save, {item.key: item.default_value for item in defs}

    def _add_messages(self, session, save_id: int, count: int) -> None:
        for index in range(count):
            session.add(
                Message(
                    save_id=save_id,
                    role="user",
                    content=f"消息{index}",
                    game_minutes_at=0,
                )
            )
        session.flush()

    def _add_provider(self, session):
        provider = Provider(
            slug="testprov",
            display_name="测试供应商",
            base_url="http://127.0.0.1:1/v1",
            api_key="sk-test",
            use_env_key=False,
            api_key_env="",
            sort_order=1,
        )
        session.add(provider)
        session.flush()
        session.add_all([
            CatalogModel(provider_id=provider.id, model_id="model-a", display_name="A"),
            CatalogModel(provider_id=provider.id, model_id="model-b", display_name="B"),
        ])
        session.flush()
        return provider

    # ── 结算 ──

    def test_advance_settles_ticks_and_fixed_event(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        session.add(
            EventDef(
                key="fixed_once", name="固定事件", category="fixed", trigger={},
                effects={"attrs": {"trust": 2}}, prompt_template="事件内容",
                once=True, cooldown_minutes=0, priority=10, enabled=True,
            )
        )
        session.commit()

        settled = events.settle_time(
            session, save, defs, values, 60, source="advance"
        )
        session.commit()

        self.assertEqual(save.game_minutes, 60)
        self.assertEqual(values["trust"], 12.0)
        self.assertAlmostEqual(values["vigilance"], 29.0)
        self.assertEqual([item["key"] for item in settled["triggered"]], ["fixed_once"])
        log = session.scalar(select(EventLog).where(EventLog.save_id == save.id))
        self.assertIsNotNone(log)
        self.assertEqual(log.game_minutes_at, clock.absolute_minutes(60, {}))
        ordered_keys = [item["key"] for item in settled["ordered_changes"]]
        self.assertIn("trust", ordered_keys)
        self.assertIn("vigilance", ordered_keys)
        self.assertLess(ordered_keys.index("vigilance"), ordered_keys.index("trust"))

    def test_cross_day_random_roll_and_inject(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        session.add(
            EventDef(
                key="rand_evt", name="随机事件", category="random",
                trigger={
                    "all": [{"type": "period", "in": ["morning"]}],
                    "chance": 1.0,
                },
                effects={"attrs": {"mood": 3}}, prompt_template="随机内容",
                once=False, cooldown_minutes=0, priority=10, enabled=True,
            )
        )
        session.commit()

        settled = events.settle_time(
            session, save, defs, values, clock.DAY_MINUTES, source="advance"
        )
        session.commit()

        split = clock.split(clock.absolute_minutes(save.game_minutes, {}))
        self.assertEqual(split["day"], 2)
        self.assertEqual([item["key"] for item in settled["triggered"]], ["rand_evt"])
        rolls = events.load_flags(session, save.id).get("random_rolls") or {}
        self.assertIn("rand_evt", rolls)
        self.assertTrue(rolls["rand_evt"]["hit"])

    # ── 场景 ──

    def test_scene_lifecycle_records_turns_and_does_not_relay(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        session.add_all([
            SceneDef(
                key="scene_a", name="场景A", category="story", enter_trigger={},
                enter_cost={}, scene_prompt="设定A", goal="目标A", min_turns=2,
                max_turns=5, exit={}, effects={"attrs": {"affection": 5}},
                next_scenes=[], once=True, cooldown_minutes=0, priority=50,
                enabled=True,
            ),
            SceneDef(
                key="scene_b", name="场景B", category="story", enter_trigger={},
                enter_cost={}, scene_prompt="设定B", goal="目标B", min_turns=1,
                max_turns=3, exit={}, effects={}, next_scenes=[], once=False,
                cooldown_minutes=0, priority=40, enabled=True,
            ),
        ])
        session.commit()

        events.settle_time(session, save, defs, values, 10, source="chat")
        session.commit()
        self.assertEqual(scenes.get_active(session, save.id)["key"], "scene_a")

        events.settle_time(session, save, defs, values, 20, source="chat")
        session.commit()
        self.assertEqual(scenes.get_active(session, save.id)["turns"], 1)

        settled = events.settle_time(
            session, save, defs, values, 30, source="chat",
            state_scene={"action": "end", "summary": "这一幕结束"},
        )
        session.commit()

        self.assertIsNone(scenes.get_active(session, save.id))
        ended = settled["scene"]["ended"]
        self.assertEqual(ended["key"], "scene_a")
        self.assertEqual(ended["reason"], "ai")
        self.assertEqual(ended["turns"], 2)
        log = session.scalar(
            select(SceneLog).where(
                SceneLog.save_id == save.id,
                SceneLog.scene_key == "scene_a",
                SceneLog.status == "finished",
            )
        )
        self.assertEqual(log.meta["turns"], 2)
        self.assertIsNotNone(
            session.scalar(select(Memory).where(Memory.save_id == save.id))
        )
        self.assertEqual(values["affection"], 15.0)
        self.assertIsNone(
            session.scalar(
                select(SceneLog).where(
                    SceneLog.save_id == save.id,
                    SceneLog.scene_key == "scene_b",
                    SceneLog.status == "started",
                )
            )
        )

        events.settle_time(session, save, defs, values, 40, source="chat")
        session.commit()
        self.assertEqual(scenes.get_active(session, save.id)["key"], "scene_b")

    def test_manual_scene_end_defers_relay(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        session.add_all([
            SceneDef(
                key="scene_a", name="场景A", category="story", enter_trigger={},
                enter_cost={}, scene_prompt="设定A", goal="目标A", min_turns=1,
                max_turns=5, exit={},
                effects={"attrs": {"trust": 1}, "advance_minutes": 30},
                next_scenes=[], once=False, cooldown_minutes=10080, priority=50,
                enabled=True,
            ),
            SceneDef(
                key="scene_b", name="场景B", category="story", enter_trigger={},
                enter_cost={}, scene_prompt="设定B", goal="目标B", min_turns=1,
                max_turns=3, exit={}, effects={}, next_scenes=[], once=False,
                cooldown_minutes=0, priority=40, enabled=True,
            ),
        ])
        session.commit()
        save_id = save.id

        entered = scenes_route.enter_scene(
            save_id, SceneEnterIn(key="scene_a"), session=session
        )
        self.assertEqual(entered["active"]["key"], "scene_a")

        ended = scenes_route.end_scene(
            save_id, SceneEndIn(summary="手动收尾"), session=session
        )
        self.assertIsNone(ended["active"])
        self.assertIsNone(
            session.scalar(
                select(SceneLog).where(
                    SceneLog.save_id == save_id,
                    SceneLog.scene_key == "scene_b",
                    SceneLog.status == "started",
                )
            )
        )
        self.assertTrue(
            any(
                item["role"] == "system" and "时间推进到了" in item["content"]
                for item in ended["messages"]
            )
        )

        events.settle_time(
            session, save, defs, values, save.game_minutes + 10, source="manual"
        )
        session.commit()
        self.assertEqual(scenes.get_active(session, save.id)["key"], "scene_b")

    def test_advance_route_writes_time_note(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)

        data = advance_route.advance(save.id, AdvanceIn(minutes=30), session=session)

        self.assertEqual(data["advance_minutes"], 30)
        notes = [
            item
            for item in data["messages"]
            if item["role"] == "system" and "时间推进到了" in item["content"]
        ]
        self.assertEqual(len(notes), 1)
        reloaded = load_attr_values(session, save.id)
        self.assertAlmostEqual(reloaded["vigilance"], 29.5)
        self.assertAlmostEqual(reloaded["mood"], 59.75)

    # ── M5 行动与经济 ──

    def test_work_action_and_wallet(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        session.add(
            EventDef(
                key="work_x", name="便利店打工", category="work", trigger={},
                cost={"time_minutes": 240}, effects={"attrs": {"money": 120}},
                prompt_template="打了四个小时的工。", once=False,
                cooldown_minutes=0, priority=15, enabled=True,
            )
        )
        session.commit()
        save_id = save.id

        data = events_route.trigger_manual(save_id, "work_x", session=session)

        self.assertEqual(data["advance_minutes"], 240)
        self.assertEqual(data["changes"][0]["key"], "money")
        session.commit()
        self.assertEqual(load_attr_values(session, save_id)["money"], 2120.0)
        state = state_route.get_state(save_id, session=session)
        self.assertEqual(state["money"], 2120.0)
        self.assertEqual([item["key"] for item in state["work_actions"]], ["work_x"])
        self.assertEqual(state["manual_events"], [])
        self.assertEqual(state["wallet_flows"][0]["amount"], 120.0)

    def test_gift_action_and_event_chain(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        session.add_all([
            EventDef(
                key="gift_x", name="大礼物", category="manual", trigger={},
                cost={"money": 300, "time_minutes": 30},
                effects={"attrs": {"affection": 5}, "flags": {"gift_given": True}},
                prompt_template="她收下了礼物。", once=False,
                cooldown_minutes=0, priority=28, enabled=True,
            ),
            EventDef(
                key="gift_follow", name="她的回应", category="fixed",
                trigger={"all": [{"type": "flag", "key": "gift_given", "value": True}]},
                effects={"attrs": {"dependence": 2}},
                prompt_template="第二天她偷偷收好了礼物。", once=True,
                cooldown_minutes=0, priority=52, enabled=True,
            ),
        ])
        session.commit()
        save_id = save.id

        events_route.trigger_manual(save_id, "gift_x", session=session)

        session.commit()
        values = load_attr_values(session, save_id)
        self.assertEqual(values["money"], 1700.0)
        self.assertEqual(values["affection"], 15.0)
        self.assertEqual(values["dependence"], 2.0)
        self.assertTrue(events.load_flags(session, save_id).get("gift_given"))
        chain = session.scalar(
            select(EventLog)
            .where(EventLog.save_id == save_id)
            .order_by(EventLog.id.desc())
        )
        self.assertEqual((chain.meta or {}).get("key"), "gift_follow")
        flow = state_route.get_state(save_id, session=session)["wallet_flows"][0]
        self.assertEqual(flow["amount"], -300.0)

    def test_neglect_penalty_is_incremental_and_capped(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        save_id = save.id

        data = None
        for _ in range(3):
            data = advance_route.advance(
                save_id, AdvanceIn(minutes=1440), session=session
            )
        self.assertEqual(data["changes"][-1]["source"], "neglect")
        self.assertEqual(load_attr_values(session, save_id)["affection"], 9.0)

        for _ in range(5):
            advance_route.advance(save_id, AdvanceIn(minutes=1440), session=session)
        self.assertEqual(load_attr_values(session, save_id)["affection"], 5.0)
        neglect = events.load_flags(session, save_id).get("neglect") or {}
        self.assertEqual(neglect.get("applied_days"), 5)

    def test_chat_applies_ai_flags_and_mood_label(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        save_id = save.id

        tag = (
            '{"attrs": {"affection": 1},'
            ' "flags": {"noted_scar": true, "active_scene": true, "scene_x": 1},'
            ' "mood_label": "开心"}'
        )
        result = chat_route._settle(save_id, "她笑了笑。", tag, False)
        self.assertEqual(result["mood_label"], "开心")

        session.rollback()
        flags = events.load_flags(session, save_id)
        self.assertTrue(flags.get("noted_scar"))
        self.assertNotIn("active_scene", flags)
        self.assertNotIn("scene_x", flags)
        self.assertEqual(flags.get("mood_label"), "开心")
        self.assertEqual(
            state_route.get_state(save_id, session=session)["mood_label"], "开心"
        )

    def test_proactive_event_on_advance(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        session.add(
            EventDef(
                key="proactive_x", name="她的晚间消息", category="fixed",
                trigger={"all": [
                    {"type": "period", "in": ["night"]},
                    {"type": "hour", "op": ">=", "value": 19},
                ]},
                effects={"attrs": {"mood": 2}}, prompt_template="手机亮了一下。",
                once=False, cooldown_minutes=0, priority=38, enabled=True,
            )
        )
        session.commit()

        data = advance_route.advance(
            save.id, AdvanceIn(minutes=660), session=session
        )

        self.assertEqual([item["key"] for item in data["events"]], ["proactive_x"])
        self.assertTrue(
            any("手机亮了一下" in item["content"] for item in data["messages"])
        )

    # ── 对话结算与记忆 ──

    def test_chat_settle_pipeline(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        save_id = save.id

        result = chat_route._settle(
            save_id,
            "回复文本",
            '{"attrs": {"affection": 3}, "time": {"advance_minutes": 30}}',
            False,
        )
        self.assertTrue(result["parsed"])
        self.assertEqual(result["time_advance"], 30)
        self.assertEqual(result["game_minutes"], 30)
        session.expire_all()
        assistant = session.scalar(
            select(Message).where(
                Message.save_id == save_id, Message.role == "assistant"
            )
        )
        self.assertEqual(assistant.content, "回复文本")
        self.assertEqual(assistant.meta["attrs"][0]["key"], "affection")
        self.assertAlmostEqual(load_attr_values(session, save_id)["affection"], 13.0)

        fallback = chat_route._settle(save_id, "第二条", None, False)
        self.assertFalse(fallback["parsed"])
        self.assertEqual(fallback["time_advance"], 10)
        self.assertEqual(fallback["game_minutes"], 40)
        session.rollback()
        latest = session.scalar(
            select(Message)
            .where(Message.save_id == save_id, Message.role == "assistant")
            .order_by(Message.id.desc())
        )
        self.assertTrue(latest.meta.get("state_parse_failed"))

    def test_memory_summary_pipeline(self):
        session = self._session()
        defs = self._defs(session)
        self._add_provider(session)
        save, _values = self._save(session, defs, model_key="testprov:model-a")
        save_id = save.id
        self._add_messages(session, save_id, 20)
        session.commit()

        self.assertTrue(memory.trigger_if_due(session, save_id))
        self.assertFalse(memory.trigger_if_due(session, save_id))

        prepared = memory._prepare_summary(save_id)
        self.assertIsNotNone(prepared)
        self.assertEqual(prepared["model_id"], "model-a")
        applied = memory._apply_summary(
            prepared,
            '[{"kind": "event", "content": "她第一次笑了。", "importance": 6}]',
        )
        self.assertEqual(len(applied["added"]), 1)
        session.rollback()
        self.assertEqual(memory.count_unsummarized(session, save_id), 0)
        row = session.scalar(select(Memory).where(Memory.save_id == save_id))
        self.assertEqual(row.content, "她第一次笑了。")

        session.get(Save, save_id).settings = {"memory_model": "testprov:model-b"}
        self._add_messages(session, save_id, 20)
        session.commit()
        memory.trigger_if_due(session, save_id)
        prepared_b = memory._prepare_summary(save_id)
        self.assertIsNotNone(prepared_b)
        self.assertEqual(prepared_b["model_id"], "model-b")
        memory._apply_summary(prepared_b, "[]")

    def test_memory_summary_unexpected_failure_marks_job(self):
        session = self._session()
        defs = self._defs(session)
        self._add_provider(session)
        save, _values = self._save(session, defs, model_key="testprov:model-a")
        self._add_messages(session, save.id, 20)
        session.commit()

        with mock.patch.object(
            memory.ai, "complete", new=mock.AsyncMock(side_effect=RuntimeError("boom"))
        ):
            result = asyncio.run(memory.run_summary(save.id))

        self.assertIsNone(result)
        session.expire_all()
        job = session.scalar(
            select(MemoryJob)
            .where(MemoryJob.save_id == save.id)
            .order_by(MemoryJob.id.desc())
        )
        self.assertEqual(job.status, "failed")
        self.assertIn("boom", job.error)


class ErrorFormatTest(unittest.TestCase):
    def test_validation_error_handler_shape(self):
        import main as main_module
        from fastapi.exceptions import RequestValidationError

        from schemas import SaveCreate

        try:
            SaveCreate(name="   ")
        except ValidationError as exc:
            request_error = RequestValidationError(exc.errors())

        response = asyncio.run(
            main_module.validation_exception_handler(None, request_error)
        )
        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(payload["code"], "validation_error")
        self.assertTrue(payload["message"])


if __name__ == "__main__":
    unittest.main()
