# STATUS — 当前状态记录

> 更新时间：2026-09-14（M5 后审查修复已提交 `bab2d80`；M6 打磨已提交 `f9dec71`；M6 后全量审查修复已完成，待提交）
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
| M4 后全量审查修复（结算顺序、场景接力、总结任务兜底、集成测试） | 已完成，已提交 `75fdcce` |
| M5 行动与经济（打工+钱包、送礼两档、冷落、性格倾向、主动消息、事件链） | 已完成，已提交 `a953e5e` |
| M5 后全量审查修复（场景冷却、总结兜底、STATE 协议闭环、断流竞态、参数防御、种子启停） | 已完成，已提交 `bab2d80` |
| M6 打磨（导出/恢复、定义管理界面与调试触发、暗/亮主题） | 已完成，已提交 `f9dec71` |
| M6 后全量审查修复（备份校验、场景收尾、钱包流水、消息分页、心情有效期等 17 项） | 已完成，待提交 |

## 三、运行方式

- 环境：Python 3.14（`backend/.venv`，uv 创建）；Node 24；MySQL 8
- 数据库密码：系统用户环境变量 `MYSQL_PASSWORD`（`new_idea` 库自动建库建表）
- 服务端口：**18730**（`APP_PORT` 可配）；启动后浏览器开 `http://127.0.0.1:18730`
- 启动：双击 `快速启动.bat`（缺 dist 会自动构建）；或手动：
  `cd backend; .venv\Scripts\python.exe main.py`
- 测试：`cd backend; .venv\Scripts\python.exe -m unittest discover -s tests`（**138 项**，含 32 项接口/DB 集成测试）
- 前端：改动后 `cd frontend; npm run build`（后端托管 dist）；开发模式 `npm run dev`（Vite 代理 18730）

## 四、数据现状（库内）

- 女主角：**小澄**（19 岁）——内置设定书 `backend/seeds/character.json`，启动装载并以种子为准覆盖
- 存档：仅 `id=6「雨夜」`（6 条消息，`aihubmix:xiaomi-mimo-v2.5-free`）；M4 自检档均已清理
- 事件定义 18 条（`backend/seeds/events.json`）；场景定义 3 条（`backend/seeds/scenes.json`）——M5 新增 6 条事件（打工/送礼两档/电影/礼物回响链/主动消息），共 **24 条**
- 记忆：正式档暂无；场景结束会写 `memories`（event/relationship），总结流水线也会写入
- 属性 tick 已生效：mood `regress`（回归 50，0.5/时）、vigilance `decay`（1/时）
- 供应商同前：`aihubmix` / `openrouter`（均 `use_env_key`，库内无明文密钥）

## 五、M4 / M5 变更清单

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

**审查修复（已提交 `75fdcce`）**

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
- `PLAN.md` §5.3/§7/§9 明确：事件/场景定义 CRUD 曾推迟（已由 M6 完成，见上）

**M5 行动与经济（已提交 `a953e5e`）**

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

**M5 后全量审查修复（已提交 `bab2d80`）**

后端
- `game/scenes.py`：场景结束/中止时把 `scene_logs.game_minutes_at` 更新为结束时刻（修复冷却起点误用开始时刻、冷却提前失效）；`abort_scene` 增加 `now_abs` 参数
- `game/memory.py`：`_prepare_summary` 抢占成功后的任何异常都会把任务落 failed（修复准备阶段异常导致 job 卡 running、该档总结永久停摆）
- `game/prompt.py`：STATE 协议补充 `mood_label` 与 `flags` 的说明与示例（修复 M5 心情与 AI 剧情标记不闭环）
- `routes/chat.py`：新增 `settle_started` 标志（修复结算期间客户端断开时兜底线程二次结算）；state_update 的 `tendency` 统一为字符串（与 `/state` 一致）
- `ai_client.py`：`num_predict` 仅正数生效（0/非法值不再产生 max_tokens=0 或 TypeError 断流）
- `seeds/loader.py`：事件/场景种子不再覆盖已存在记录的 `enabled`（与 README 声明一致；新增记录仍按种子启用）

前端
- `stores/chat.js`：取消/失败且无回复文本时移除空占位气泡

测试
- 新增 `tests/test_ai_client.py`（参数组装 5 项）；`test_game.py` 补 STATE 协议覆盖；`test_integration.py` 新增 4 项（场景冷却起点、总结准备失败落库、事件/场景种子启停保留）

**M6 打磨（已提交 `f9dec71`）**

后端
- `routes/backup.py`（新）：`GET /api/saves/{id}/export` 导出全量 JSON（存档元数据、属性、标记、消息、事件/场景日志、记忆、角色快照，附件文件名 RFC 5987）；`POST /api/saves/import` 导入为新存档（消息 id 重映射、`last_summarized_message_id` 与记忆来源映射、event_key 重新关联定义、未知 model_key 置空、非法格式/版本 400、消息条数上限）
- `main.py`：注册备份路由
- `routes/defs.py`：新增 `/api/event-defs`、`/api/scene-defs` CRUD（key 创建后不可改、事件分类白名单、min/max 轮数校验、`from_seed` 内置标记）；`routes/events.py` 的 manual 触发支持 `?debug=true`（任意分类、跳过条件与余额校验、source=debug）；`game/events.py` 的 `settle_time` 新增 `exclude_events`（避免手动/调试触发的事件在同一次结算中被重复收集）
- `schemas.py`：`EventDefIn/Patch`、`SceneDefIn/Patch`

前端
- `views/Home.vue`：存档卡片「导出」（附件下载，实现于点击处 `@click.stop`）；顶栏「导入存档」（文件选择 → POST → 跳转新档）、「定义管理」、「主题」入口
- `components/DefsPanel.vue`（新）：事件/场景定义管理弹层（列表、编辑表单、JSON 字段、启停、新建/删除、内置标记、对存档调试触发）
- `components/ThemeModal.vue`（新）+ `stores/ui.js` 主题状态与 localStorage 持久化 + `styles/base.css` 亮色变量；`main.js` 启动应用主题；`views/Game.vue` 接入两个入口

测试
- `test_integration.py` 新增 6 项：导出导入往返、非法格式与版本拒绝、未知模型 key 置空、事件定义 CRUD（重复 key/非法分类）、场景定义 CRUD（轮数校验）、debug 触发（分类拦截、效果只应用一次、source=debug）

**M6 后全量审查修复（已完成，待提交）**

后端
- `routes/backup.py`：导入时属性 key 重复返回 400（原先 IntegrityError→500）、消息 `game_minutes_at` 钳制非负、事件/场景日志与记忆数量上限（20000）；导出/展示统一走 `get_save_character`（character_id 缺失回退全局女主角）
- `game/scenes.py`：活跃场景的定义被删除/停用时改为 `abort_scene` 落 `aborted` 日志（原先静默清 active 遗留 started）；场景进入花费与结束效果的金钱变动补写 `event_logs`（category=scene），钱包「最近收支」不再漏记
- `routes/chat.py`：空白消息（strip 后为空）返回 400；`_prepare` 标记事件情境已注入（`meta.narrated`），每条事件只在触发后的第一轮 prompt 注入一次；心情短语写入 `mood_label_at`；SSE 返回有效期内的实际心情
- `game/events.py`：新增 `mood_label_of` / `set_mood_label`（TTL=`MOOD_LABEL_TTL_HOURS` 24 虚拟小时，超期不再注入；旧数据缺时间戳视为过期）；`recent_events` 过滤已注入与场景类日志；冷落参数显式支持 0=禁用（原先 0 被替换成默认值）
- `config.py`：新增 `MOOD_LABEL_TTL_HOURS`
- `routes/state.py`：钱包流水扫描深度 16 → 120；`mood_label` 走有效期判定；角色回退
- `seeds/loader.py`：种子数值字段统一安全转换（null/非法值不再导致启动崩溃）
- `routes/defs.py`：`_seed_keys` 按 mtime 缓存，列表接口不再每次读盘
- `ai_client.py`：`_looks_like_unknown_param` 去掉过宽的 `invalid parameter` 匹配（避免无谓重试）
- `main.py`：`server.log` 改为 5MB × 3 轮转
- `helpers.py`：新增 `get_save_character`

前端
- `stores/chat.js` + `components/ChatStream.vue` + `views/Game.vue`：消息历史「加载更早的消息」（利用已有 `before_id`/`has_more`，前置插入并保持滚动位置；自动滚底改为只看最后一条消息变化）

测试
- `unittest` 123 → **138 项**：新增心情 TTL/旧数据过期、种子与 config 数值一致性、关闭思考参数识别范围、空白消息 400、冷落禁用、场景定义删除落 aborted、场景金钱流水、事件只注入一次、消息分页、导入重复属性拒绝

## 六、验证记录（2026-09-14）

- `unittest` **107 项**全过（纯函数 93 + DB 集成 14）；`npm run build` 通过
- httpx 端到端（真实模型 aihubmix，临时档已清理，21 项全过）：22 条消息 → 达阈值登记 pending 任务 → 总结新增 6 条（抽取质量抽检良好）→ 进度推进 / 未总结清零 / 任务 done → 记忆 CRUD → prompt 注入「长期记忆」且召回计数更新 → 模型缺失时失败状态落库
- 浏览器实测：记忆弹层打开（未总结 22 条）→ 手动总结 → 6 条记忆上屏 → 归档 → 恢复
- 审查修复复验（2026-09-14）：`unittest` **117 项**全过（纯函数 99 + DB 集成 18，新增 10 项）；`npm run build` 通过；httpx 端到端（真实模型 aihubmix，临时档已清理，20 项全过）：SSE 链路、`tendency` 字符串、事件触发与时间推进、时间说明均正常
- M6 导出恢复验证（2026-09-14）：`unittest` **120 项**全过（新增 3 项）；`npm run build` 通过；httpx 端到端（正式档只读导出 → 导入 → 消息/属性/时间一致性校验 → 清理，15 项全过）；浏览器实测首页「导入存档」上传备份 → 跳转新档且 6 条消息与属性完整恢复 → 返回列表双档显示 → 测试档已清理
- M6 定义管理/主题验证（2026-09-14）：`unittest` **123 项**全过（新增 3 项）；`npm run build` 通过；httpx 端到端（定义 CRUD、调试触发与清理，16 项全过）；浏览器实测定义弹层（24 事件/3 场景、内置标记、编辑表单渲染正确）、亮/暗主题切换与 localStorage 持久化；期间修复 debug 触发 fixed 事件被同次结算重复收集的缺陷
- M6 后审查修复复验（2026-09-14）：`unittest` **138 项**全过（纯函数 106 + 集成 32，新增 15 项）；`npm run build` 通过；httpx 端到端（临时起服务，8 项全过）：空白消息 400、推进 1 天、state 结构、消息分页字段、导入重复属性 400、导出导入往返；临时档与测试库均已清理（库内仅正式档 id=6）

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

## 八、M6（打磨）完成情况

1. 轻量导出备份 — 已完成（`GET /api/saves/{id}/export` + `POST /api/saves/import`，首页「导出」「导入存档」）
2. 事件/场景定义管理界面 — 已完成（defs CRUD + DefsPanel 弹层 + 调试触发）
3. 主题与 README 收尾 — 已完成（暗/亮主题，持久化；README/PLAN 已更新）
4. 可选后置 — 未做：向量检索（embedding top-K）、M5 扩展（付费事件即时 AI 演出、更多打工/礼物种子）

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

- 动手前：读 `PLAN.md` + 本文件 → `git status`（M5 后审查修复已提交 `bab2d80`；M6 打磨已提交 `f9dec71`；M6 后全量审查修复已完成，待提交）
- 可选后置项：向量检索（embedding top-K）、M5 扩展（付费事件即时 AI 演出、更多打工/礼物种子）；新增事件/场景可直接用「定义管理」界面或种子文件
- 后端改动需重启服务（未开 reload）；前端改动需 `npm run build`
- 验证习惯：先 `unittest` → 再 httpx 端到端（含 SSE/真实模型）→ 最后浏览器实测
- 聊天验证注意选可用模型（aihubmix 的 `xiaomi-mimo-v2.5-free`）；总结同样走该模型（或配 `MEMORY_MODEL`）
- 平衡数值已定稿（PLAN §10）；M5 的打工/礼物/冷落参数已在 `config.py`
