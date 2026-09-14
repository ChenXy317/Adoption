# STATUS — 当前状态记录

> 更新时间：2026-09-14（M4 记忆系统已完成，未提交；真实模型端到端与浏览器自检通过）
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
| M4 记忆系统（总结流水线与互斥任务、检索注入、记忆面板、场景记忆） | **已完成，未提交** |
| M5 行动与经济 | 未开工（下一步，见第八节） |

## 三、运行方式

- 环境：Python 3.14（`backend/.venv`，uv 创建）；Node 24；MySQL 8
- 数据库密码：系统用户环境变量 `MYSQL_PASSWORD`（`new_idea` 库自动建库建表）
- 服务端口：**18730**（`APP_PORT` 可配）；启动后浏览器开 `http://127.0.0.1:18730`
- 启动：双击 `快速启动.bat`（缺 dist 会自动构建）；或手动：
  `cd backend; .venv\Scripts\python.exe main.py`
- 测试：`cd backend; .venv\Scripts\python.exe -m unittest discover -s tests`（**88 项**）
- 前端：改动后 `cd frontend; npm run build`（后端托管 dist）；开发模式 `npm run dev`（Vite 代理 18730）

## 四、数据现状（库内）

- 女主角：**小澄**（19 岁）——内置设定书 `backend/seeds/character.json`，启动装载并以种子为准覆盖
- 存档：仅 `id=6「雨夜」`（6 条消息，`aihubmix:xiaomi-mimo-v2.5-free`）；M4 自检档均已清理
- 事件定义 18 条（`backend/seeds/events.json`）；场景定义 3 条（`backend/seeds/scenes.json`）——同 M3.5
- 记忆：正式档暂无；场景结束会写 `memories`（event/relationship），总结流水线也会写入
- 属性 tick 已生效：mood `regress`（回归 50，0.5/时）、vigilance `decay`（1/时）
- 供应商同前：`aihubmix` / `openrouter`（均 `use_env_key`，库内无明文密钥）

## 五、M4 变更清单（未提交）

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

## 六、M4 验证记录（2026-09-14）

- `unittest` 88 项全过；`npm run build` 通过
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

## 八、下一步 M5（行动与经济）建议顺序（PLAN 5.8）

1. 打工 manual 事件（4 小时 → +120，固定模板消息不耗 AI）+ 钱包面板收支
2. 送礼两档（¥80 / 好感+2；¥300 / 好感+5）与付费手动事件种子扩充（价目已定稿 PLAN §10）
3. 冷落规则（两次互动推进 ≥3 游戏日且无对话 → 好感 -1/日，单次上限 -5）
4. 性格演化（阶段倾向）与主动消息（推进越过时点触发，随推进 SSE 推送）
5. 事件链扩充（配合「事件 ⇄ 场景」混合链）

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
- 交流用中文；提交信息用泛化描述（AGENTS.md）；提交前建议先跑单测

## 十、给下一个会话的建议

- 动手前：读 `PLAN.md` + 本文件 → `git status`（M4 未提交）→ 建议先提交 M4 再开工 M5
- 后端改动需重启服务（未开 reload）；前端改动需 `npm run build`
- 验证习惯：先 `unittest` → 再 httpx 端到端（含 SSE/真实模型）→ 最后浏览器实测
- 聊天验证注意选可用模型（aihubmix 的 `xiaomi-mimo-v2.5-free`）；总结同样走该模型（或配 `MEMORY_MODEL`）
- 平衡数值已定稿（PLAN §10）；M5 的打工/礼物/冷落参数已在 `config.py`
