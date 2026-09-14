# STATUS — 当前状态记录

> 更新时间：2026-09-14（M2 完成、全量审查修复完成、M3 未开工）
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
| M2 女主角刻画（内置设定书、prompt 深度注入、属性管理接口） | 已完成，**未提交**（见第五节） |
| M3 事件与时间（三类事件、随机每日判定、推进面板、事件种子） | 未开工（下一步，见第七节） |

## 三、运行方式

- 环境：Python 3.14（`backend/.venv`，uv 创建）；Node 24；MySQL 8
- 数据库密码：系统用户环境变量 `MYSQL_PASSWORD`（`new_idea` 库自动建库建表）
- 服务端口：**18730**（`APP_PORT` 可配）；启动后浏览器开 `http://127.0.0.1:18730`
- 启动：双击 `快速启动.bat`（缺 dist 会自动构建）；或手动：
  `cd backend; .venv\Scripts\python.exe main.py`
- 测试：`cd backend; .venv\Scripts\python.exe -m unittest discover -s tests`（21 项）
- 前端：改动后 `cd frontend; npm run build`（后端托管 dist）；开发模式 `npm run dev`（Vite 代理 18730）

## 四、数据现状（库内）

- 女主角：**小澄**（19 岁，你收留的女孩）——内置设定书 `backend/seeds/character.json`，启动时装载并以种子为准覆盖库记录；界面不暴露编辑
- 存档：仅 `id=6「雨夜」`（6 条消息，模型 `aihubmix:xiaomi-mimo-v2.5-free`）；其余测试档已清理
- 供应商（均为 `use_env_key` 模式，库内无明文密钥）：
  - `aihubmix` → `xiaomi-mimo-v2.5-free`（实测可用，环境变量 `AIHUBMIX_API_KEY`）
  - `openrouter` → `nvidia/nemotron-3-ultra-550b-a55b:free`（免费额度 50 次/天，每日 08:00 重置；环境变量 `OPENROUTER_API_KEY`）
- 属性定义：库内 8 条（affection/trust/mood/stamina/intimacy/dependence/vigilance/money）；**stamina 已停用**；money `ai_editable=false`、max 999999999；代码种子 `seeds/attributes.json` 现为 7 条（不含 stamina，库内旧行为停用状态）
- 其它密钥在系统环境变量：`DEEPSEEK_API_KEY`、`OLLAMA_API_KEY`（deepseek-chat 已弃用；Ollama Cloud 直连超时未采用）

## 五、未提交变更（含审查修复，数量见 git status）

功能块概览（相对 `44c7425`）：

- **M2 后端**：characters 全局化 + 旧库自动迁移（`db.py`）、`/api/character` 只读路由、属性定义 CRUD（界面不暴露）、prompt 深度注入（设定书全字段+阶段描述+参考台词）、属性数值 FLOAT→DOUBLE 迁移
- **内置设定书**：`seeds/character.json`（小澄完整设计）+ 启动装载；删除 `seeds/templates.json` 与模板接口
- **工程**：端口 18730、日志写 `backend/server.log`、SPA 路由回退、.env 增加 APP_HOST/APP_PORT
- **前端**：移除设定书编辑器/属性管理面板/模板交互；存档创建改为内置女主摘要；Game 显示关系阶段
- **全量审查修复（2026-09-14）**：模型改名/删除引用校验改为精确 key（供应商仍按前缀）、UI 关系阶段随对话刷新、SSE `time_update` 携带完整 virtual、中文输入法回车不误发送、空白存档名拦截、`tick_rule` 可置空、空正文不落库、重试重置思考链剥离器、流中止支持（切换页面自动取消）、`MYSQL_PASSWORD` 校验后移到 `db.py`（单测不再依赖该变量）
- **文档**：PLAN.md（单女主/内置设定书/三类事件等）、README.md

> 建议：下次开工前先提交这批变更（提交信息按 AGENTS.md 用泛化描述）。

## 六、关键决策速查（详见 PLAN 第 10 节）

- 单女主全局唯一（`characters` 与存档解耦）；存档 = 从头来过的周目
- 设定书与属性定义均为内置内容，游戏界面不暴露编辑；**模型配置保留**（配密钥必需）
- 事件三类：`random` 随机（每游戏日开始时判定一次，结果记 `save_flags`）/ `fixed` 固定（属性/flag 阈值）/ `manual` 手动（行动菜单主动选择，带 cost）；剧情链用 flag 串联；时段/日期/节日是条件不是类型
- 不做换装（文字描述）、不做体力/健康/伤病机制（纯数值属性）、内容默认无限制
- 时间与现实隔离（纯虚拟时钟）；`game/` 纯函数层配最小单测

## 七、下一步 M3（事件与时间）建议顺序

1. `game/events.py`：条件求值器（`period`/`date`/`game_day`/`attr`/`flag`，复用 PLAN 5.3 的 JSON 结构）
2. `game/clock.py` 扩展：跨日检测、时段边界工具
3. 三类触发：随机（跨日判定 + `save_flags` 防重复 + 冷却/once）、固定（阈值）、手动（cost 校验）
4. 事件注入对话：写 `event_logs` + `role=event` 消息 + prompt 情境块；SSE 增加 `event_triggered`
5. `/api/saves/{id}/advance` + 调试推进面板（+10m/+1h/+1d/跳时刻）
6. 为小澄写事件种子：每阶段 2–3 个 + 主线链「雨夜→噩梦→坦白→和解」
7. 单测：条件求值、跨日判定、冷却/once、钳制边界

## 八、环境坑与约定（踩过的雷）

- 服务控制台窗口**不能关**（关 = 停服）；`pythonw.exe` 启动不监听（已放弃）；请用 `快速启动.bat`（独立窗口）
- PowerShell 5.1 调 API：`Invoke-RestMethod` 中文 JSON 会乱码——接口测试统一用 `backend/.venv` 的 python + httpx
- mysql CLI：`key` 是保留字需反引号；该实例 `ANSI_QUOTES` 开启，字符串必须单引号（双引号会被当标识符）
- SQLAlchemy pin ≥2.0.41（Py3.14）；属性数值列用 `Double`（`Float` 丢精度）
- 流式阶段不写 DB（会话在流前/流后两端）；状态标签解析失败留痕 `meta.tag_debug`
- codebase-memory 图谱**未索引**本项目（需要时可 `index_repository`）
- 交流用中文；提交信息用泛化描述（AGENTS.md）

## 九、给下一个会话的建议

- 动手前：读 `PLAN.md` + 本文件 → 启动服务确认 18730 可用 → `git status` 看未提交变更
- 后端改动需重启服务（未开 reload）；前端改动需 `npm run build`
- 验证习惯：先 `unittest` → 再 httpx 端到端（含 SSE）→ 最后浏览器实测
- 聊天验证注意选可用模型（aihubmix 的 `xiaomi-mimo-v2.5-free`），OpenRouter 免费额度可能已用尽
