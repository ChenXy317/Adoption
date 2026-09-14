# STATUS — 当前状态记录

> 更新时间：2026-09-14（M5 行动与经济已完成，未提交；M4 后审查修复一并未提交）
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
| 全量审查修复 | 已完成，已提交 `d55e9e0` |
| M3.5 多轮场景（场景引擎、STATE scene、场景接口、SceneBanner、场景种子） | 已完成，已提交 `5551cd0` |
| M4 记忆系统（总结流水线与互斥任务、检索注入、记忆面板、场景记忆） | 已完成，已提交 `2ecceb3` |
| M4 后全量审查修复（结算顺序、场景接力、总结任务兜底、集成测试） | 已完成，未提交 |
| M5 行动与经济（打工+钱包、送礼两档、冷落、性格倾向、主动消息、事件链） | **已完成，未提交** |
| M6 打磨 | 未开工（下一步） |

## 三、运行方式

- 环境：Python 3.14（`backend/.venv`，uv 创建）；Node 24；MySQL 8
- 数据库密码：系统用户环境变量 `MYSQL_PASSWORD`（`new_idea` 库自动建库建表）
- 服务端口：**18730**（`APP_PORT` 可配）；启动后浏览器开 `http://127.0.0.1:18730`
- 启动：双击 `快速启动.bat`（缺 dist 会自动构建）；或手动：
  `cd backend; .venv\Scripts\python.exe main.py`
- 测试：`cd backend; .venv\Scripts\python.exe -m unittest discover -s tests`（**107 项**，含 14 项 DB 集成测试）
- 前端：改动后 `cd frontend; npm run build`（后端托管 dist）；开发模式 `npm run dev`（Vite 代理 18730）

## 四、数据现状（库内）

- 女主角：**小澄**（19 岁）——内置设定书 `backend/seeds/character.json`，启动装载并以种子为准覆盖
- 存档：仅 `id=6「雨夜」`（6 条消息，`aihubmix:xiaomi-mimo-v2.5-free`）；M4 自检档均已清理
- 事件定义 18 条（`backend/seeds/events.json`）；场景定义 3 条（`backend/seeds/scenes.json`）——M5 新增 6 条事件（打工/送礼两档/电影/礼物回响链/主动消息），共 **24 条**
- 记忆：正式档暂无；场景结束会写 `memories`（event/relationship），总结流水线也会写入
- 属性 tick 已生效：mood `regress`（回归 50，0.5/时）、vigilance `decay`（1/时）
- 供应商同前：`aihubmix` / `openrouter`（均 `use_env_key`，库内无明文密钥）

## 五、M4 与审查修复变更清单

**M4（已提交 `2ecceb3`）**

**后端**
- `game/memory.py`（新）：纯函数（`parse_summary` / `merge_entries` / `memory_score` / `select_memories` / `timeline_lines` / `clip_lines` / `build_summary_messages`）+ DB 区（`trigger_if_due` 阈值登记、`requeue_interrupted` 启动补跑、`_claim_job` 条件抢占、`_prepare_summary` / `_apply_summary`、`run_summary` / `safe_run_summary`、`retrieve` / `mark_recalled`）
- `ai_client.py`：新增非流式 `complete()`（总结用；重试与思考链剥离）
- `game/prompt.py`：`_memory_block` + `build_messages` 注入「长期记忆」块（顺序：场景 → 事件情境 → 长期记忆 → 内容风格）
- `routes/chat.py`：流前检索记忆注入并更新召回元数据；流后未总结消息 ≥ 阈值时登记任务，经 BackgroundTasks 在响应结束后执行
- `routes/memories.py`（新）：`GET/POST/PATCH/DELETE /api/saves/{id}/memories` + `POST .../memories/summarize`（手动总结同步等待）
- `main.py`：注册路由；lifespan 启动补跑中断任务
- `schemas.py`：`MemoryIn` / `MemoryPatch`；`config.py`：`MEMORY_*` 配置系列

**前端**
- `MemoryPanel.vue`（新）：记忆列表（类型/重要度/召回次数）、内容编辑、新增、归档/恢复、删除、手动总结；`Game.vue` 顶栏「记忆」入口

**测试**：68 → **88 项**（新增 `tests/test_memory.py` 20 项）

**审查修复（未提交，2026-09-14）**

后端
- `game/events.py`：新增 `write_time_note`（非对话推进的 system 时间说明）；`settle_time` 新增 `ordered_changes`（按实际应用顺序的属性变化，修正前端覆盖顺序）与 `skip_scene_enter`；场景推进跨日时补登记随机判定；`_roll_new_days` 写 flag 后 flush（修复首次跨日判定同事务内读不到 `random_rolls`、随机事件延迟一天触发的缺陷）
- `game/scenes.py`：`settle_scenes` 支持 `skip_enter`（手动结束场景后不接力进入下一幕）；结束结算按自增后的轮数记录（原记录少 1）
- `routes/chat.py`：`scene_update.active` 改用 `public_active`（不再下发场景设定原文）；属性变化改用 `ordered_changes`
- `routes/scenes.py` / `routes/events.py` / `routes/advance.py`：非对话推进统一补时间说明 system 消息；手动结束场景传 `skip_scene_enter=True`
- `game/memory.py`：总结任务任何异常都落 failed（不再卡 running）；支持存档级 `settings.memory_model` 覆盖总结模型（与删除保护口径一致）
- `main.py`：新增 422 参数错误的统一错误结构（前端 api 客户端依赖 message 字段）
- `seeds/loader.py`：`max_turns` 缺省值改用 `SCENE_MAX_TURNS_DEFAULT`（恢复该配置引用）

前端
- `stores/chat.js`：有回复文本但流中断时也刷新权威状态
- `views/Game.vue`：路由参数变化时重新加载（切换存档不残留旧数据）
- `ModelCatalogModal.vue`：模型 model-id 可编辑（后端已有引用保护）；新增「清除已存密钥」

测试与文档
- 新增 `tests/test_integration.py`（9 项，使用独立 `new_idea_test` 库、自动建删）：结算 tick/固定事件/跨日随机、场景生命周期与不接力、手动结束不接力、advance 时间说明、对话结算（含解析失败兜底）、记忆总结流水线与失败落库、422 错误格式
- `PLAN.md` §5.3/§7/§9 明确：事件/场景定义 CRUD 推迟（当前以种子文件维护，列入 M6 之后）

**M5 行动与经济（未提交，2026-09-14）**

后端
- `game/events.py`：`manual_candidates` 纳入 `work` 分类（返回 category）；`apply_event` 支持 `extra_meta`（manual 扣费明细入日志）与事件 effects 的 `unlock_scenes`；`_leaf` 新增 `hour` 条件；新增 `apply_ai_flags`（拒绝系统保留键 / `scene_`、`event_` 前缀 / 非法值）；新增 `apply_neglect` 冷落结算（距上次对话 ≥ 阈值天数后按超时天数增量扣好感，单次上限，`settings.neglect` 可覆盖）；`set_flag` 复制 dict 存储（修复就地修改 JSON 值导致 ORM 漏检变更的缺陷，随机判定同受益）
- `game/attributes.py`：新增 `tendency_of`（戒备/黏人/信赖/安定，依赖/信任比 + 互动计数）
- `game/prompt.py`：当前状态块注入「当前倾向」与「她此刻的心情」；新增 `_tendency_note` 与通用兜底
- `routes/chat.py`：解析并应用 STATE 的 `flags` 与 `mood_label`，写入消息 meta 与 SSE state_update；prompt 注入倾向与心情
- `routes/events.py`：放行 `work` 分类触发；扣费明细写 event_logs
- `routes/state.py`：返回 `tendency` / `mood_label` / `work_actions` / `wallet_flows`（收支来源 event_logs）
- `helpers.py`：新增 `behavior_count`（互动计数）
- 种子：`events.json` 新增打工（4h→+120）、小礼物（¥80/好感+2）、大礼物（¥300/好感+5，写 flag 触发回响事件链）、看电影（¥60）、她的晚间消息（主动消息）、礼物回响（事件链）；`character.json` 新增 `tendencies` 四类描述

前端
- `WalletPanel.vue`（新）：余额 + 打工入口 + 最近收支；`Game.vue` 接入并展示关系倾向与心情
- `stores/game.js` / `stores/chat.js`：state_update 同步倾向与心情

测试
- `test_game.py` 新增倾向 5 项；`test_events.py` 补 hour 条件；`test_integration.py` 新增 M5 五项（打工与钱包、送礼与事件链、冷落增量与上限、AI flags/心情、主动消息）

## 六、验证记录（2026-09-14）

- `unittest` **107 项**全过（纯函数 93 + DB 集成 14）；`npm run build` 通过
- httpx 端到端（真实模型 aihubmix，临时档已清理，21 项全过）：22 条消息 → 达阈值登记 pending 任务 → 总结新增 6 条（抽取质量抽检良好）→ 进度推进 / 未总结清零 / 任务 done → 记忆 CRUD → prompt 注入「长期记忆」且召回计数更新 → 模型缺失时失败状态落库
- 浏览器实测：记忆弹层打开（未总结 22 条）→ 手动总结 → 6 条记忆上屏 → 归档 → 恢复

## 七、关键决策速查（M4 实现口径）

- **触发**：未总结消息 ≥ `MEMORY_TRIGGER_TURNS`(20) 时，流后结算登记 pending；同一存档已有 pending/running 不重复登记；手动总结同步等待；启动把 running 回退 pending 并补跑
- **互斥**：`save_settle_lock` 保护「检查+抢占」短临界区；条件 `UPDATE ... WHERE status='pending'`（rowcount=1）抢占 running；**LLM 调用期间不持锁**
- **摘要输入**：`last_summarized_message_id` 之后的消息（≤200 条）+ 期间事件日志（≤50 条）+ 已有 active 记忆（≤60 条，提示不要重复输出）；时间线按虚拟时间排序，字符预算 12000 保留最近部分
- **摘要输出**：LLM 只输出 JSON 数组；解析失败记 job failed（不推进进度，下次重试）；kind 白名单回退 fact、importance 钳制 1-10、content ≤300 字；与已有记忆及本次内部按文本去重
- **检索注入**：重要性 × 新近度打分（新记忆最高约 2 倍加成、随时间衰减到 1 倍）；核心（`relationship` 或 ≥8）常驻预算；总预算 2000 字符；注入后更新 `last_recalled_at` / `recall_count`
- **总结模型**：`MEMORY_MODEL`，空则用存档主模型；输出上限 2048 tokens
- **场景记忆去重**：场景结束写的 `memories` 会作为「已有记忆」附给总结提示，避免重复抽取
- **场景接力**：手动结束场景时 `settle_time(skip_scene_enter=True)`，本次结算不再进入新场景（与对话路径同口径）；下一次结算再评估
- **结算顺序**：`ordered_changes` 为唯一权威的属性变化序列（AI → tick → 事件/场景效果），前端按序覆盖后再以 state 刷新兜底
- **总结任务兜底**：任何异常都会把 job 落 failed（不卡 running）；总结模型优先级 `save.settings.memory_model` → `MEMORY_MODEL` → 存档主模型
- **随机判定**：跨日判定写 `random_rolls` 后 flush；场景/事件推进跨日同样登记，避免当日判定丢失
- **M5 口径**：打工 = `category="work"` 的确定性事件（时间换钱、固定模板消息、不走 AI）；送礼/消费 = manual 事件（cost + effects + 专属 prompt_template，AI 在下一轮对话承接演出）；冷落 = 距上次 user/assistant 消息 ≥3 游戏日，按超时天数增量扣好感（-1/日、单次上限 -5、`save_flags.neglect` 记录已扣天数，对话后自动重置）；倾向 = `tendency_of(属性, 互动计数)`；主动消息 = 带 period/hour 条件的 fixed 事件（随推进返回并上前端）
- **AI flags 白名单**：仅允许 `^[a-z][a-z0-9_]{0,63}$`，拒绝 `active_scene`/`random_rolls`/`neglect`/`mood_label` 与 `scene_`/`event_` 前缀；`mood_label` 单独存 flag 并注入 prompt

## 八、下一步 M6（打磨）建议顺序

1. 轻量导出备份（存档 JSON 全量导出/恢复，PLAN §9 M6）
2. 事件/场景定义管理界面（PLAN §5.3/§7 推迟项：event-defs/scene-defs CRUD + EventDefEditor/SceneDefEditor）
3. 主题（ThemeModal）与 README 收尾；向量检索（可选）
4. 如需扩展 M5：付费手动事件触发后立即 AI 演出（当前为事件消息 + 下一轮承接）、更多打工/礼物种子

## 九、环境坑与约定（踩过的雷）

- 服务控制台窗口**不能关**（关 = 停服）；请用 `快速启动.bat`（独立窗口）
- PowerShell 5.1 调 API 中文会乱码——接口测试统一用 `backend/.venv` 的 python + httpx，并设 `PYTHONIOENCODING=utf-8`
- mysql CLI：`key` 是保留字需反引号；该实例 `ANSI_QUOTES` 开启，字符串必须单引号
- SQLAlchemy pin ≥2.0.41（Py3.14）；属性数值列用 `Double`
- `SessionLocal` 为 `autoflush=False`：手动改 ORM 行后、依赖查询前需先 flush
- 流式阶段不写 DB；状态标签解析失败留痕 `meta.tag_debug`
- `save_flags` 读写用 `events.set_flag` / `scenes.get_active`（dict 值不加 "value" 包装）；场景 active 读旧格式时兼容 `{"value": {...}}`
- 总结任务的 LLM 调用不持结算锁（避免阻塞聊天）；`asyncio.run` 只适用于脚本自检，服务内统一走 BackgroundTasks / lifespan 任务
- codebase-memory 图谱**已索引**本项目（项目名 `new-idea`；M3.5/M4 新代码可重索引）
- 集成测试会建 `new_idea_test` 库并在结束时删除；需 MySQL 可用（与原有测试的前置条件相同）
- 交流用中文；提交信息用泛化描述（AGENTS.md）；提交前建议先跑单测

## 十、给下一个会话的建议

- 动手前：读 `PLAN.md` + 本文件 → `git status`（审查修复 + M5 未提交）→ 建议先提交再开工 M6
- 后端改动需重启服务（未开 reload）；前端改动需 `npm run build`
- 验证习惯：先 `unittest` → 再 httpx 端到端（含 SSE/真实模型）→ 最后浏览器实测
- 聊天验证注意选可用模型（aihubmix 的 `xiaomi-mimo-v2.5-free`）；总结同样走该模型（或配 `MEMORY_MODEL`）
- 平衡数值已定稿（PLAN §10）；M5 的打工/礼物/冷落参数已在 `config.py`
