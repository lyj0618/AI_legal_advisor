# AI 法律顾问助手

基于 **Vue 3** + **Python FastAPI** 的法律咨询助手，沿用原 `index.html` 的 UI 布局与功能模块，大模型接入阿里云 **qwen-turbo**（DashScope）。

## 功能概览

| 模块 | 说明 |
|------|------|
| 助手广场 | 内置法律专家 + 绑定知识库的自定义助手 |
| 法律知识库 | 创建库、上传 txt/md/pdf/docx、解析分块、切片管理 |
| 检索测试 | 验证法条/制度召回效果 |
| 专家管理 | 创建助手、配置提示词、绑定知识库 |
| 咨询对话 | qwen-turbo + RAG 多轮对话，**SSE 流式输出**，思考过程与最终回答分离展示 |
| 系统管理 | 用户管理、个性化管理（问题/回答气泡颜色） |
| 登录认证 | JWT 登录页，保护业务 API |
| 文档格式 | txt / md / pdf / csv / **docx（Word）** |

## 目录结构

```
legal-ai-advisor/
├── backend/          # FastAPI + SQLite + DashScope
├── frontend/         # Vue 3 + Vite + Element Plus
└── README.md
```

## 环境要求

- Python 3.10+
- Node.js 18+
- 有效的 [阿里云 DashScope API Key](https://dashscope.aliyun.com/)

---

## 他人安装指南

适用于从 Git 克隆本项目后，在本地或新机器上首次部署。

### 第一步：获取代码

```bash
git clone https://github.com/lyj0618/AI_legal_advisor.git
cd AI_legal_advisor/legal-ai-advisor
```

> 若仓库根目录即为 `legal-ai-advisor`，则直接进入该目录即可。

### 第二步：配置后端环境

```bash
cd backend
copy .env.example .env    # Linux / macOS: cp .env.example .env
```

用文本编辑器打开 `.env`，**至少**修改以下项：

| 配置项 | 说明 |
|--------|------|
| `DASHSCOPE_API_KEY` | 填入你在阿里云百炼申请的 API Key（**不要使用示例占位符**） |
| `JWT_SECRET` | 生产环境请改为随机长字符串（至少 32 位） |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | 可选；默认 `admin` / `LegalAi@2026` |
| `PORT` | 后端端口，默认 `8002`，需与前端代理一致 |

可选配置：

| 配置项 | 说明 |
|--------|------|
| `CHAT_MODEL` | 对话模型，默认 `qwen-turbo` |
| `ENABLE_THINKING` | 是否强制开启思考模式；Qwen3 / QwQ 等模型可设为 `true` |
| `VISION_MODEL` | 图片解读模型，默认 `qwen-vl-plus` |
| `EMBEDDING_MODEL` | 向量嵌入模型，默认 `text-embedding-v2` |

### 第三步：安装并启动后端

**Windows：**

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

**Linux / macOS：**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

启动成功后：

- 后端地址：`http://127.0.0.1:8002`
- 健康检查：浏览器访问 `http://127.0.0.1:8002/health`，应返回 `{"status":"ok",...}`

首次启动会自动：

- 创建 SQLite 数据库（`backend/data/legal_ai.db`）
- 创建默认管理员账号
- 初始化内置专家模板

### 第四步：安装并启动前端

**新开一个终端窗口：**

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：**http://localhost:5173**

### 第五步：登录并使用

| 项目 | 默认值 |
|------|--------|
| 用户名 | `admin` |
| 密码 | `LegalAi@2026` |

推荐使用顺序：

1. **知识库** → 创建库 → 上传文档 → 点击「解析」
2. **专家管理** → 创建助手 → 绑定知识库 → 配置提示词
3. **助手广场** → 选择助手 → 开始咨询
4. **系统管理 → 个性化管理** → 自定义对话气泡颜色（可选）

### 常见问题

**1. 前端报 502 / 接口 Not Found**

- 确认后端已启动且端口与 `frontend/vite.config.js` 中 `proxy.target` 一致（默认均为 **8002**）
- 若修改了 `.env` 中的 `PORT`，需同步修改 `vite.config.js` 的代理地址

**2. 对话无响应或报 API Key 错误**

- 检查 `backend/.env` 中 `DASHSCOPE_API_KEY` 是否正确
- 确认阿里云账户余额充足、Key 未过期

**3. 看不到「思考过程」**

- `qwen-turbo` 不支持独立思考通道；可换用 Qwen3 / QwQ 等模型，并在 `.env` 设置 `ENABLE_THINKING=true`

**4. 端口被占用**

Windows PowerShell 强制重启后端：

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/restart-backend.ps1
```

或手动指定端口：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

（同时修改 `frontend/vite.config.js` 中的代理端口。）

### 生产部署（可选）

```bash
# 前端构建
cd frontend
npm run build
# 产物在 frontend/dist/，由 Nginx 等静态托管

# 后端生产运行（示例）
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

生产环境建议：

- 修改 `JWT_SECRET`、管理员密码
- 使用 Nginx 反向代理 `/api` 到后端
- 不要将 `backend/.env` 或 `backend/data/` 提交到 Git

### 安全提示

- **切勿**将真实 `DASHSCOPE_API_KEY` 提交到 Git
- 若 Key 曾泄露，请立即在阿里云控制台轮换
- `backend/data/` 含业务数据，已在 `.gitignore` 中排除

---

## 快速开始（开发者）

与上方「他人安装指南」步骤相同，简要版：

```bash
# 1. 配置
cd backend && copy .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY

# 2. 后端
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt && python run.py

# 3. 前端（新终端）
cd frontend && npm install && npm run dev
```

浏览器：`http://localhost:5173`  
默认账号：`admin` / `LegalAi@2026`

## 技术说明

- **对话模型**：`qwen-turbo`（可在 `.env` 中修改 `CHAT_MODEL`）
- **思考过程**：支持 Qwen3 / QwQ 等模型的 `reasoning_content` 流式展示
- **向量模型**：`text-embedding-v2`（文档解析与检索）
- **数据存储**：SQLite + 本地文件（`backend/data/`）
- **API 风格**：`/api/v1/...`
- **流式对话**：`POST /chats/{id}/completions` 默认 `stream: true`，返回 SSE
- **Word 解析**：使用 `python-docx`；旧版 `.doc` 请另存为 `.docx`
- **认证**：除 `/api/v1/auth/login`、`/health` 外，接口需 `Authorization: Bearer <token>`
- **上传限制**：单文件默认最大 50 MB；对话图片默认最多 3 张、单张 5 MB

## 免责声明

本系统回答由 AI 生成，**仅供参考，不构成正式法律意见**。重大法律事项请咨询执业律师。
