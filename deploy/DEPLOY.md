# Legal AI Advisor 部署指南（systemd + nginx 方案 A）

目标服务器：2 核 / 2GB 内存 / 50GB 系统盘（Hermes Agent-ltu8 同类轻量云服务器适用）

预计时间：30-45 分钟（含下载依赖与首次构建）。

---

## 0. 前置要求

| 项 | 命令/说明 |
|----|----------|
| OS | Ubuntu 22.04 LTS / Debian 12（其他发行版等价命令） |
| Python | ≥ 3.10（项目按 3.13 写） |
| Node.js | ≥ 20.x（构建前端用） |
| Nginx | ≥ 1.20 |
| 公网域名 | 1 个，已解析到服务器 IP |
| DashScope API Key | 阿里云百炼控制台开通 |

一次性安装系统依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev \
                    nodejs npm nginx git curl ufw rsync
# 可选：PDF/Word 解析
sudo apt install -y libreoffice poppler-utils
# 可选：OCR（如需扫描件）
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
```

防火墙（**只开 22/80/443**；后端 8003 不对外暴露）：

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 1. 传代码到服务器

任选一种：

```bash
# 方式 A：git clone（推荐，便于后续升级）
ssh user@your.server
sudo mkdir -p /opt/legal-ai-advisor
sudo chown $USER:$USER /opt/legal-ai-advisor
cd /opt/legal-ai-advisor
git clone <your-repo-url> .

# 方式 B：rsync（适合本地开发机 → 服务器）
# 本地 PowerShell 或 Git Bash：
rsync -av --exclude='node_modules' --exclude='.venv' --exclude='data' \
      --exclude='frontend/dist' --exclude='__pycache__' \
      ./ user@your.server:/opt/legal-ai-advisor/
```

---

## 2. 部署后端

```bash
cd /opt/legal-ai-advisor
chmod +x deploy/backend/install.sh
sudo ./deploy/backend/install.sh
```

脚本会：

1. 复制 `backend/` 到 `${DEPLOY_ROOT}/backend`
2. 创建 venv 并安装 `requirements.txt`
3. 从模板生成 `.env`（自动写入随机 JWT secret、绝对路径 DATA_DIR）
4. 注册 systemd 服务 `legal-ai-advisor-backend.service` 并 `enable`

**必改** `.env`（标 ⚠️ 的项）：

```bash
sudo nano /opt/legal-ai-advisor/backend/.env
```

```ini
DASHSCOPE_API_KEY=sk-你的真实key           # ⚠️
AUTH_PASSWORD=你的强密码                   # ⚠️
CORS_ORIGINS=https://你的域名              # ⚠️
JWT_SECRET=                              # 已自动生成 64 字符随机值，无需动
DATA_DIR=/opt/legal-ai-advisor/backend/data  # 已自动写入绝对路径
```

启动后端：

```bash
sudo systemctl start legal-ai-advisor-backend
sudo systemctl status legal-ai-advisor-backend
journalctl -u legal-ai-advisor-backend -f    # 跟踪日志
```

验证：

```bash
curl -s http://127.0.0.1:8003/health
# 期望：{"status":"ok","model":"qwen-turbo",...,"dashscope_configured":true}
```

如果 `dashscope_configured: false`，说明 `DASHSCOPE_API_KEY` 没读上：检查 `.env` 权限（应为 600）、重启服务。

---

## 3. 部署前端

前端是纯静态文件，构建后由 nginx 直接服务。

```bash
cd /opt/legal-ai-advisor/frontend
npm ci
npm run build
# 产物在 frontend/dist/
```

把构建产物放到 nginx 站点目录：

```bash
sudo mkdir -p /var/www/legal-ai-advisor
sudo cp -r dist/* /var/www/legal-ai-advisor/
sudo chown -R www-data:www-data /var/www/legal-ai-advisor 2>/dev/null || true
```

### 3.1 如果前端要调外部后端（推荐：用 nginx 反代，无需改）

配置已写好：所有 `/api/*` 请求由 nginx 转到 `127.0.0.1:8003`，前端代码不需要改。

如果前端要单独配置 baseURL（如部署到子路径），在 `src/utils/api.js` 或 `axios` 实例里改：

```js
baseURL: '/api/v1'
```

> ⚠️ 之前开发时 `vite.config.js` 里 proxy 指向 `http://127.0.0.1:8003`，**那是开发态**。生产态不依赖 vite proxy，全靠 nginx 反代。

---

## 4. 配 nginx

```bash
# 1. 复制配置
sudo cp /opt/legal-ai-advisor/deploy/nginx/legal-ai-advisor.conf \
        /etc/nginx/sites-available/legal-ai-advisor.conf

# 2. 改 server_name 和证书占位符
sudo nano /etc/nginx/sites-available/legal-ai-advisor.conf
# 把所有 your.domain.com 替换成你的真实域名
# ssl_certificate / ssl_certificate_key 暂用占位也行（先不开 HTTPS）

# 3. 启用站点
sudo ln -sf /etc/nginx/sites-available/legal-ai-advisor.conf \
             /etc/nginx/sites-enabled/legal-ai-advisor.conf
sudo rm -f /etc/nginx/sites-enabled/default

# 4. 校验 + 加载
sudo nginx -t
sudo systemctl reload nginx
```

此时 `http://你的域名` 应该能打开前端（用 HTTP）。

---

## 5. 申请 HTTPS 证书（acme.sh，推荐）

```bash
# 安装 acme.sh
curl https://get.acme.sh | sh -s email=your@email.com
source ~/.bashrc

# 申请 ECC 证书，签发机构 ZeroSSL（默认）
acme.sh --issue -d your.domain.com --nginx

# 安装到 nginx 期望的路径
mkdir -p /etc/nginx/ssl/your.domain.com_nginx
acme.sh --install-cert -d your.domain.com --ecc \
  --key-file       /etc/nginx/ssl/your.domain.com_nginx/your.domain.com.key \
  --fullchain-file /etc/nginx/ssl/your.domain.com_nginx/fullchain.cer \
  --reloadcmd      "systemctl reload nginx"

# 自动续签已由 acme.sh 的 cron 接管（默认 60 天后自动续）
```

之后再次 `sudo nginx -t && sudo systemctl reload nginx`，HTTPS 即生效。

---

## 6. 验证全链路

```bash
# 1. 后端健康
curl -s http://127.0.0.1:8003/health

# 2. 前端（应返回 index.html）
curl -sI https://your.domain.com/

# 3. 反代（经 nginx 调后端）
curl -s https://your.domain.com/api/v1/experts \
     -H "Authorization: Bearer $(curl -s -X POST https://your.domain.com/api/v1/auth/login \
       -H 'Content-Type: application/json' \
       -d '{"username":"admin","password":"<你的密码>"}' | jq -r '.data.access_token')"
```

浏览器打开 `https://your.domain.com/`，用 `admin / <你的密码>` 登录，完整跑一遍聊天+知识库上传。

---

## 7. 数据备份（强烈建议）

```bash
# 1. 启用备份脚本
sudo chmod +x /opt/legal-ai-advisor/deploy/scripts/backup.sh

# 2. 加 cron（每天 3 点）
sudo crontab -e
# 加：
0 3 * * * /opt/legal-ai-advisor/deploy/scripts/backup.sh >> /var/log/legal-ai-advisor-backup.log 2>&1
```

本地保留 7 天自动清理。**强烈建议**把 `deploy/scripts/backup.sh` 末尾的"对象存储同步"段启用（AWS S3 / 腾讯云 COS / 阿里云 OSS），否则一旦系统盘故障数据全丢。

---

## 8. 升级流程（本机 → 服务器）

> ⚠️ 本项目的目标服务器（腾讯云，124.223.189.99）**访问不到 GitHub**
> （`GnuTLS recv error (-110)`），因此 `git pull` 这条路走不通。
> 实际采用的方式是：**在本机打包 → scp 上传 → 服务器端 rsync 精确同步**。
> 已经封装成脚本，日常一条命令搞定。

### 8.1 日常同步（推荐）

在本机 Git Bash 里执行：

```bash
cd C:/Users/Administrator/legal-ai-advisor-original   # 你的工作副本路径
./deploy/scripts/sync-to-server.sh
```

默认行为：同步后端源码 → 构建前端 → 上传 `dist/` → 重启后端 → 等待健康检查通过。
`.env`、`.venv/`、`data/` **不会被覆盖**。

常用变体：

| 命令 | 用途 |
|------|------|
| `./deploy/scripts/sync-to-server.sh backend` | 只改了后端 Python 代码 |
| `./deploy/scripts/sync-to-server.sh frontend` | 只改了前端（纯静态更新，不重启服务） |
| `./deploy/scripts/sync-to-server.sh frontend --no-build` | 已有 dist/，直接上传，不重新构建 |
| `./deploy/scripts/sync-to-server.sh backend --pip` | requirements.txt 有变动，顺带更新依赖 |
| `./deploy/scripts/sync-to-server.sh deps` | 只重装 Python 依赖 |

脚本顶部可用环境变量覆盖目标机：`SERVER_HOST` / `SERVER_USER` / `SSH_KEY` /
`APP_DIR` / `WEB_DIR` / `SERVICE`。

### 8.2 手工同步（脚本不可用时的兜底）

```bash
# --- 后端 ---
cd legal-ai-advisor-original
tar -czf /tmp/laa-backend.tgz -C backend app run.py requirements.txt scripts tests
scp -i ~/.ssh/id_ed25519_legalai /tmp/laa-backend.tgz ubuntu@124.223.189.99:/tmp/
ssh -i ~/.ssh/id_ed25519_legalai ubuntu@124.223.189.99
  mkdir -p /tmp/stg && tar -xzf /tmp/laa-backend.tgz -C /tmp/stg
  rsync -a --delete /tmp/stg/app/ /opt/legal-ai-advisor/backend/app/
  cp -a /tmp/stg/run.py /tmp/stg/requirements.txt /opt/legal-ai-advisor/backend/
  sudo systemctl restart legal-ai-advisor-backend
  curl -s http://127.0.0.1:8003/health

# --- 前端 ---
cd frontend && npm run build
tar -czf /tmp/laa-frontend.tgz -C dist .
scp -i ~/.ssh/id_ed25519_legalai /tmp/laa-frontend.tgz ubuntu@124.223.189.99:/tmp/
ssh -i ~/.ssh/id_ed25519_legalai ubuntu@124.223.189.99
  mkdir -p /tmp/stg2 && tar -xzf /tmp/laa-frontend.tgz -C /tmp/stg2
  rsync -a --delete /tmp/stg2/ /var/www/legal-ai-advisor/
```

### 8.3 回滚

后端代码回滚：在本机 `git checkout <旧提交> -- backend/` 后重新同步即可；
`app/` 用 `--delete` 同步，能保证服务器上多余文件也被清掉。

前端回滚：本机切到旧提交后重新 `npm run build` 再同步。

数据回滚：`deploy/scripts/backup.sh` 的备份解压回 `/opt/legal-ai-advisor/backend/data/`。

### 8.4 注意事项

- 改了 `requirements.txt` 记得加 `--pip`，否则只是文件传上去、依赖没装。
- 改了 `.env` 必须手工到服务器上改（脚本刻意不碰 `.env`，避免覆盖线上密钥）。
- 前端 `vite.config.js` 的 proxy 只对开发态生效，生产走 Caddy 反代，不需要改。
- 同步前脚本会提示本地未提交的改动，建议先 `git commit` 再同步，便于追溯线上版本。

---

## 9. 故障排查

| 现象 | 检查 |
|------|------|
| 前端打开白屏 | `sudo tail -f /var/log/nginx/legal-ai-advisor.error.log`；浏览器 F12 看 Network |
| `/api/v1/auth/login` 401 | `.env` 的 `AUTH_USERNAME/AUTH_PASSWORD` 改过没重启；`sudo systemctl restart legal-ai-advisor-backend` |
| `/api` 502 Bad Gateway | 后端没起：`systemctl status legal-ai-advisor-backend`；`journalctl -u legal-ai-advisor-backend -n 50` |
| 聊天没返回 | `DASHSCOPE_API_KEY` 是否配置；`dashscope_configured: true` 了吗；模型名是否在百炼控制台开通 |
| 内存爆掉 OOM | 2GB 机器在 FAISS 索引大时可能触发。`systemctl status` 看 `MemoryMax=1600M` 是否生效；考虑把 `indexes/` 切到内存映射（`USE_VECTOR_INDEX=false` 仅留 SQLite 暴力检索） |
| SQLite 锁等待 | `data/legal_ai.db-wal` 异常大时关掉后端再启：`sudo systemctl restart legal-ai-advisor-backend` |

---

## 10. 卸载

```bash
sudo systemctl stop legal-ai-advisor-backend
sudo systemctl disable legal-ai-advisor-backend
sudo rm /etc/systemd/system/legal-ai-advisor-backend.service
sudo rm -rf /opt/legal-ai-advisor
sudo rm /etc/nginx/sites-enabled/legal-ai-advisor.conf
sudo rm /var/www/legal-ai-advisor -rf
sudo systemctl reload nginx
```

---

## 文件清单

```
deploy/
├── DEPLOY.md                                        # 本文档
├── backend/
│   ├── install.sh                                   # 一键部署脚本
│   └── legal-ai-advisor-backend.service             # systemd unit
├── env/
│   └── .env.production.template                     # 生产环境变量模板
├── nginx/
│   └── legal-ai-advisor.conf                        # nginx 站点配置
└── scripts/
    └── backup.sh                                    # 数据备份 + 清理旧备份
```
