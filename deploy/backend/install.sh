#!/usr/bin/env bash
# 一键部署后端到 Linux 服务器（systemd + nginx 方案 A）
# 用法：
#   sudo ./install.sh                  # 部署到默认路径 /opt/legal-ai-advisor
#   sudo ./install.sh /custom/path     # 自定义部署根目录
#
# 部署完成后：
#   1. 编辑 /opt/legal-ai-advisor/backend/.env（必改 DASHSCOPE_API_KEY/JWT_SECRET/AUTH_PASSWORD/CORS_ORIGINS）
#   2. sudo systemctl start legal-ai-advisor-backend
#   3. sudo systemctl enable legal-ai-advisor-backend
#
# 卸载：
#   sudo systemctl stop legal-ai-advisor-backend
#   sudo systemctl disable legal-ai-advisor-backend
#   sudo rm /etc/systemd/system/legal-ai-advisor-backend.service
#   sudo rm -rf /opt/legal-ai-advisor
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "[错误] 必须用 root 运行（sudo $0）"
  exit 1
fi

DEPLOY_ROOT="${1:-/opt/legal-ai-advisor}"
SERVICE_NAME="legal-ai-advisor-backend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_SRC="${SRC_DIR}/backend"
SERVICE_SRC="${SCRIPT_DIR}/${SERVICE_NAME}.service"
ENV_TEMPLATE_SRC="${SCRIPT_DIR}/../env/.env.production.template"

echo "==> 部署根目录: ${DEPLOY_ROOT}"
echo "==> 项目源目录: ${SRC_DIR}"

# 1. 前置检查
echo "==> [1/6] 检查环境"
if ! command -v python3.13 >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未检测到 Python3，请先安装 (apt install python3 python3-venv python3-pip)"
  exit 1
fi
PY_BIN="$(command -v python3.13 || command -v python3)"
PY_VERSION="$(${PY_BIN} -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "    Python: ${PY_BIN} (${PY_VERSION})"
if [[ "${PY_VERSION%%.*}" -lt 3 ]] || [[ "${PY_VERSION}" < "3.10" ]]; then
  echo "[错误] 需要 Python >= 3.10（项目按 3.13 写）"
  exit 1
fi

# 2. 复制后端代码
echo "==> [2/6] 复制后端到 ${DEPLOY_ROOT}/backend"
mkdir -p "${DEPLOY_ROOT}"
if [[ -d "${DEPLOY_ROOT}/backend" ]]; then
  echo "    目标已存在，保留运行时数据 (data/、.env、venv)，仅覆盖 app/ 源码"
  rsync -a --delete --exclude='venv' --exclude='.env' --exclude='data' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='.pytest_cache' \
        "${BACKEND_SRC}/" "${DEPLOY_ROOT}/backend/"
else
  mkdir -p "${DEPLOY_ROOT}/backend"
  rsync -a --exclude='venv' --exclude='.env' --exclude='data' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='.pytest_cache' \
        "${BACKEND_SRC}/" "${DEPLOY_ROOT}/backend/"
fi

# 3. 建 venv
echo "==> [3/6] 创建 Python 虚拟环境"
if [[ ! -d "${DEPLOY_ROOT}/backend/venv" ]]; then
  "${PY_BIN}" -m venv "${DEPLOY_ROOT}/backend/venv"
fi
"${DEPLOY_ROOT}/backend/venv/bin/pip" install --upgrade pip wheel setuptools >/dev/null
"${DEPLOY_ROOT}/backend/venv/bin/pip" install -r "${DEPLOY_ROOT}/backend/requirements.txt"

# 4. .env：不存在则从模板复制
echo "==> [4/6] 准备 .env"
if [[ ! -f "${DEPLOY_ROOT}/backend/.env" ]]; then
  if [[ -f "${ENV_TEMPLATE_SRC}" ]]; then
    cp "${ENV_TEMPLATE_SRC}" "${DEPLOY_ROOT}/backend/.env"
    # 强制生成一个强随机 JWT secret
    JWT_SECRET="$(head -c 48 /dev/urandom | base64 | tr -d '\n' | head -c 64)"
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" "${DEPLOY_ROOT}/backend/.env"
    # data_dir 用绝对路径
    sed -i "s|^DATA_DIR=.*|DATA_DIR=${DEPLOY_ROOT}/backend/data|" "${DEPLOY_ROOT}/backend/.env"
    echo "    已生成 .env（请编辑 DASHSCOPE_API_KEY / AUTH_PASSWORD / CORS_ORIGINS）"
  else
    echo "[警告] 未找到 .env 模板：${ENV_TEMPLATE_SRC}"
  fi
else
  echo "    .env 已存在，跳过"
fi

# 权限：仅 root 可读
chmod 600 "${DEPLOY_ROOT}/backend/.env" 2>/dev/null || true

# 5. 装 systemd unit
echo "==> [5/6] 注册 systemd 服务"
if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "[错误] 找不到 service 文件：${SERVICE_SRC}"
  exit 1
fi
# 替换路径占位符
TMP_SERVICE="$(mktemp)"
sed "s|__DEPLOY_ROOT__|${DEPLOY_ROOT}|g" "${SERVICE_SRC}" > "${TMP_SERVICE}"
install -m 644 "${TMP_SERVICE}" "/etc/systemd/system/${SERVICE_NAME}.service"
rm -f "${TMP_SERVICE}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service" >/dev/null

# 6. 提示
echo "==> [6/6] 部署完成"
cat <<EOF

=================== 下一步 ===================
1. 编辑配置文件（必须改 4 项）：
   sudo nano ${DEPLOY_ROOT}/backend/.env
   必改：
     DASHSCOPE_API_KEY=sk-xxxxxx
     AUTH_PASSWORD=改成你自己的强密码
     CORS_ORIGINS=https://你的域名
   可选：
     AUTH_USERNAME=admin
     CHAT_MODEL/VISION_MODEL/EMBEDDING_MODEL

2. 启动后端：
   sudo systemctl start ${SERVICE_NAME}
   sudo systemctl status ${SERVICE_NAME}
   journalctl -u ${SERVICE_NAME} -f

3. 部署前端（见 DEPLOY.md）：
   cd ${DEPLOY_ROOT}/frontend
   npm ci && npm run build
   sudo cp -r dist/* /var/www/legal-ai-advisor/

4. 配 nginx（见 deploy/nginx/legal-ai-advisor.conf）：
   sudo cp deploy/nginx/legal-ai-advisor.conf /etc/nginx/sites-available/
   sudo ln -sf /etc/nginx/sites-available/legal-ai-advisor.conf /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx

5. 防火墙（仅开 22/80/443）：
   sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
================================================
EOF
