# STATUS — 当前状态记录

> 更新时间：2026-09-14（M3.5 多轮场景已完成，未提交；真库与浏览器自检通过）
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
| 全量审查修复（P1 属性补行/标签类型防御；P2/P3 见 PLAN 工程口径） | 已完成，已提交 `d55e9e0` |
| M3.5 多轮场景（场景引擎、STATE scene、场景接口、SceneBanner、场景种子） | **已完成，未提交** |
| M4 记忆系统 | 未开工（下一步，见第八节） |

## 三、运行方式

- 环境：Python 3.14（`backend/.venv`，uv 创建）；Node 24；MySQL 8
- 数据库密码：系统用户环境变量 `MYSQL_PASSWORD`（`new_idea` 库自动建库建表）
- 服务端口：**18730**（`APP_PORT` 可配）；启动后浏览器开 `http://127.0.0.1:18730`
- 启动：双击 `快速启动.bat`（缺 dist 会自动构建）；或手动：
  `cd backend; .venv\Scripts\python.exe main.py`
- 测试：`cd backend; .venv\Scripts\python.exe -m unittest discover -s tests`（**68 项**）
- 前端：改动后 `cd frontend; npm run build`（后端托管 dist）；开发模式 `npm run dev`（Vite 代理 18730）

## 四、数据现状（库内）

- 女主角：**小澄**（19 岁）——内置设定书 `backend/seeds/character.json`，启动装载并以种子为准覆盖
- 存档：仅 `id=6「雨夜」`（6 条消息，`aihubmix:xiaomi-mimo-v2.5-free`）；M3.5 自检档均已清理
- 事件定义：`backend/seeds/events.json` 共 **18 条**（同 M3：主线 4 + 阶段 3 + random 6 + manual 5）
- 场景定义：`backend/seeds/scenes.json` 共 **3 条**，启动装载（种子为准覆盖同 key）：
  - `date_first_outing` 第一次一起出门（trust≥18/affection≥12/白天；无 once，冷却 7 天）
  - `talk_rainy_night` 雨夜谈心（trust≥35/affection≥30/傍晚或晚上；once；next_scenes → care_fever）
  - `care_fever` 照顾发烧的她（flag `scene_unlocked:care_fever` + trust≥35；once；category=relationship）
- 属性 tick 已生效：mood `regress`（回归 50，0.5/时）、vigilance `decay`（1/时）
- 供应商同前：`aihubmix` / `openrouter`（均 `use_env_key`，库内无明文密钥）

## 五、M3.5 变更清单（未提交）

**后端**
- `game/scenes.py`（新）：场景引擎。纯函数（`scene_availability` 复用事件条件求值器、`should_finish` 轮数边界、`scene_block` prompt 块、`memory_content`）+ DB 区（active_scene 生命周期、`enter_scene`/`finish_scene`/`abort_scene`、`available_scenes`、`try_enter`、`settle_scenes` 统一入口）
- `game/events.py`：`settle_time` 新增 `state_scene` 参数与场景结算段（事件循环后先结束判定、再进入评估；场景推进并入统一时钟）；`apply_event` 返回 `start_scene`（effects 支持 `{"start_scene":"key"}`）
- `game/prompt.py`：组装新增「当前场景」块（名称/设定/目标/轮数；turns≥max_turns 追加收尾指令，不注入结束条件）；STATE 协议新增 `scene` 说明
- `routes/chat.py`：流前注入活跃场景；流后把 AI 标签 `scene` 交场景引擎；SSE 新增 `scene_update`；场景消息并入 `event_triggered.messages`
- `routes/scenes.py`（新）：`GET /scenes`（历史+可用清单）、`POST /scenes`（手动进入，调试）、`POST /scenes/end`（正常收尾 / `abort` 强制中止）
- `routes/state.py`：`active_scene` 改走 `scenes.public_active`（精简结构，不回场景设定原文）
- `seeds/loader.py` + `seeds/scenes.json`：场景种子装载（`apply_scene_seeds`，启动调用）
- `schemas.py`：`SceneEnterIn` / `SceneEndIn`；`config.py`：`SCENE_PROMPT_CHAR_BUDGET`、`SCENE_MEMORY_IMPORTANCE`
- `main.py`：注册 scenes 路由与种子装载

**前端**
- `SceneBanner.vue`（新）：场景名称/轮数/目标/「结束当前场景」按钮
- `Game.vue`：右栏接入 SceneBanner；`stores/chat.js`：处理 `scene_update` 并刷新状态；`stores/game.js`：`endScene`

**测试**：46 → **68 项**（新增 `tests/test_scenes.py`：可用性/轮数边界/场景块/记忆内容/对外结构）

## 六、M3.5 验证记录（2026-09-14）

- `unittest` 68 项全过；`npm run build` 通过
- httpx 端到端（临时档，已清理）：advance 自动进入 `date_first_outing`（开场消息入流）→ 手动结束（effects/记忆/`scene_done` flag/历史落库）→ 冷却期内手动进入 409 → 跳时段进入 `talk_rainy_night` → min_turns 内拒绝 AI 提前收尾 → 4 轮后 AI 收尾生效（总结写入记忆）→ `next_scenes` 解锁 `care_fever` → 下一次推进自动进入 → 中止记 aborted 且不写记忆
- 浏览器实测：场景面板显示正确（名称/第 1 轮/目标），点击结束 → 收尾消息上屏、面板回到「暂无进行中的场景」、属性实时刷新
- 说明：以上自检未调用真实模型；聊天路径的 `scene` 标签经直调 `_settle` 验证（真实模型 SSE 建议下次随手复验）

## 七、关键决策速查（M3.5 实现口径）

- **生命周期**：`save_flags.active_scene` 存 `{key,name,goal,prompt,turns,min_turns,max_turns,started_game_minutes,source}`；同一时刻仅 1 个活跃场景
- **进入评估**：每次结算（chat / advance / 手动事件）末尾统一评估，priority 高者先得；事件 `effects.start_scene` 指定 key 时只评估该场景（条件/once/冷却/花费仍校验）；**本次结算刚结束一幕则不接力进入**（下次结算再评估）
- **轮数**：仅对话结算 `turns+1`；显式推进不算轮
- **结束判定顺序**：AI 标签 `{"action":"end","summary":...}`（`turns>=min_turns` 才接受，min 内静默忽略并继续）→ `exit` 条件（服务端求值）→ `turns > max_turns` 强制；`turns>=max_turns` 时下一轮 prompt 注入收尾指令
- **结算内容**：effects（attrs/flags/unlock_events/unlock_scenes）→ `scene_logs(finished, summary, meta)` → `memories` 一条（category=relationship 用 relationship，否则 event；importance=7）→ 清 active → 写 `scene_done:<key>` + `next_scenes` 解锁为 `scene_unlocked:<key>`
- **中止（abort）**：记 `scene_logs(aborted)`，不应用 effects、不写记忆与收尾消息；cooldown 从最近结束（含中止）时刻计，once 只认 finished
- **开场/收尾消息**：均以 `role=event` 轻量消息入库（`meta.kind=scene_start/scene_end`），模板生成不耗 AI
- **场景花费**：`enter_cost.money` 扣款校验；`errors.advance_minutes` / `enter_cost.time_minutes` 并入统一结算（上限 24h），不递归触发新事件
- **手动结束**：不受 min_turns 限制（玩家/调试明确意图）；「结束当前场景」按钮已接

## 八、下一步 M4（记忆系统）建议顺序（PLAN 5.6）

1. `game/memory.py`：总结流水线（未总结 ≥20 条 / 手动 / 启动补跑；`memory_jobs` 条件更新抢占 running 实现 save 级互斥）
2. 检索注入：importance × 新近度全量 + 字符预算；`kind=relationship` 或 importance≥8 常驻
3. `routes/memories.py`：CRUD + 手动总结；prompt 组装插入「永久记忆」块
4. 前端 `MemoryPanel`（列表/编辑/归档/手动总结）
5. 场景结束记忆已在 M3.5 落 `memories`（event/relationship），M4 总结时注意不要把场景记忆重复抽取

## 九、环境坑与约定（踩过的雷）

- 服务控制台窗口**不能关**（关 = 停服）；请用 `快速启动.bat`（独立窗口）
- PowerShell 5.1 调 API 中文会乱码——接口测试统一用 `backend/.venv` 的 python + httpx，并设 `PYTHONIOENCODING=utf-8`
- mysql CLI：`key` 是保留字需反引号；该实例 `ANSI_QUOTES` 开启，字符串必须单引号
- SQLAlchemy pin ≥2.0.41（Py3.14）；属性数值列用 `Double`
- `SessionLocal` 为 `autoflush=False`：手动改 ORM 行后、依赖查询前需先 flush
- 流式阶段不写 DB；状态标签解析失败留痕 `meta.tag_debug`
- `save_flags` 读写用 `events.set_flag` / `scenes.get_active`（dict 值不加 "value" 包装）；场景 active 读旧格式时兼容 `{"value": {...}}`
- codebase-memory 图谱**已索引**本项目（项目名 `new-idea`，530+ 节点；M3.5 有新代码可重索引）
- 交流用中文；提交信息用泛化描述（AGENTS.md）；提交前建议先跑单测

## 十、给下一个会话的建议

- 动手前：读 `PLAN.md` + 本文件 → `git status`（M3.5 未提交）→ 建议先提交 M3.5 再开工 M4
- 后端改动需重启服务（未开 reload）；前端改动需 `npm run build`
- 验证习惯：先 `unittest` → 再 httpx 端到端（含 SSE）→ 最后浏览器实测
- 聊天验证注意选可用模型（aihubmix 的 `xiaomi-mimo-v2.5-free`），OpenRouter 免费额度可能已用尽
- 平衡数值已定稿（PLAN §10）；冷落规则/打工/礼物为 M5 实现时的数据依据
