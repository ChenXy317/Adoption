"""数据库集成测试：结算流水线、场景生命周期、记忆任务与接口兜底路径。

依赖 MySQL 与 MYSQL_PASSWORD（与现有测试一致），使用独立的 <库名>_test 数据库，
不会影响正式数据；测试结束自动删除该库。
"""
from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime
from unittest import mock
from urllib.parse import quote_plus

import pymysql
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.background import BackgroundTasks

import routes.advance as advance_route
import routes.backup as backup_route
import routes.chat as chat_route
import routes.defs as defs_route
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
    SaveFlag,
    SceneDef,
    SceneLog,
)
from schemas import (
    AdvanceIn,
    ChatIn,
    EventDefIn,
    EventDefPatch,
    SceneDefIn,
    SceneDefPatch,
    SceneEndIn,
    SceneEnterIn,
)
from seeds.loader import apply_event_seeds, apply_scene_seeds

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

    def test_chat_mood_label_expires_with_time(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        save_id = save.id

        chat_route._settle(save_id, "回复", '{"mood_label": "开心"}', False)
        session.rollback()
        self.assertEqual(events.load_flags(session, save_id).get("mood_label"), "开心")

        advance_route.advance(save_id, AdvanceIn(minutes=clock.DAY_MINUTES), session=session)
        self.assertEqual(
            state_route.get_state(save_id, session=session)["mood_label"], "开心"
        )

        advance_route.advance(save_id, AdvanceIn(minutes=1), session=session)
        self.assertEqual(
            state_route.get_state(save_id, session=session)["mood_label"], ""
        )

    def test_chat_rejects_blank_message(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        session.commit()

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                chat_route.chat(save.id, ChatIn(message="   "), BackgroundTasks())
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_neglect_can_be_disabled_via_settings(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        save.settings = {**(save.settings or {}), "neglect": {"days": 0}}
        session.commit()

        for _ in range(4):
            advance_route.advance(save.id, AdvanceIn(minutes=1440), session=session)

        self.assertEqual(load_attr_values(session, save.id)["affection"], 10.0)
        self.assertIsNone(events.load_flags(session, save.id).get("neglect"))

    def test_scene_def_removed_aborts_open_log(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        scene = SceneDef(
            key="gone", name="将被删除", category="story", enter_trigger={},
            enter_cost={}, scene_prompt="", goal="", min_turns=1, max_turns=3,
            exit={}, effects={}, next_scenes=[], once=False,
            cooldown_minutes=0, priority=0, enabled=True,
        )
        session.add(scene)
        session.commit()

        events.settle_time(session, save, defs, values, 10, source="chat")
        session.commit()
        self.assertEqual(scenes.get_active(session, save.id)["key"], "gone")

        session.delete(scene)
        session.commit()
        values = load_attr_values(session, save.id)
        events.settle_time(session, save, defs, values, 20, source="chat")
        session.commit()

        self.assertIsNone(scenes.get_active(session, save.id))
        log = session.scalar(select(SceneLog).where(SceneLog.scene_key == "gone"))
        self.assertEqual(log.status, "aborted")

    def test_scene_money_flows_recorded(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        session.add(
            SceneDef(
                key="paid_scene", name="付费场景", category="story",
                enter_trigger={}, enter_cost={"money": 100}, scene_prompt="",
                goal="", min_turns=0, max_turns=1, exit={},
                effects={"attrs": {"money": 30}}, next_scenes=[], once=False,
                cooldown_minutes=0, priority=0, enabled=True,
            )
        )
        session.commit()
        save_id = save.id

        events.settle_time(session, save, defs, values, 10, source="chat")
        session.commit()
        self.assertEqual(load_attr_values(session, save_id)["money"], 1900.0)

        values = load_attr_values(session, save_id)
        events.settle_time(
            session, save, defs, values, 20, source="chat",
            state_scene={"action": "end", "summary": "收尾"},
        )
        session.commit()
        self.assertEqual(load_attr_values(session, save_id)["money"], 1930.0)

        flows = state_route.get_state(save_id, session=session)["wallet_flows"]
        self.assertEqual([flow["amount"] for flow in flows[:2]], [30.0, -100.0])
        self.assertTrue(all(flow["category"] == "scene" for flow in flows[:2]))

    def test_recent_events_only_injected_once(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        session.add(
            EventLog(
                save_id=save.id, event_id=None, status="triggered",
                content="事件原文", meta={"key": "evt", "name": "事件"},
                game_minutes_at=clock.absolute_minutes(0, {}),
            )
        )
        session.commit()

        first = events.recent_events(session, save, window_minutes=180, limit=3)
        self.assertEqual([item["name"] for item in first], ["事件"])
        events.mark_events_narrated(session, [item["log_id"] for item in first])
        session.commit()

        second = events.recent_events(session, save, window_minutes=180, limit=3)
        self.assertEqual(second, [])

    def test_messages_pagination(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        save_id = save.id
        self._add_messages(session, save_id, 25)
        session.commit()

        first = state_route.list_messages(
            save_id, limit=10, before_id=None, session=session
        )
        self.assertEqual(len(first["messages"]), 10)
        self.assertTrue(first["has_more"])
        self.assertEqual(
            [m["content"] for m in first["messages"]],
            [f"消息{i}" for i in range(15, 25)],
        )

        older = state_route.list_messages(
            save_id, limit=10, before_id=first["messages"][0]["id"], session=session
        )
        self.assertEqual(
            [m["content"] for m in older["messages"]],
            [f"消息{i}" for i in range(5, 15)],
        )
        self.assertTrue(older["has_more"])

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
        self.assertIsInstance(result["tendency"], str)
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

    def test_prepare_summary_failure_marks_job_failed(self):
        session = self._session()
        defs = self._defs(session)
        self._add_provider(session)
        save, _values = self._save(session, defs, model_key="testprov:model-a")
        self._add_messages(session, save.id, 3)
        session.commit()

        with mock.patch.object(
            memory, "build_summary_messages", side_effect=RuntimeError("采集失败")
        ):
            prepared = memory._prepare_summary(save.id)

        self.assertIsNone(prepared)
        session.expire_all()
        job = session.scalar(
            select(MemoryJob)
            .where(MemoryJob.save_id == save.id)
            .order_by(MemoryJob.id.desc())
        )
        self.assertEqual(job.status, "failed")
        self.assertIn("采集失败", job.error)

    def test_scene_cooldown_starts_at_finish_time(self):
        session = self._session()
        defs = self._defs(session)
        save, values = self._save(session, defs)
        session.add(
            SceneDef(
                key="cd_scene", name="冷却场景", category="story",
                enter_trigger={}, enter_cost={}, scene_prompt="", goal="",
                min_turns=0, max_turns=5, exit={}, effects={},
                next_scenes=[], once=False, cooldown_minutes=10080,
                priority=50, enabled=True,
            )
        )
        session.commit()

        events.settle_time(session, save, defs, values, 10, source="chat")
        session.commit()
        self.assertEqual(scenes.get_active(session, save.id)["key"], "cd_scene")

        events.settle_time(
            session, save, defs, values, 10 + 2 * clock.DAY_MINUTES, source="chat"
        )
        session.commit()
        scene = session.scalar(select(SceneDef).where(SceneDef.key == "cd_scene"))
        active = scenes.get_active(session, save.id)
        ctx = events.build_context(session, save, values)
        scenes.finish_scene(
            session, save, scene, active, ctx, values, {d.key: d for d in defs},
            reason="manual",
        )
        session.commit()

        finish_abs = clock.absolute_minutes(save.game_minutes, {})
        _, last_at = scenes.load_scene_stats(session, save.id)
        self.assertEqual(last_at["cd_scene"], finish_abs)

    def test_event_seed_keeps_enabled_state(self):
        session = self._session()
        apply_event_seeds(session)
        row = session.scalar(
            select(EventDef).where(EventDef.key == "work_convenience")
        )
        self.assertIsNotNone(row)
        row.enabled = False
        session.commit()

        apply_event_seeds(session)

        session.expire_all()
        row = session.scalar(
            select(EventDef).where(EventDef.key == "work_convenience")
        )
        self.assertFalse(row.enabled)

    def test_scene_seed_keeps_enabled_state(self):
        session = self._session()
        apply_scene_seeds(session)
        row = session.scalar(
            select(SceneDef).where(SceneDef.key == "date_first_outing")
        )
        self.assertIsNotNone(row)
        row.enabled = False
        session.commit()

        apply_scene_seeds(session)

        session.expire_all()
        row = session.scalar(
            select(SceneDef).where(SceneDef.key == "date_first_outing")
        )
        self.assertFalse(row.enabled)

    def test_export_backup_roundtrip(self):
        session = self._session()
        defs = self._defs(session)
        self._add_provider(session)
        save, _values = self._save(session, defs, model_key="testprov:model-a")
        save_id = save.id
        save.game_minutes = 123
        session.add(
            EventDef(
                key="evt_x", name="事件X", category="fixed", trigger={},
                effects={}, prompt_template="内容", once=False,
                cooldown_minutes=0, priority=0, enabled=True,
            )
        )
        session.flush()
        event_id = session.scalar(select(EventDef.id).where(EventDef.key == "evt_x"))
        message_ids: list[int] = []
        for index in range(5):
            message = Message(
                save_id=save_id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"消息{index}",
                meta={},
                game_minutes_at=index,
            )
            session.add(message)
            session.flush()
            message_ids.append(message.id)
        save.last_summarized_message_id = message_ids[-1]
        session.add(SaveFlag(save_id=save_id, key="flag_a", value={"value": True}))
        session.add(
            EventLog(
                save_id=save_id, event_id=event_id, status="triggered",
                content="日志", meta={"key": "evt_x", "name": "事件X"},
                game_minutes_at=3,
            )
        )
        session.add(
            SceneLog(
                save_id=save_id, scene_key="scene_x", status="finished",
                summary="总结", meta={"name": "场景X"}, game_minutes_at=4,
                finished_at=datetime.now(),
            )
        )
        session.add(
            Memory(
                save_id=save_id, kind="event", content="记忆内容", importance=6,
                source_from_id=message_ids[0], source_to_id=message_ids[-1],
            )
        )
        session.commit()

        payload = backup_route.build_backup(session, save)
        self.assertEqual(payload["format"], backup_route.BACKUP_FORMAT)
        self.assertEqual(payload["save"]["game_minutes"], 123)
        self.assertEqual(
            [m["content"] for m in payload["messages"]],
            [f"消息{i}" for i in range(5)],
        )
        self.assertTrue(any(f["key"] == "flag_a" for f in payload["flags"]))

        response = backup_route.export_save(save_id, session=session)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertEqual(json.loads(response.body)["save"]["name"], "测试档")

        imported = backup_route.import_backup(session, payload, name="恢复档")
        session.commit()
        self.assertNotEqual(imported.id, save_id)
        self.assertEqual(imported.name, "恢复档")
        self.assertEqual(imported.model_key, "testprov:model-a")
        self.assertEqual(imported.game_minutes, 123)
        new_messages = list(
            session.scalars(
                select(Message)
                .where(Message.save_id == imported.id)
                .order_by(Message.id)
            )
        )
        self.assertEqual(
            [m.content for m in new_messages], [f"消息{i}" for i in range(5)]
        )
        self.assertEqual(imported.last_summarized_message_id, new_messages[-1].id)
        self.assertTrue(events.load_flags(session, imported.id).get("flag_a"))
        log = session.scalar(
            select(EventLog).where(EventLog.save_id == imported.id)
        )
        self.assertEqual(log.event_id, event_id)
        scene_log = session.scalar(
            select(SceneLog).where(SceneLog.save_id == imported.id)
        )
        self.assertEqual(scene_log.scene_key, "scene_x")
        memory_row = session.scalar(
            select(Memory).where(Memory.save_id == imported.id)
        )
        self.assertEqual(memory_row.content, "记忆内容")
        self.assertEqual(memory_row.source_from_id, new_messages[0].id)
        self.assertEqual(memory_row.source_to_id, new_messages[-1].id)

    def test_import_backup_rejects_invalid_format(self):
        session = self._session()
        defs = self._defs(session)
        self._save(session, defs)
        session.commit()
        with self.assertRaises(HTTPException) as invalid:
            backup_route.import_backup(session, {"format": "nope", "version": 1})
        self.assertEqual(invalid.exception.status_code, 400)
        with self.assertRaises(HTTPException) as version:
            backup_route.import_backup(
                session, {"format": backup_route.BACKUP_FORMAT, "version": 99}
            )
        self.assertEqual(version.exception.status_code, 400)

    def test_import_backup_rejects_duplicate_attributes(self):
        session = self._session()
        defs = self._defs(session)
        self._save(session, defs)
        session.commit()
        payload = {
            "format": backup_route.BACKUP_FORMAT,
            "version": backup_route.BACKUP_VERSION,
            "save": {"name": "坏备份"},
            "attributes": [
                {"key": "affection", "value": 1},
                {"key": "affection", "value": 2},
            ],
        }
        with self.assertRaises(HTTPException) as ctx:
            backup_route.import_backup(session, payload)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_import_backup_clears_unknown_model_key(self):
        session = self._session()
        defs = self._defs(session)
        self._save(session, defs)
        session.commit()
        payload = {
            "format": backup_route.BACKUP_FORMAT,
            "version": backup_route.BACKUP_VERSION,
            "save": {"name": "旧档", "model_key": "ghost:model", "game_minutes": 5},
        }
        imported = backup_route.import_backup(session, payload)
        session.commit()
        self.assertEqual(imported.model_key, "")
        self.assertEqual(imported.name, "旧档（恢复）")
        self.assertEqual(imported.game_minutes, 5)

    def test_event_def_crud(self):
        session = self._session()
        defs = self._defs(session)
        self._save(session, defs)
        session.commit()

        created = defs_route.create_event_def(
            EventDefIn(
                key="custom_evt",
                name="自定义事件",
                category="manual",
                cost={"money": 10},
                effects={"attrs": {"mood": 1}},
                prompt_template="文本",
            ),
            session=session,
        )
        self.assertEqual(created["key"], "custom_evt")
        self.assertFalse(created["from_seed"])
        self.assertIn(
            "custom_evt",
            [item["key"] for item in defs_route.list_event_defs(session=session)],
        )

        updated = defs_route.update_event_def(
            created["id"], EventDefPatch(name="改名", enabled=False), session=session
        )
        self.assertEqual(updated["name"], "改名")
        self.assertFalse(updated["enabled"])

        with self.assertRaises(HTTPException) as duplicate:
            defs_route.create_event_def(
                EventDefIn(key="custom_evt", name="重复"), session=session
            )
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as category:
            defs_route.create_event_def(
                EventDefIn(key="bad_evt", name="非法分类", category="nope"),
                session=session,
            )
        self.assertEqual(category.exception.status_code, 400)

        defs_route.delete_event_def(created["id"], session=session)
        self.assertNotIn(
            "custom_evt",
            [item["key"] for item in defs_route.list_event_defs(session=session)],
        )

    def test_scene_def_crud_and_turn_validation(self):
        session = self._session()
        defs = self._defs(session)
        self._save(session, defs)
        session.commit()

        created = defs_route.create_scene_def(
            SceneDefIn(
                key="custom_scene",
                name="自定义场景",
                min_turns=2,
                max_turns=5,
                next_scenes=["a", " b ", ""],
            ),
            session=session,
        )
        self.assertEqual(created["next_scenes"], ["a", "b"])
        self.assertFalse(created["from_seed"])

        with self.assertRaises(HTTPException) as turns:
            defs_route.update_scene_def(
                created["id"], SceneDefPatch(min_turns=6), session=session
            )
        self.assertEqual(turns.exception.status_code, 400)

        updated = defs_route.update_scene_def(
            created["id"], SceneDefPatch(max_turns=10), session=session
        )
        self.assertEqual(updated["max_turns"], 10)

        defs_route.delete_scene_def(created["id"], session=session)
        self.assertNotIn(
            "custom_scene",
            [item["key"] for item in defs_route.list_scene_defs(session=session)],
        )

    def test_debug_trigger_fixed_event(self):
        session = self._session()
        defs = self._defs(session)
        save, _values = self._save(session, defs)
        session.add(
            EventDef(
                key="fixed_dbg", name="固定调试", category="fixed",
                trigger={},
                effects={"attrs": {"trust": 3}}, prompt_template="调试内容",
                once=False, cooldown_minutes=0, priority=0, enabled=True,
            )
        )
        session.commit()
        save_id = save.id

        with self.assertRaises(HTTPException) as blocked:
            events_route.trigger_manual(
                save_id, "fixed_dbg", debug=False, session=session
            )
        self.assertEqual(blocked.exception.status_code, 400)

        data = events_route.trigger_manual(
            save_id, "fixed_dbg", debug=True, session=session
        )
        self.assertEqual(data["event"]["key"], "fixed_dbg")
        session.commit()
        self.assertEqual(load_attr_values(session, save_id)["trust"], 13.0)
        logs = list(
            session.scalars(select(EventLog).where(EventLog.save_id == save_id))
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual((logs[0].meta or {}).get("source"), "debug")


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
