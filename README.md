# 养成

网页版 AI 文字养成游戏：通过对话与日常互动，和一位女主角慢慢建立起一段关系。

时间与现实隔离，使用独立的虚拟时钟。所有存档共用同一位女主角，每份存档从头开始这段关系。

## 功能

- **流式对话**：OpenAI 兼容接口，回复会带动属性、心情与剧情变化
- **关系演化**：好感、信任、亲密等属性随互动变化，关系阶段与性格倾向随之改变
- **虚拟时间**：可手动推进；属性会随时间回归或衰减
- **事件与场景**：固定、随机、手动事件，以及多轮剧情场景
- **记忆**：对话会自动提炼为长期记忆，注入后续对话
- **经济**：打工、送礼、钱包收支；久未互动会受到冷落影响
- **存档**：多周目并存，支持单档导出 / 导入
- **内容管理**：可在界面编辑角色书、事件与场景，也可一键恢复内置内容
- **主题**：暗色 / 亮色

## 技术栈

- 后端：Python 3.14、FastAPI、SQLAlchemy 2.0、MySQL 8
- 前端：Vue 3、Vite、Pinia、Vue Router
- 模型：任意 OpenAI 兼容接口（SSE 流式）

## 环境

- MySQL 8
- [uv](https://github.com/astral-sh/uv)（后端环境）
- Node.js 24（前端构建）

## 安装

1. 启动 MySQL，确保账号可连接。
2. 复制 `.env.example` 为 `.env`，填写 `MYSQL_PASSWORD`（也可使用系统环境变量）。数据库默认名为 `new_idea`，首次启动会自动创建。

3. 安装后端依赖：

```bash
cd backend
uv venv --python 3.14
uv pip install -r requirements.txt
```

4. 安装并构建前端：

```bash
cd frontend
npm install
npm run build
```

## 启动

Windows 可双击 **`一键启动.bat`**：检查环境、按需构建前端、启动服务并打开浏览器。

手动启动：

```bash
cd backend
.venv/bin/python main.py          # Linux / macOS
.venv\Scripts\python.exe main.py  # Windows
```

默认地址：`http://127.0.0.1:18730`。端口可通过 `.env` 中的 `APP_PORT` 修改。

开发时前后端可分开跑：

```bash
# 后端（可选热重载：UVICORN_RELOAD=1）
cd backend
.venv/bin/python main.py

# 前端（Vite 将 /api 代理到后端）
cd frontend
npm run dev
```

## 使用

1. 打开「模型配置」，添加 OpenAI 兼容供应商与模型，并测试连通。
2. 「新建存档」，选择对话模型，开始一周目。
3. 在对话中互动；用侧栏查看状态、钱包、事件，并推进时间、打工或送礼。
4. 需要备份时，在存档卡片上「导出」；首页「导入存档」可恢复为新存档。
5. 「定义管理」可编辑角色书、事件书与场景书。

内置女主角为「小澄」，设定与事件、场景均来自 `backend/seeds/`。界面里改过的内容会保留，重启不会被覆盖；未改过的内置项，编辑对应 JSON 后重启即可更新。

数据保存在 MySQL。若要清空，停止服务后执行 `DROP DATABASE new_idea;`，下次启动会重建（请先导出存档）。

## 测试

```bash
cd backend
.venv/bin/python -m unittest discover -s tests
```

集成测试使用独立数据库 `new_idea_test`，结束后自动删除，需要本机 MySQL 可用。
