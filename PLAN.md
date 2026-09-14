# 计划：网页版 AI 养成游戏（个人向）

> 纯网页端、AI 驱动的文字养成游戏。个人自用，不发布；内容不做分级限制（默认无限制），角色设定为明确成年。
> 核心循环：**对话/互动 → 属性变化 → 事件触发 → 性格演化 → 新对话与新事件**
> 时间与现实完全隔离：纯虚拟时钟，由对话/行动推进；经济系统（金钱/打工/消费）作为互动燃料。
> **定位：单女主、深刻画的 galgame 式体验（方向参考 Teaching Feeling）。女主角全局唯一（跨存档共享设定书）；存档 = 从头来过的周目。核心日常循环：照顾/陪伴互动 → 状态与关系渐变（警戒降、信任升）→ 时间推进 → 阶段解锁新互动与特殊事件。优先角色刻画深度，分支/日程等玩法后置。**

- 状态：M1 骨架、M2 女主角刻画、M3 事件与时间、M3.5 多轮场景、M4 记忆系统已完成；M5 行动与经济待启动
- 项目目录：`D:\Projects\New Idea`（代码直接建于此目录；本文档为唯一真相源）
- 本文档随决策更新

---

## 1. 范围

**本期做**：单女主角色设定书（深度刻画）、属性、事件、虚拟时间、对话引擎、记忆系统（底层骨架）、日常互动行动（含经济）。
**本期不做**：Live2D、TTS 语音、小游戏、换装（外观仅文字描述）、体力/健康/伤病机制、多角色阵容、发布合规（个人自用）。
**边界**：内容默认无限制（个人自用），可选的内容风格指令由用户自写；角色为明确成年设计。

## 2. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.14 / FastAPI（3.12+ 兼容） |
| ORM | SQLAlchemy 2.0（同步，pin ≥2.0.41 已验证支持 Py3.14）+ pymysql |
| 数据库 | MySQL 8 |
| AI | OpenAI 兼容 SDK（DeepSeek/Qwen 等），SSE 流式 |
| 前端 | Vue 3 + Vite + Pinia + vue-router，手写 CSS 变量主题 |
| 部署 | 后端托管 `frontend/dist`，`.bat` 一键启动；单用户无登录 |

**不引入 Redis**：即时记忆是组装视图非独立存储；单机场景 MySQL 足够；异步总结用 BackgroundTasks。

## 3. 架构

```
浏览器 (Vue3 SPA)
 ├─ 存档宫格 / 游戏主界面 / 管理弹层
 ├─ Pinia: game(属性·事件·消息·时间·金钱) · chat(流式) · catalog(模型) · ui(主题)
 └─ sse.js: 流读取（参考 Nehchat，按 Vue composable 重写）
        │ HTTP / SSE
FastAPI
 ├─ routes/  saves · chat(SSE) · state · events · advance · defs · memories · catalog
 ├─ game/    clock(虚拟时钟/推进结算) · attributes(数值) · events(触发引擎)
 │           prompt(提示词组装) · tags(状态标签解析) · memory(总结/检索)
 ├─ ai_client.py（复用 Nehchat：重试/思考链剥离 + 新增状态标签剥离）
 └─ SQLAlchemy ORM → MySQL 8
```

## 4. 数据模型

| 表 | 关键字段 | 说明 |
|---|---|---|
| `saves` | id, character_id(FK), name, status, model_key, game_minutes, last_summarized_message_id, settings JSON | 周目存档；model_key 为目录模型引用（`slug:model_id`）；game_minutes 为虚拟时钟（累计分钟）；settings 存日历、推进、冷落、生成参数 |
| `characters` | id, name, age, relation, persona JSON, freeform | 女主角设定书（全局唯一，跨存档共享）；age 后端校验 ≥18 |
| `attribute_defs` | id, key, name, category, min, max, default_value, tick_rule JSON, ai_editable, sort, enabled | 属性定义；ai_editable=false 时禁止 AI 在状态标签改动（如金钱）；key 创建后不可改（仅启停），避免孤儿属性值 |
| `attribute_values` | save_id, attr_key, value, updated_at | 每存档属性值（联合主键） |
| `event_defs` | id, key, name, category, trigger JSON, cost JSON, effects JSON, prompt_template, once, cooldown_minutes, priority, enabled | 事件定义；category 三类：random / fixed / manual；manual 配 cost 供手动触发 |
| `event_logs` | id, save_id, event_id, status, content, meta JSON, game_minutes_at, triggered_at | 事件历史；记录触发时虚拟时刻与收支 |
| `scene_defs` | id, key, name, category, enter_trigger JSON, enter_cost JSON, scene_prompt, goal, min_turns, max_turns, exit JSON, effects JSON, next_scenes JSON, once, cooldown_minutes, priority, enabled | 多轮场景定义；进入/结束条件复用事件条件求值器 |
| `scene_logs` | id, save_id, scene_key, status(started/finished/aborted), summary, meta JSON, game_minutes_at, started_at, finished_at | 场景历史；结束写总结与结算 |
| `messages` | id, save_id, role(user/assistant/system/event), content, meta JSON, game_minutes_at, created_at | 对话；meta 存属性变化/时间推进/事件关联/状态标签解析失败原文 |
| `save_flags` | save_id, key, value JSON | 事件链/剧情标记 + 当前活跃场景 active_scene（联合主键） |
| `memories` | id, save_id, kind, content, importance, source_from_id, source_to_id, embedding(可空), last_recalled_at, recall_count, status, created_at | 永久记忆 |
| `memory_jobs` | id, save_id, status, error, created_at | 总结任务（pending/running/done/failed）；save 级互斥防并发重复总结，失败与中断任务启动时补跑 |
| `providers` | id, slug(创建后不可改), display_name, base_url, api_key, use_env_key, api_key_env, sort_order | 供应商（照 Nehchat）；slug 为模型 key 前缀；密钥双模式（存库/环境变量） |
| `catalog_models` | id, provider_id(FK 级联删除), model_id, display_name, UNIQUE(provider_id, model_id) | 目录模型；引用一律用 `slug:model_id` |

**默认属性种子**：好感度、信任、心情、亲密、依赖、警戒、金钱(money)。

**属性原则**：只做通用数值属性，不建体力/健康/伤病等身体状态机制；属性定义由种子/管理接口维护（界面不暴露编辑，属性值正常展示），由状态标签、时间 tick、事件/行动效果修改。

## 5. 核心系统

### 5.1 女主角设定书（单女主，内置内容）

- **定位**：全局唯一女主角，完全设计好的内置内容，不在游戏界面暴露编辑；存档是从头开始的周目，开局即按设定书展开这段关系的重演
- **真相源**：`seeds/character.json`，启动时装载（以种子为准覆盖库中记录）；修改设定 = 改种子文件后重启
- **深度字段**：基本信息（名字/年龄/称呼玩家的方式）、外貌描述（含日常穿着文字描述）、性格（多维度）、说话风格（语气/句长/口癖/常用词/禁用词）、喜好/厌恶、背景故事、与玩家的关系史、日常（作息/职业/兴趣）、秘密与敏感点、阶段变化（陌生→熟悉→亲近→依恋 各自的行为与语气描述）、参考台词（few-shot 示例，3–10 条）
- **注入**：按当前关系阶段选取对应描述注入 prompt；参考台词作为 few-shot 附在系统提示后
- 外观与穿着不做换装系统，以设定书 + AI 文字描述承载

### 5.2 属性系统

- `tick_rule` 模式：`decay`（衰减）/ `recover`（恢复）/ `regress`（回归中值），按**游戏小时**结算（仅在时间推进时）
- 金钱（money）：resource 类，min 0，无 tick，ai_editable=false
- 冷落规则：按虚拟时间重定义，见 5.4
- 变化来源：AI 状态标签（钳制到 min/max + 单轮变化上限）、时间推进 tick、事件/动作效果

### 5.3 事件与场景系统

- **内容原则**：角色固定后，事件/场景像 galgame 一样针对内置女主角专门设计（贴合其背景、性格与关系阶段），由种子维护；触发条件用属性阈值表达阶段门槛，剧情链用 flag 串联
- **三类事件**：
  - `random` 随机事件：每个游戏日开始时做一次判定（每日一次，判定结果记入 `save_flags` 防重复），命中后在当天注入；参数含每日概率、冷却、once、可选的时段/属性门槛
  - `fixed` 固定事件：属性/flag 达到阈值即触发（阶段解锁、剧情链节点）；纯条件判定，不含概率
  - `manual` 手动事件：行动菜单直接选择（主动交互），带 cost、条件校验与效果
- 剧情链不单设类型：由固定事件的 flag 条件串联（前序事件写 flag，后续事件以 flag 为门槛）
- 触发条件 JSON 对三类通用（`period`/`date`/`game_day`/`attr`/`flag` 等）；时段/日期/节日作为条件而非独立类型
- 触发条件 JSON 示例：

```json
{"all":[
  {"type":"attr","key":"affection","op":">=","value":30},
  {"type":"period","in":["night"]},
  {"type":"game_day","op":">=","value":3}
], "chance":0.15}
```

- 效果 JSON：`{"attrs":{"mood":10,"money":-80},"advance_minutes":180,"flags":{"unlocked_movie":true},"unlock_events":["movie_night"]}`
- cost JSON（manual 专用）：`{"money":80,"time_minutes":180}`
- 时机：每次交互后 + 时间推进结算时（含跨日随机判定）+ 手动触发；离线世界静止，无需页面加载评估
- manual 事件：点击 → 校验条件与余额 → 扣 cost → 注入场景 prompt 由 AI 叙述，落 `event_logs` 与消息
- 管理界面：事件/场景定义 CRUD + 启停 + 调试手动触发（**推迟**：当前以种子文件维护，接口与编辑器列入 M6 之后）

**多轮场景（scene）**：

- **定位**：持续多轮的剧情单元（约会、旅行、照顾生病、吵架冷战）；与事件同为"注入 prompt 由 AI 演出"，但跨越多轮、带目标与收尾，解决一次性事件撑不起的剧情
- **定义**（`scene_defs`）：进入条件（复用事件条件 JSON）、进入 cost（可选）、场景设定（地点/参与人/氛围）、本幕目标 goal、轮数范围 min/max、结束条件 exit、结束结算 effects、可衔接 next_scenes（场景链）、once/冷却
- **生命周期**：
  1. **进入**：每次交互后 / 时间推进结算时 / 手动评估进入条件；**同一时刻仅 1 个活跃场景**，已有活跃场景时候选跳过；写 `save_flags.active_scene = {key, turns:0, goal, started_game_minutes}`，写 `scene_logs(started)`，并注入一条轻量 `event` 消息（场景标题 + 环境一句，模板生成、不耗 AI）
  2. **持续**：每轮 prompt 注入「当前场景」块——场景名、地点氛围、本幕目标、已进行轮数（不注入结束条件，防 AI 应付）；`turns` 每轮 +1
  3. **结束**（任一触发）：AI 在 STATE 标签输出 `"scene":{"action":"end","summary":"..."}`；`turns >= max_turns` 时下一轮注入收尾指令、回复落库后强制结算；或 exit 条件满足由服务端判定；`turns < min_turns` 时忽略 AI 的提前收尾
  4. **结算**（同一事务）：应用 effects → 写 `scene_logs(finished, summary)` → 生成场景记忆（kind=event/relationship，importance 可配）→ 清 `active_scene` → 解锁 next_scenes；调试中止记 aborted（不应用 effects 与记忆）
- **进入评估时机**：每次结算（对话/推进/手动事件）末尾统一评估；本次结算中刚结束一幕则不再接力进入（下一次结算再评估），防止连续跳幕
- **与事件系统互通**：事件 effects 可 `{"start_scene":"..."}`；场景结束 effects 可触发/解锁事件——事件链升级为「事件 ⇄ 场景」混合链
- **手动干预**：主界面显示当前场景（名称 + 第几轮 + 目标），支持「结束当前场景」（正常收尾）与调试强制进入/中止（`scene_logs` 记 aborted）
- **配置项**：`SCENE_MAX_TURNS_DEFAULT` / 场景块字符预算 / 场景结束记忆 importance 默认值

### 5.4 时间系统（全虚拟时钟）

- **设计原则**：与现实时间完全隔离；时间只在对话/行动/事件推动下前进；离线时世界静止（无回归快进、无后台结算、无轮询）
- **存储**：`saves.game_minutes`（自开局累计的虚拟分钟数），由它换算虚拟月日与时段
- **日历显示**：虚拟月日 + 时段（如「5 月 12 日 · 晚上」）；起始日期可配（默认 5 月 1 日 08:00），月长 30 天；节日/季节表为虚拟日历 JSON
- **时段**：清晨/上午/中午/下午/傍晚/晚上/深夜（映射日内分钟区间）
- **推进来源**（仅此三类）：
  1. AI 状态标签 `"time":{"advance_minutes":N}`；服务端校验并钳制（如 0–180 分钟/条）
  2. 显式动作（睡觉、等待、打工），动作自带目标时刻或时长
  3. 事件效果（effects.advance_minutes）
- **兜底**：AI 未输出推进量时按默认值推进（默认 +10 分钟，可配），保证时钟不卡死
- **跳时后的上下文同步**：跨时段/跨日推进后，下轮 prompt 的「当前时间」取新虚拟时刻；非对话来源的推进（打工/manual 事件/调试面板）额外注入一条 system 说明（如「时间已推进至 5 月 3 日 · 晚上」），防止 AI 时间认知错乱
- **结算**：只在推进发生时按块结算——属性 tick（按游戏小时）、时段切换、跨时段大跳按中间时刻**有序**评估事件与场景进入条件；单次跳时上限（如 24 小时）+ 单次评估事件数上限，超出只入日志不注入
- **事件条件全部基于虚拟时钟**：`period` / `date` / `game_day` / `attr` / `flag` / `距上次事件的虚拟时长`；"时间 + 好感"组合触发直接可用
- **冷落规则（重建）**：两次互动之间推进 ≥N 游戏日（默认 3）且期间无对话 → 好感微降；参数可配
- **主动消息**：时间推进越过时点触发的事件（如"晚上 8 点她来消息"），随推进 SSE 推送前端；无需后台常驻
- **调试面板**：+10m / +1h / +1d、跳到指定时刻（取代原 TIME_SCALE）
- `messages` / `event_logs` 记录当时虚拟时刻，供"最近事件"、剧情回看与 prompt 使用
- **配置项**：`TIME_DEFAULT_ADVANCE`（默认推进）/ `TIME_MAX_ADVANCE_PER_MESSAGE` / `TIME_MAX_JUMP_HOURS` / 日历与冷落参数（存档 settings）

### 5.5 对话引擎（SSE）

- **Prompt 组装顺序**：系统规则 → 角色人设 → 属性+性格阶段 → 虚拟时间/节日 → 当前场景（如有）→ 激活事件情境 → 永久记忆注入 → 内容风格指令（可选，用户自写） → 最近 M 条原文 → 状态标签协议说明
- **状态标签协议**：模型回复末尾输出 `<<<STATE {"attrs":{"affection":2},"mood_label":"开心","flags":{},"time":{"advance_minutes":30},"scene":{"action":"end","summary":"..."}} STATE>>>`（完整形态；当前已启用 `attrs` 与 `time`，非 dict 结构静默忽略；`flags`/`mood_label` 属 M5，`scene` 属 M3.5）；后端流式剥离（仿 `_ThinkStripper`，注意标签可能在末尾且跨 chunk，需 hold-back + 流结束 flush 解析）；应用钳制后的数值与推进量；`scene` 动作交场景结算（受 min_turns 约束）；解析失败静默忽略
- **落库事务边界**：一次回复的全部写入（assistant 消息 + 属性钳制结果 + 时间推进 + tick + 事件/场景结算）在流结束后同一事务提交；客户端中途断流时保留已生成文本并照常结算（meta 标记 interrupted）
- **sync ORM 使用规则**：流式阶段不做 DB 写；DB 访问集中在流前（组装上下文）与流后（结算落库）两端，中间不碰库，避免阻塞事件循环；确需中途写时用 run_in_threadpool 包装
- **标签调试留痕**：解析失败或未输出状态标签时，把回复原文尾部存入消息 meta（不展示给用户），供调试 prompt 用
- **组装 API 消息时**：DB 里的 `role=event` 需映射为 system 或并入上下文（OpenAI 兼容协议只认 system/user/assistant）
- **SSE 事件**：`chunk` / `state_update` / `event_triggered` / `scene_update`（进入/轮数/结束）/ `time_update` / `done` / `error`

### 5.6 记忆系统（两层）

| | 即时记忆 | 永久记忆 |
|---|---|---|
| 本质 | 组装视图（不落独立存储） | LLM 总结产物（`memories` 表） |
| 来源 | 最近 M 条消息 + 最近 N 小时事件（**虚拟时间**）+ 当前状态 | 未总结消息/事件的抽取条目 |
| 生命周期 | 随窗口滑动，旧的被压缩进永久记忆 | 长期保留，可编辑/归档 |

**总结流水线**：

```
触发（未总结 ≥20 条 / 手动 / 启动补跑；"空闲 ≥30 分钟"为技术调度，可选保留）
  → 取 last_summarized_message_id 之后的消息 + 期间事件日志
  → LLM 结构化抽取 [{kind, content, importance}]（附相似已有记忆供判断新增/更新）
  → 去重合并 → 写 memories → 更新 last_summarized_message_id
```

- kind：`fact` / `event` / `relationship` / `promise`；importance 1–10
- 异步执行（BackgroundTasks），失败记 `memory_jobs` 下次重试，不阻塞对话；执行前用条件更新抢占 `running` 状态（save 级互斥），防止两次对话并发触发重复总结
- 自动触发在对话流后结算完成时登记任务（约当响应结束执行）；手动总结同步等待结果；启动时中断的 running 任务回退 pending 补跑；总结模型取 `MEMORY_MODEL`，空则用存档主对话模型
- 检索按「重要性 × 新近度」打分，核心记忆（`relationship` 或 importance ≥ 8）常驻预算；注入同时更新 `last_recalled_at` / `recall_count`

**检索（三级递进）**：

1. 重要性 × 新近度全量注入（字符预算截断）— MVP
2. MySQL ngram 全文索引关键词匹配 — MVP（可后置）
3. embedding 向量 top-K（SiliconFlow bge-m3）— 后置可选

**核心记忆**：`kind=relationship` 或 `importance ≥ 8` 永远注入。

**配置项**：`MEMORY_TRIGGER_TURNS` / `MEMORY_CHAR_BUDGET` / `MEMORY_MODEL`（总结可单独用便宜模型）/ `MEMORY_MAX_MESSAGES_PER_JOB` / `MEMORY_SUMMARY_MAX_TOKENS` / `MEMORY_PROMPT_CHAR_BUDGET`；即时记忆窗口取 `CHAT_HISTORY_MESSAGES`，`MEMORY_IDLE_MINUTES` 保留未启用；prompt 各块（属性/事件/记忆）分别设字符预算。

### 5.7 性格演化

- 阶段：陌生 → 熟悉 → 亲近 → 依恋；倾向由「依赖/信任比 + 行为计数」推导
- 每阶段/倾向的行为与语气描述取自设定书阶段字段，未填写时用通用模板兜底

### 5.8 行动与互动（含经济）

- **定位**：行动面板是 TF 式日常循环的核心入口——陪伴/照顾/触碰/外出/送礼/打工等互动全部由 `event_defs`（manual 类型 + cost + effects + prompt_template）数据驱动，新增互动只需加数据，无需改代码
- **金钱**：保留属性 `money`（resource 类；min 0；无 tick；`ai_editable=false`）。AI 可见可提及，但不能在状态标签里改钱；改动只来自动作/事件/调试。初始金额取属性默认值
- **打工**（暂最简）：确定性动作——消耗虚拟时间（如 4 小时）→ 加钱 → 写一条固定模板的 `event` 消息入库；不走 AI、不耗 token。条目数据驱动（event_defs），将来可加"家教/外卖"等
- **付费手动事件**：`event_defs` 的 `manual` 类型 + `cost` + `prompt_template`。点击时校验条件与余额 → 扣钱扣时 → 场景注入对话由 AI 叙述；不足则按钮禁用并提示。承载逛街、看电影、吃饭等
- **送礼**：付费 manual 事件；好感为固定配置值；每个礼物带独立 `prompt_template`，用于触发不同对话/场景
- **外观与穿着**：无换装系统，穿着以设定书与 AI 文字描述承载
- **身体状态**：不建体力/健康/伤病机制，一切状态用普通属性表达
- **记录与展示**：不建独立流水表，收支历史由 `event_logs` 承载；前端右栏加钱包小板块（余额 + 打工入口 + 最近收支）

### 5.9 模型配置（照 Nehchat 目录设计）

- **两层结构**：`providers`（供应商）+ `catalog_models`（其下模型）；一切引用统一用字符串 key `slug:model_id`（存档的 `model_key`、总结模型配置同）
- **供应商字段**：slug（小写字母/数字/`-`/`_`，创建后不可改）、显示名、base_url（须 `http(s)://`，存前去尾斜杠）、api_key、`use_env_key` + `api_key_env`、排序
- **密钥双模式**：直接存库 or 运行时读环境变量；对外接口只返回 `has_api_key` / `key_ready`，**永不回传明文**；运行时 `resolve_secret()` 解析，环境变量缺失时报 `missing_api_key`；无鉴权本地端点用占位 key 兜底
- **删除保护**：被存档（或总结模型配置）引用的 provider/model 禁止删除，返回 409 并提示占用位置
- **连通性测试**：`POST /api/providers/{id}/models/{mid}/test` 发送 hello，返回 ok / latency_ms / preview / error，前端模型行内展示结果
- **运行时解析**：`get_runtime()` → `{model_id, base_url, api_key, max_tokens}`，对话与总结共用；生成参数（temperature 等）存存档 `settings`，默认值由 `/api/default-params` 提供
- **总结模型**：`MEMORY_MODEL` 用同一目录 key，默认同主对话模型，可单独配便宜模型
- **前端**：ModelCatalogModal = 左侧供应商列表 + 右侧表单（内嵌模型行增删/改名 + 测试按钮）；交互照 `catalog.js`（draft 模型行、未保存不可测试）
- **单用户简化**：去掉 Nehchat 的 user_id 多租户列与迁移逻辑，其余照搬

## 6. 前端设计

- 视图：`Home`（存档宫格）、`Game`（主界面）
- Game 布局：顶栏（虚拟日期·时段·节日·设置·推进入口）｜中央（角色状态卡 + 对话流 + 输入区）｜右栏（属性面板+飘字、钱包板块、行动面板、事件面板）
- 组件：ChatStream、MessageBubble、StatusBars、SceneBanner（当前场景条：名称/轮数/目标/结束）、WalletPanel、ActionPanel（行动菜单：日常互动/送礼/打工）、EventCard、EventDefEditor、SceneDefEditor、AdvancePanel（调试）、MemoryPanel、ModelCatalogModal、ThemeModal、Toast
- 参考 Nehchat 重写（非直接复制）：`sse.js`、`api.js` 指数退避、主题/弹层/Toast、catalog 交互模式；源码为 vanilla JS + 全局 state，一律按 Vue composable + Pinia 重写

## 7. API 一览（要点）

| 方法 | 路径 | 说明 |
|---|---|---|
| CRUD | `/api/saves` | 存档管理（含选模型 model_key、生成参数） |
| POST | `/api/saves/{id}/chat` | SSE 对话（含推进结算+事件评估） |
| GET | `/api/saves/{id}/state` | 属性+虚拟时间+激活事件+当前场景+金钱 |
| POST | `/api/saves/{id}/advance` | 显式推进时间（动作/调试） |
| GET/POST | `/api/saves/{id}/events` | 事件日志（GET）；手动触发见下一行 |
| POST | `/api/saves/{id}/events/{key}/trigger` | manual 事件触发（校验 cost） |
| GET/POST | `/api/saves/{id}/scenes` | 场景历史 / 手动进入（调试） |
| POST | `/api/saves/{id}/scenes/end` | 手动结束当前场景（正常收尾） |
| CRUD | `/api/attribute-defs` | 属性定义管理（`/api/event-defs`、`/api/scene-defs` 推迟，见 §5.3） |
| GET/POST/PATCH/DELETE | `/api/saves/{id}/memories` | 记忆管理 |
| POST | `/api/saves/{id}/memories/summarize` | 手动总结 |
| GET | `/api/character` | 女主角设定书（内置内容，只读） |
| GET/POST | `/api/providers` | 供应商列表 / 新建 |
| PATCH/DELETE | `/api/providers/{id}` | 编辑 / 删除（被引用时 409） |
| POST | `/api/providers/{id}/models` | 添加目录模型 |
| PATCH/DELETE | `/api/providers/{id}/models/{mid}` | 编辑 / 删除（被引用时 409） |
| POST | `/api/providers/{id}/models/{mid}/test` | 连通性测试（hello） |
| GET | `/api/models` | 扁平模型列表（选择器/总结配置用） |
| GET | `/api/default-params` | 默认生成参数 |

## 8. 目录结构

```
New Idea/（= D:\Projects\New Idea）
├─ backend/
│  ├─ main.py config.py db.py orm.py schemas.py ai_client.py
│  ├─ game/  clock.py attributes.py events.py scenes.py prompt.py tags.py memory.py
│  ├─ routes/ saves.py chat.py state.py events.py scenes.py advance.py defs.py memories.py catalog.py
│  └─ seeds/ 内置女主角·默认属性·事件·场景 JSON
├─ frontend/
│  └─ src/ main.js App.vue stores/ api/ views/ components/ styles/
├─ .env  PLAN.md  README.md  快速启动.bat  重置启动.bat
```

## 9. 里程碑

| 阶段 | 内容 | 验证标准 |
|---|---|---|
| M1 骨架 | ORM 建表+种子、存档 CRUD、模型目录（照 5.9）、SSE 对话闭环、Vue 骨架（先用 curl 打通 SSE+落库，再接前端） | 建存档→配目录并连通测试→选模型→流式聊天并落库 |
| M2 女主角刻画 | 内置设定书种子（完整设计）+ 启动装载、prompt 深度注入（阶段描述 + 参考台词）、属性定义管理接口、属性面板实时变化 | 改种子即时影响语气与行为；阶段描述随关系切换；聊天驱动属性变化、重启后保持 |
| M3 事件与时间 | 虚拟时钟+推进协议（AI/动作/兜底钳制）、虚拟日历/时段/节日、三类事件引擎（每日随机判定 / 阈值固定 / 手动+cost）、为女主角设计的事件种子集（阶段化+剧情链）、调试推进面板、事件注入对话 | 对话与推进面板均能推动时间；跨日随机判定每日仅一次；阈值事件与剧情链按设计生效；AI 推进量被正确钳制 |
| M3.5 多轮场景 | scene_defs 定义、进入/持续/结束/结算全生命周期、STATE 标签扩展、场景 prompt 注入、SceneBanner 与场景定义管理、种子场景 2–3 个 | 触发场景→多轮目标与轮数持续生效→AI/上限自然收尾→结算与场景记忆落库；同时仅一个活跃场景；min_turns 内拒绝提前收尾 |
| M4 记忆系统 | 总结流水线、记忆管理面板、检索注入 | 达到阈值自动总结；记忆影响后续对话 |
| M5 行动与经济 | 行动面板（数据驱动日常互动：陪伴/照顾/外出）、打工、付费手动事件（逛街/看电影）、送礼（专属对话）、冷落（虚拟时间版）、性格演化、主动消息（推进触发）、事件链 | 行动菜单可增条目即生效；打工赚钱→消费送礼→触发专属对话；推进越过时点收到主动消息；互动间隔过大好感下降 |
| M6 打磨 | 导出备份（建议 M2 后即做轻量导出）、主题、向量检索（可选）、事件/场景定义管理界面、README | 完整备份可恢复 |

## 10. 已定 / 待定

**已定**：

- 单女主全局唯一设定书（characters 与存档解耦，存档引用 character_id，可从头开新周目）；整体方向参考 Teaching Feeling 的日常照顾循环（互动 → 状态与关系渐变 → 时间推进 → 阶段解锁）；优先角色刻画深度，分支/日程等玩法后置
- 不做换装（外观仅文字描述）；不建体力/健康/伤病机制，一切状态用通用数值属性表达
- 设定书与属性定义均为内置内容：游戏界面不暴露编辑（模型配置保留）；设定书真相源为 `seeds/character.json`
- 内容不做分级限制（默认无限制）；可选的内容风格指令由用户自写，引擎不内置
- 个人向不发布；无账号单用户；多存档；ORM MySQL；Vue3；无 Redis；纯文本（Live2D/TTS 后置）
- 时间与现实完全隔离：纯虚拟时钟、行动/AI/事件驱动、离线零行为、AI 未输出时默认推进、冷落按虚拟时间、显示虚拟月日+时段
- 记忆阈值 20 条 / 30 分钟（30 分钟为技术调度）；检索先做重要性+新近度+关键词
- 经济：金钱为保留属性且 AI 不可改；打工纯时间换钱（暂不涉体力）；付费手动事件；礼物固定好感+专属对话模板；不建流水表，右栏小板块展示
- 多轮场景：scene_defs + save_flags.active_scene + scene_logs；每轮注入场景块（含轮数）；结束由 AI 标签 / min-max 轮 / exit 条件判定，min_turns 内拒绝提前收尾；结束同事务结算并生成场景记忆；同时仅一个活跃场景；事件 ⇄ 场景可互相衔接
- 事件三类：随机（每游戏日开始时一次判定，结果记 save_flags）、固定（属性/flag 阈值触发）、手动（行动菜单主动选择，带 cost）；剧情链用 flag 串联；时段/日期/节日作为条件而非独立类型
- 模型配置照 Nehchat：providers/catalog_models 两层目录 + `slug:model_id` 引用 + 密钥双模式（存库/环境变量）+ 对外永不回明文 + 删除引用保护 + hello 连通测试；单用户去掉多租户；总结模型同目录可选
- 工程约定：流结束单事务落库、流式阶段不写 DB、总结任务 save 级互斥、属性 key 不可改（仅启停）、状态标签解析失败留痕 meta；同一存档的结算事务进程内串行（流后结算 / 推进 / 手动事件共用）
- 兼容：SQLAlchemy pin ≥2.0.41（支持 Py3.14）；「她的日记」本期不做（对核心循环无贡献，留作将来）
- 测试：`game/` 纯函数层（clock/events/tags）配最小单元测试，覆盖时间换算、条件评估、钳制边界
- 项目根目录 `D:\Projects\New Idea`；Python 3.14（3.12+ 兼容，与 Nehchat 环境一致）
- **平衡数值定稿（原待定 1，2026-09-14）**：推进默认 10 分钟/条、上限 180 分钟/条、单跳 24 小时、目标跳最多 60 天（现有 config 值不变）；打工 4 小时 → +120（时薪 30）；礼物两档：小礼物 ¥80 / 好感 +2，大礼物 ¥300 / 好感 +5；手动事件价格沿用种子（火锅 80 / 书店 60 / 连衣裙 300）；冷落阈值 3 游戏日无对话 → 好感 -1/日，单次上限 -5。参数落 `backend/config.py`（`WORK_*` / `GIFT_TIERS` / `NEGLECT_*`），M5 直接引用

**待定**：

- 暂无（内容种子清单可在 M5 按上述价目扩充）
