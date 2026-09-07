#!/usr/bin/env bash
# ============================================================
# sync-to-server.sh —— 把本地代码改动同步到腾讯云服务器
#
# 用法（在 Git Bash 里执行）：
#   ./deploy/scripts/sync-to-server.sh              # 同步后端 + 前端（默认，会先构建前端）
#   ./deploy/scripts/sync-to-server.sh backend      # 只同步后端
#   ./deploy/scripts/sync-to-server.sh frontend     # 只同步前端
#   ./deploy/scripts/sync-to-server.sh deps         # 只重装/更新 Python 依赖
#
# 可选参数（可组合）：
#   --no-build      跳过前端 npm run build，直接上传现有 dist/
#   --pip           顺带根据 requirements.txt 更新 Python 依赖
#   --no-restart    只传文件，不重启服务
#
# 环境变量（默认值已适配当前服务器，一般不用改）：
#   SERVER_HOST=124.223.189.99  SERVER_USER=ubuntu
#   SSH_KEY=~/.ssh/id_ed25519_legalai
#   APP_DIR=/opt/legal-ai-advisor   WEB_DIR=/var/www/legal-ai-advisor
# ============================================================

set -euo pipefail

SERVER_HOST="${SERVER_HOST:-124.223.189.99}"
SERVER_USER="${SERVER_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_legalai}"
APP_DIR="${APP_DIR:-/opt/legal-ai-advisor}"
WEB_DIR="${WEB_DIR:-/var/www/legal-ai-advisor}"
SERVICE="${SERVICE:-legal-ai-advisor-backend}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TS="$(date +%Y%m%d%H%M%S)"
STAGE_DIR="/tmp/laa-sync-${TS}"

TARGET="all"
DO_BUILD=1
DO_PIP=0
DO_RESTART=1

for arg in "$@"; do
  case "$arg" in
    all|backend|frontend|deps) TARGET="$arg" ;;
    --no-build)  DO_BUILD=0 ;;
    --pip)       DO_PIP=1 ;;
    --no-restart) DO_RESTART=0 ;;
    -h|--help)   sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "[错误] 未知参数: $arg（用 --help 查看用法）"; exit 1 ;;
  esac
done

SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i $SSH_KEY"
SCP="scp -o BatchMode=yes -o StrictHostKeyChecking=no -i $SSH_KEY"

step()  { echo; echo "==> $*"; }
ok()    { echo "    ✓ $*"; }
die()   { echo; echo "[失败] $*"; exit 1; }

# ---------- 0. 前置检查 ----------
[ -f "$SSH_KEY" ] || die "找不到 SSH 私钥: $SSH_KEY"
[ -d "$LOCAL_ROOT/backend" ] || die "找不到 backend/ 目录，当前根路径: $LOCAL_ROOT"

cd "$LOCAL_ROOT"

if ! git diff --quiet 2>/dev/null || [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "    ⚠ 本地存在未提交的改动："
  git status --porcelain | head -8 | sed 's/^/      /'
  echo "      （只是提醒，不影响同步；但不建议把没验证过的改动直接推线上）"
fi

# 连通性
[ "$($SSH "${SERVER_USER}@${SERVER_HOST}" 'echo ok' 2>/dev/null)" = "ok" ] \
  || die "SSH 连不上 ${SERVER_USER}@${SERVER_HOST}（检查密钥、防火墙 22 端口是否放行）"
ok "SSH 连通正常"

# ---------- 1. 后端 ----------
if [ "$TARGET" = "all" ] || [ "$TARGET" = "backend" ]; then
  step "打包后端源码"
  PKG="/tmp/laa-backend-${TS}.tgz"
  tar -czf "$PKG" -C backend app run.py requirements.txt scripts tests 2>/dev/null \
    || die "打包失败（确认 backend/app 存在）"
  ok "打包完成：$PKG ($(du -h "$PKG" | cut -f1))"

  step "上传并部署后端到 ${APP_DIR}/backend"
  $SCP "$PKG" "${SERVER_USER}@${SERVER_HOST}:/tmp/" >/dev/null
  rm -f "$PKG"

  $SSH "${SERVER_USER}@${SERVER_HOST}" bash -s <<REMOTE
set -e
mkdir -p ${STAGE_DIR}
tar -xzf /tmp/laa-backend-${TS}.tgz -C ${STAGE_DIR}

# app/ 用 --delete 精确同步，保证本地删掉的文件服务器上也删掉
rsync -a --delete ${STAGE_DIR}/app/          ${APP_DIR}/backend/app/
cp -a  ${STAGE_DIR}/run.py                   ${APP_DIR}/backend/run.py
cp -a  ${STAGE_DIR}/requirements.txt         ${APP_DIR}/backend/requirements.txt
[ -d  ${STAGE_DIR}/scripts ] && rsync -a --delete ${STAGE_DIR}/scripts/ ${APP_DIR}/backend/scripts/ || true
[ -d  ${STAGE_DIR}/tests   ] && rsync -a --delete ${STAGE_DIR}/tests/   ${APP_DIR}/backend/tests/   || true

rm -rf ${STAGE_DIR} /tmp/laa-backend-${TS}.tgz
# 保留 data/、.venv/、.env 不动
echo "    后端文件已就位"
REMOTE
  ok "后端代码已同步（.env / .venv / data 未受影响）"
fi

# ---------- 2. Python 依赖 ----------
if [ "$DO_PIP" = "1" ] || [ "$TARGET" = "deps" ]; then
  step "更新 Python 依赖（requirements.txt）"
  $SSH "${SERVER_USER}@${SERVER_HOST}" \
    "${APP_DIR}/backend/.venv/bin/python -m pip install --no-cache-dir -r ${APP_DIR}/backend/requirements.txt" \
    | tail -3
  ok "依赖更新完成"
fi

# ---------- 3. 前端 ----------
if [ "$TARGET" = "all" ] || [ "$TARGET" = "frontend" ]; then
  if [ "$DO_BUILD" = "1" ]; then
    step "本机构建前端（npm run build）"
    (cd frontend && npm run build 2>&1 | tail -4) || die "前端构建失败，已中止同步"
    ok "构建完成：frontend/dist"
  else
    echo; echo "==> 跳过构建（--no-build），上传现有 dist/"
  fi

  step "上传前端产物到 ${WEB_DIR}"
  PKG="/tmp/laa-frontend-${TS}.tgz"
  tar -czf "$PKG" -C frontend/dist .
  $SCP "$PKG" "${SERVER_USER}@${SERVER_HOST}:/tmp/" >/dev/null
  rm -f "$PKG"

  $SSH "${SERVER_USER}@${SERVER_HOST}" bash -s <<REMOTE
set -e
mkdir -p ${STAGE_DIR}
tar -xzf /tmp/laa-frontend-${TS}.tgz -C ${STAGE_DIR}
rsync -a --delete ${STAGE_DIR}/ ${WEB_DIR}/
rm -rf ${STAGE_DIR} /tmp/laa-frontend-${TS}.tgz
echo "    前端产物已就位"
REMOTE
  ok "前端已同步"
fi

# ---------- 4. 重启并验证 ----------
if [ "$DO_RESTART" = "1" ] && [ "$TARGET" != "frontend" ] && [ "$TARGET" != "deps" ]; then
  step "重启后端服务并等待健康检查"
  $SSH "${SERVER_USER}@${SERVER_HOST}" "sudo systemctl restart ${SERVICE}"
  for i in $(seq 1 20); do
    sleep 1
    HEALTH="$($SSH "${SERVER_USER}@${SERVER_HOST}" 'curl -s -m 3 http://127.0.0.1:8003/health' 2>/dev/null || true)"
    if echo "$HEALTH" | grep -q '"status":"ok"'; then
      ok "健康检查通过（第 ${i}s）"
      echo "    $HEALTH"
      break
    fi
    if [ "$i" = "20" ]; then
      echo "    ✗ 20 秒内未通过健康检查，看日志："
      echo "      ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_HOST} 'sudo journalctl -u ${SERVICE} -n 50'"
      exit 1
    fi
  done
elif [ "$TARGET" = "frontend" ]; then
  echo; echo "==> 纯静态资源更新，无需重启服务（Caddy reload 也不需要）"
fi

echo
echo "完成。访问 http://${SERVER_HOST} 验证。"
