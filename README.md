# 养成 — 网页版 AI 养成游戏

纯网页端、AI 驱动的文字养成游戏（个人自用）。核心循环：**对话/互动 → 属性变化 → 事件触发 → 性格演化 → 新对话与新事件**。时间与现实完全隔离，使用纯虚拟时钟。

详细设计见 [PLAN.md](PLAN.md)（唯一真相源）。

## 技术栈

- 后端：Python 3.12+ / FastAPI / SQLAlchemy 2.0 + pymysql / MySQL 8 / OpenAI 兼容 SDK（SSE 流式）
- 前端：Vue 3 + Vite + Pinia + vue-router
- 部署：后端托管 `frontend/dist`，`.bat` 一键启动；单用户无登录

## 目录结构

```
backend/
  main.py config.py db.py orm.py schemas.py helpers.py ai_client.py
  game/     clock.py tags.py attributes.py events.py scenes.py memory.py prompt.py
  routes/   saves.py chat.py state.py advance.py events.py scenes.py memories.py defs.py catalog.py character.py
  seeds/    内置女主角设定书、默认属性与事件定义 JSON
  tests/    game/ 纯函数层单元测试
frontend/
  src/      views/ components/ stores/ api/ styles/ router/
```

## 环境准备

1. MySQL 8 已启动；密码写入系统环境变量 `MYSQL_PASSWORD`（或项目根 `.env`）。
2. 复制 `.env.example` 为 `.env` 并按需修改（端口、库名默认为 `18730` / `new_idea`）。
3. 后端依赖与虚拟环境：

```powershell
cd backend
uv venv --python 3.14
uv pip install -r requirements.txt
```

4. 前端构建（首次或前端改动后）：

```powershell
cd frontend
npm install
npm run build
```

## 启动

- 日常启动：双击 `快速启动.bat`（自动检查环境 → 启动服务 → 打开浏览器 `http://127.0.0.1:18730`）。
- 重置数据：双击 `重置启动.bat`（二次确认后删除数据库并重建）。

## 开发模式

```powershell
# 终端 1：后端（热重载可选 $env:UVICORN_RELOAD="1"）
cd backend; .venv\Scripts\python.exe main.py

# 终端 2：前端（Vite 代理 /api → 127.0.0.1:18730）
cd frontend; npm run dev
```

## 测试

```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests
```

## 使用流程

1. 首页「模型配置」：新建供应商（OpenAI 兼容接口，密钥可存库或读环境变量），添加模型并「测试」连通性。
2. 「新建存档」：选对话模型并创建周目；所有存档共用同一位女主角，从头开始这段关系。
3. 进入游戏：对话驱动属性与虚拟时间；右侧面板展示关系阶段、属性与金钱。

## 女主角设定书（内置内容）

- 完全设计好的内置角色，不在游戏界面暴露编辑；真相源为 `backend/seeds/character.json`，启动时自动装载（以种子为准覆盖库中记录）。
- 修改设定：编辑该 JSON 后重启服务。
- 深度字段：外貌/穿着/性格/说话风格/喜好/背景/关系史/日常/秘密/四阶段语气/参考台词。
- 属性定义与事件同为内置种子（`backend/seeds/attributes.json`、`backend/seeds/events.json`），启动时以种子为准覆盖入库；改完重启生效（`enabled` 启停状态不受种子影响）。

## 当前进度

- 已完成：M1 骨架（数据模型建表与种子、存档 CRUD、模型目录、SSE 对话闭环、状态标签协议、Vue 基础界面）；M2 女主角刻画（内置设定书种子与启动装载、prompt 深度注入、属性定义种子与管理接口）；M3 事件与时间（虚拟时钟推进与属性 tick、三类事件引擎与事件种子、推进面板与互动菜单）；M3.5 多轮场景（场景种子与装载、进入/持续/结束/结算全生命周期、STATE 标签 scene 扩展、场景面板与手动收尾）；M4 记忆系统（总结流水线与互斥任务、永久记忆检索注入、记忆管理面板、场景记忆）；M4 后全量审查修复（结算顺序与场景接力修正、记忆任务兜底、新增 DB 集成测试）；M5 行动与经济（打工与钱包收支、送礼两档与付费事件、冷落规则、性格倾向、主动消息、STATE flags/mood_label）。
- 计划中：M6 打磨（导出备份、事件/场景定义管理界面、主题、可选向量检索）。
