# 养成 — 网页版 AI 文字养成游戏

单女主、注重人物刻画的 galgame 式文字养成游戏（个人自用，不对外发布）。

核心循环：**对话 / 互动 → 属性变化 → 事件触发 → 性格演化 → 新的对话与事件**。时间与现实隔离，使用纯虚拟时钟；所有存档共用同一位女主角，每份存档从头开始这段关系。

## 功能一览

| 模块 | 说明 |
|---|---|
| 对话 | SSE 流式对话；模型回复经状态标签（STATE）驱动属性、心情与剧情标记 |
| 属性与关系 | 多属性、关系阶段、性格倾向（戒备 / 黏人 / 信赖 / 安定）随互动演化 |
| 虚拟时间 | 手动推进时间；属性随时间回归 / 衰减，跨日随机判定 |
| 事件 | 固定 / 随机 / 手动三类事件：打工、送礼、看电影、事件链、主动消息 |
| 场景 | 多轮剧情场景：设定注入、轮数上限、进入与结束结算、场景记忆 |
| 记忆 | 对话总结流水线自动提炼长期记忆，按重要度与新近度检索注入后续对话 |
| 经济 | 钱包收支、打工挣钱、礼物与消费、久未互动的冷落惩罚 |
| 存档 | 多周目并存，单档全量导出 / 导入备份 |
| 内容管理 | 角色书 / 事件 / 场景定义在线维护（修改持久生效、可一键恢复内置，支持对存档调试触发）、暗色 / 亮色主题 |

## 技术栈

- 后端：Python 3.14 / FastAPI / SQLAlchemy 2.0 + PyMySQL / MySQL 8 / OpenAI 兼容 SDK（SSE 流式）
- 前端：Vue 3 + Vite + Pinia + Vue Router
- 部署：后端托管前端 `dist`，`.bat` 一键启动；单用户无登录

## 目录结构

```
backend/
  main.py config.py db.py orm.py schemas.py helpers.py ai_client.py
  game/      clock.py tags.py attributes.py events.py scenes.py memory.py prompt.py
  routes/    saves.py chat.py state.py advance.py events.py scenes.py memories.py
             defs.py backup.py catalog.py character.py
  seeds/     character.json attributes.json events.json scenes.json loader.py
  tests/     test_game.py test_events.py test_scenes.py test_memory.py
             test_ai_client.py test_integration.py
frontend/
  src/       views/ components/ stores/ api/ router/ styles/
一键启动.bat  环境检查 / 前端构建 / 启动服务 / 打开网页
.env.example  环境变量模板
```

## 环境准备

1. 安装并启动 MySQL 8，确保账号可连接。
2. 数据库密码写入系统环境变量 `MYSQL_PASSWORD`，或复制 `.env.example` 为 `.env` 后在其中配置。数据库 `new_idea` 首次启动自动创建，无需手工建库。
3. 后端依赖（需已安装 uv）：

```powershell
cd backend
uv venv --python 3.14
uv pip install -r requirements.txt
```

4. 前端依赖与构建（需 Node 24）：

```powershell
cd frontend
npm install
npm run build
```

## 启动

双击 **`一键启动.bat`**：自动检查后端环境（缺失时创建）→ 前端源码有更新时自动重新构建 → 启动服务 → 等待就绪后打开浏览器 `http://127.0.0.1:18730`；若服务已在运行则直接打开网页。端口可用 `.env` 的 `APP_PORT` 修改。

手动启动：

```powershell
cd backend
.venv\Scripts\python.exe main.py
```

开发模式：

```powershell
# 终端 1：后端（热重载可选 $env:UVICORN_RELOAD="1"）
cd backend; .venv\Scripts\python.exe main.py

# 终端 2：前端（Vite 代理 /api → 127.0.0.1:18730）
cd frontend; npm run dev
```

> 后端改动需重启服务；前端改动需 `npm run build`（或使用开发模式）。

## 测试

```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests
```

共 143 项：纯函数单测 + 接口 / 数据库集成测试。集成测试使用独立数据库 `new_idea_test`，自动创建与清理，需本机 MySQL 可用。

## 使用流程

1. 首页「模型配置」：新建 OpenAI 兼容供应商（密钥可存库或读环境变量），添加模型并测试连通性。
2. 「新建存档」：选择对话模型创建周目。
3. 进入游戏：左侧对话，右侧查看关系阶段、属性、金钱、场景与事件；通过推进面板与互动菜单推进时间、打工、送礼。
4. 存档卡片「导出」将单个存档备份为 JSON；首页「导入存档」可恢复为新存档。
5. 「定义管理」在线维护事件 / 场景定义；「主题」切换暗色 / 亮色。

## 内置内容（种子）

- 女主角「小澄」：完整设定书（外貌 / 穿着 / 性格 / 说话风格 / 背景 / 关系史 / 秘密 / 四阶段语气等），默认内容来自 `backend/seeds/character.json`。
- 属性定义与事件 / 场景定义同为内置种子（`backend/seeds/*.json`），启动时装载入库；库内的 `enabled` 启停状态不受种子影响。
- **界面可改**：在「定义管理」中可编辑角色书、事件书与场景书；被修改过的内容会标记「已修改」，重启服务不再被种子覆盖，随时可点「恢复内置」回到种子内容。
- 未在界面修改过的内置定义，编辑对应 JSON 后重启服务即可同步更新。

## 数据管理

- 数据全部存放于 MySQL 数据库 `new_idea`。
- 需要清空数据时：停止服务后执行 `DROP DATABASE new_idea;`，下次启动自动重建（所有存档不可恢复，请先导出备份）。

## 开发提示

- 服务控制台窗口不能关闭（关闭即停止服务）。
- PowerShell 直接调接口中文易乱码，接口自检建议使用 `backend/.venv` 的 Python + httpx，并设置 `PYTHONIOENCODING=utf-8`。
- 属性数值列使用 `Double`；`SessionLocal` 为 `autoflush=False`，手动修改 ORM 行后、依赖查询前需先 flush。
- 流式对话阶段不写数据库；状态标签解析失败会留痕 `meta.tag_debug`。
