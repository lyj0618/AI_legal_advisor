# AI 法律顾问助手

基于 **Vue 3** + **Python FastAPI** 的法律咨询助手，沿用原 `index.html` 的 UI 布局与功能模块，大模型接入阿里云 **qwen-turbo**（DashScope）。

## 功能概览

| 模块 | 说明 |
|------|------|
| 法律顾问团 | 8 位内置法律专家 + 绑定知识库的自定义助手 |
| 法律知识库 | 创建库、上传 txt/md/pdf、解析分块、切片管理 |
| 检索测试 | 验证法条/制度召回效果 |
| 助手管理 | 创建助手、配置提示词、绑定知识库 |
| 咨询对话 | qwen-turbo + RAG 多轮对话，**SSE 流式输出**，历史消息持久化 |
| 登录认证 | JWT 登录页，保护业务 API |
| 文档格式 | txt / md / pdf / **docx（Word）** |

## 目录结构

```
legal-ai-advisor/
├── backend/          # FastAPI + SQLite + DashScope
├── frontend/         # Vue 3 + Vite + Element Plus
└── README.md
```

## 快速开始

### 1. 配置 API Key

在 [阿里云百炼 / DashScope](https://dashscope.aliyun.com/) 获取 API Key，复制 backend 环境文件：

```bash
cd legal-ai-advisor/backend
copy .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

### 2. 启动后端

```bash
cd legal-ai-advisor/backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

后端地址：`http://127.0.0.1:8000`  
健康检查：`http://127.0.0.1:8000/health`

`python run.py` 已开启 `--reload`，保存代码后会自动热重载。若端口被占用或需强制重启：

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/restart-backend.ps1
```

### 3. 启动前端

```bash
cd legal-ai-advisor/frontend
npm install
npm run dev
```

浏览器打开：`http://localhost:5173`

**默认登录账号**：`admin` / `123456`（可在 `backend/.env` 中修改 `AUTH_USERNAME`、`AUTH_PASSWORD`）

## 推荐使用流程

1. **法律知识库** → 创建库 → 上传法规/制度文档 → 点击「解析」
2. **助手管理** → 创建助手 → 绑定知识库 → 配置提示词
3. **法律顾问团** → 点击「立即咨询」开始对话
4. 或在知识库详情中使用 **检索测试** 验证召回

## 技术说明

- **对话模型**：`qwen-turbo`（可在 `.env` 中修改 `CHAT_MODEL`）
- **向量模型**：`text-embedding-v2`（文档解析与检索）
- **数据存储**：SQLite + 本地文件（`backend/data/`）
- **API 兼容**：接口路径对齐原 RAGFlow 风格（`/api/v1/...`），便于前端迁移
- **流式对话**：`POST /chats/{id}/completions` 默认 `stream: true`，返回 SSE（`text/event-stream`）
- **Word 解析**：使用 `python-docx` 提取段落与表格文本；旧版 `.doc` 请另存为 `.docx`
- **认证**：除 `/api/v1/auth/login`、`/health` 外，接口需 `Authorization: Bearer <token>`

## 免责声明

本系统回答由 AI 生成，**仅供参考，不构成正式法律意见**。重大法律事项请咨询执业律师。

## 环境要求

- Python 3.10+
- Node.js 18+
- 有效的 DashScope API Key
