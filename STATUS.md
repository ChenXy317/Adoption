# STATUS — 当前状态记录

> 更新时间：2026-09-14（M3 已提交 `679a356`；全量审查完成，P1/P2/P3 修复未提交）
> 用途：跨会话交接。新会话先读 `PLAN.md`（唯一真相源）+ 本文件，再动手。

## 一、项目速览

- 位置：`D:\Projects\New Idea`（git 仓库，main 分支）
- 定位：单女主、深刻画的 galgame 式文字养成游戏（方向参考 Teaching Feeling），个人自用、不发布
- 技术栈：FastAPI + SQLAlchemy 2.0 + MySQL 8（`new_idea` 库）/ Vue 3 + Vite + Pinia；SSE 流式对话
- 详细设计见 `PLAN.md`；启动脚本 `快速启动.bat` / `重置启动.bat`

## 二、进度

| 里程碑 | 状态 |
|---|---|
| M1 骨架（建表+种子、存档 CRUD、模型目录、SSE 对话、Vue 基础界面） | 已完成，已提交 `44c7425` |
| M2 女主角刻画（内置设定书、prompt 深度注入、属性管理接口） | 已完成，已提交 `890a3bd` |
| M3 事件与时间（虚拟时钟结算、三类事件、推进面板、事件种子） | 已完成，已提交 `679a356` |
| 审查修复（P1 属性补行/标签类型防御；P2/P3 见第十一节） | **已完成，未提交** |
| M3.5 多轮场景 | 未开工（下一步，见第八节） |

## 三、运行方式

- 环境：Python 3.14（`backend/.venv`，uv 创建）；Node 24；MySQL 8
- 数据库密码：系统用户环境变量 `MYSQL_PASSWORD`（`new_idea` 库自动建库建表）
- 服务端口：**18730**（`APP_PORT` 可配）；启动后浏览器开 `http://127.0.0.1:18730`
- 启动：双击 `快速启动.bat`（缺 dist 会自动构建）；或手动：
  `cd backend; .venv\Scripts\python.exe main.py`
- 测试：`cd backend; .venv\Scripts\python.exe -m unittest discover -s tests`（**46 项**）
- 前端：改动后 `cd frontend; npm run build`（后端托管 dist）；开发模式 `npm run dev`（Vite 代理 18730）

## 四、数据现状（库内）

- 女主角：**小澄**（19 岁）——内置设定书 `backend/seeds/character.json`，启动装载并以种子为准覆盖
- 存档：仅 `id=6「雨夜」`（6 条消息，`aihubmix:xiaomi-mimo-v2.5-free`）；M3 自检档均已清理
- 事件定义：`backend/seeds/events.json` 共 **18 条**，启动装载（种子为准覆盖同 key）：
  - 主线 fixed（flag 串联，once）：第一个早晨 → 噩梦 → 手腕上的疤 → 不会送你走
  - 阶段 fixed（once）：改口叫名字、第一次开口要东西、想要一个拥抱
  - random（每日判定，带 chance/冷却）：午后的雨、楼下的猫、等你回家、说梦话、偷偷学的菜、偷偷缝好的衣服
  - manual（行动菜单，带 cost）：傍晚散步、一起煮火锅、帮她整理头发、带她买连衣裙、陪她逛书店
- 属性 tick 已生效：mood `regress`（回归 50，0.5/时）、vigilance `decay`（1/时）
- 供应商同前：`aihubmix` / `openrouter`（均 `use_env_key`，库内无明文密钥）

## 五、M3 变更清单（已提交 `679a356`，历史记录）

**后端**
- `game/events.py`（新）：条件求值器（`all/any/not` + `attr/flag/game_day/period/date/since_event` + 根级 `chance`）；可用性（启用/once/冷却/条件）；`settle_time` 统一结算（tick → 跨日随机判定 → fixed/random 触发 → 效果应用，最多 4 轮、单次最多 3 个事件）
- `game/clock.py`：`day_index` / `game_day_of` / `day_starts_between`（跨日检测）/ `next_period_start`
- `game/attributes.py`：`apply_ticks`（decay/recover/regress）、`apply_effects`（事件效果，可改金钱、无单次上限）
- `routes/advance.py`（新）：`POST /api/saves/{id}/advance`（minutes / period / target 三种方式，+1 天=1440 上限，目标跳最多 60 天）、`GET /api/saves/{id}/clock`
- `routes/events.py`（新）：`GET /api/saves/{id}/events`（历史）、`POST /api/saves/{id}/events/{key}/trigger`（manual：条件+金钱校验 → 扣钱/耗时 → 落库）
- `routes/chat.py`：流后走 `settle_time`；SSE 新增 `event_triggered`；prompt 注入「当前事件情境」（180 虚拟分钟窗口、最多 3 条）
- `routes/state.py`：`recent_events`（最近 5 条）、`manual_events`（可用性+原因）
- `seeds/loader.py` + `seeds/events.json`：事件种子装载
- `schemas.py`：`AdvanceIn`
- 配置：`EVENT_MAX_PER_SETTLEMENT=3`、`EVENT_RECENT_WINDOW_MINUTES=180`

**前端**
- `AdvancePanel.vue`（+10分/+1时/+1天/跳到时段）、`ActionPanel.vue`（互动列表：cost、可用性、冷却/条件/金钱不足提示）、`EventPanel.vue`（最近事件）
- `stores/chat.js`：处理 `event_triggered`（追加事件消息并在流后刷新状态）
- `stores/game.js`：`advance` / `triggerManual`；`Game.vue` 右栏接入三个面板

**测试**：21 → **46 项**（`tests/test_events.py` 新增；tick/效果/时钟扩展补进 `test_game.py`）

## 六、M3 验证记录（2026-09-14）

- `unittest` 46 项全过
- httpx 端到端（临时档，已清理）：推进 60m 触发「第一个早晨」+ tick 正确；剧情链按序触发（d3 深夜噩梦 → 疤 → 约定），once 不重复；随机判定 12 游戏日命中多个且**同日不重复**；manual 冷却/条件/花钱校验与扣款正确
- 真实模型 SSE（aihubmix `xiaomi-mimo-v2.5-free`）：事件情境进入 prompt，回复围绕事件演出；`state_update/event_triggered/time_update/done` 顺序正常
- 浏览器实测：新建档 → 推进面板 +10 分（事件上屏、属性/时间实时更新）→ 散步（冷却按钮变灰）

## 七、关键决策速查（M3 实现口径）

- **随机事件**：每游戏日**零点**判定一次（判定时忽略时段/日期条件），结果记 `save_flags.random_rolls = {key:{day,hit}}`；命中后当天满足全部条件（含时段）即注入，同日不重复；当天尚无判定记录时（含开局首日）在下一次结算补判一次
- **固定事件**：每次结算评估；种子均 `once=true`。注意：自定义 fixed 若不带 once/cooldown，会每次结算重复触发
- **手动事件**：条件/once/冷却 + 金钱余额校验；`cost.money` 直接扣（支持小数），`cost.time_minutes` 作为额外推进走统一结算
- **效果 JSON**：`attrs`（无视 ai_editable，可改钱）/ `advance_minutes`（单次上限 24h）/ `flags` / `unlock_events`（写 `event_unlocked:<key>` flag）
- **事件落库**：`event_logs` + `role=event` 消息 + prompt 情境块；SSE `event_triggered` 携带消息体
- **大跳兜底**：跳过多日时中间日期只做随机判定、不注入（仅当日命中注入）；单次结算最多 4 轮/3 事件防循环
- **结算串行**：同一存档的「流后结算 / advance / 手动事件」共用进程内锁（helpers.save_settle_lock），防并发覆盖属性
- **推进参数**：AI 推进的默认/上限读存档 `settings.advance`（缺省回退 config 10/180）；显式推进仍由 `TIME_MAX_JUMP_HOURS` 钳制

## 八、下一步 M3.5（多轮场景）建议顺序（PLAN 5.3 / 里程碑）

1. `game/scenes.py`：进入/持续/结束/结算；`save_flags.active_scene` 生命周期（同时仅 1 个）
2. STATE 标签扩展 `"scene":{"action":"end","summary":...}`；min_turns 内拒绝提前收尾；max_turns 注入收尾指令
3. `/api/saves/{id}/scenes`（历史/调试进入）、`/scenes/end`（手动收尾）；effects 支持 `start_scene`
4. 前端 `SceneBanner`（名称/轮数/目标/结束）；场景种子 2–3 个（约会/照顾生病等）
5. 场景结束写入场景记忆（kind=event/relationship，M4 前可先落 `memories` 占位）
6. 单测：进入条件复用事件求值器、轮数边界、结算 flags/attrs

## 九、环境坑与约定（踩过的雷）

- 服务控制台窗口**不能关**（关 = 停服）；请用 `快速启动.bat`（独立窗口）
- PowerShell 5.1 调 API 中文会乱码——接口测试统一用 `backend/.venv` 的 python + httpx，并设 `PYTHONIOENCODING=utf-8`
- mysql CLI：`key` 是保留字需反引号；该实例 `ANSI_QUOTES` 开启，字符串必须单引号
- SQLAlchemy pin ≥2.0.41（Py3.14）；属性数值列用 `Double`
- `SessionLocal` 为 `autoflush=False`：手动改 ORM 行后、依赖查询前需先 flush
- 流式阶段不写 DB；状态标签解析失败留痕 `meta.tag_debug`
- codebase-memory 图谱**已索引**本项目（项目名 `new-idea`，530+ 节点）
- 交流用中文；提交信息用泛化描述（AGENTS.md）；提交前建议先跑单测

## 十、给下一个会话的建议

- 动手前：读 `PLAN.md` + 本文件 → `git status`（审查修复未提交）→ 可先提交修复再开工 M3.5
- 后端改动需重启服务（未开 reload）；前端改动需 `npm run build`
- 验证习惯：先 `unittest` → 再 httpx 端到端（含 SSE）→ 最后浏览器实测
- 聊天验证注意选可用模型（aihubmix 的 `xiaomi-mimo-v2.5-free`），OpenRouter 免费额度可能已用尽
- 平衡数值已定稿（PLAN §10）；冷落规则/打工/礼物为 M5 实现时的数据依据

## 十一、审查修复记录（2026-09-14，未提交）

全量审查（含无模型真库冒烟）后修复：

- **P1-1 属性值补行**：`events.write_changes` 在 `attribute_values` 缺行时自动补建（此前建档后新增/重新启用的属性，变化只上报不落库）
- **P1-2 标签类型防御**：STATE 标签 `attrs`/`time` 非 dict 时不再抛异常（`game/attributes.py` 也加了 deltas 类型守卫）；结构异常静默忽略
- **P2-1 存档级推进生效**：`clock.advance_limits(settings)` 读取 `settings.advance`（默认 10 / 上限 180），替换原全局常量硬编码
- **P2-2 首日随机判定**：当天无 `random_rolls` 记录时（含开局首日）在结算中补判一次
- **P2-3 属性种子覆盖式**：`seeds/loader.apply_seeds` 改为与角色/事件一致（种子为准覆盖字段），`enabled` 不受影响；README 已注明
- **P2-4 前端刷新**：聊天成功结算后也 `loadState`，互动菜单可用性不再过期（`stores/chat.js`）
- **P2-5 重置脚本**：`重置启动.bat` 从 `.env` 读 host/port/user/database/password（系统环境变量优先）
- **P2-6 平衡数值定稿**：见 PLAN §10；参数落 `config.py`（`WORK_*` / `GIFT_TIERS` / `NEGLECT_*`）
- **P3-1 SPA 路径校验**：`main.py` 改用 `is_relative_to`（防同前缀目录绕过）
- **P3-2 money 小数**：手动事件扣款不再 `int()` 截断
- **P3-3 结算锁**：同一存档的流后结算/advance/手动事件串行（`helpers.save_settle_lock`），防并发覆盖
- **P3-4 存档缺失**：流后结算发现存档被删时回 SSE `error`（`save_not_found`），不再 500
- **P3-5 文档/默认值**：`EventDef.category` 默认改 `fixed`；PLAN 5.5 标签说明与 API 表修正
