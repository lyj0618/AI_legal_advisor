#!/usr/bin/env bash
# 数据备份脚本 - 每天凌晨 3 点把 SQLite + data/ 目录打包
# 部署方法（root 身份）：
#   1. 放到 /opt/legal-ai-advisor/deploy/backup.sh
#   2. chmod +x /opt/legal-ai-advisor/deploy/backup.sh
#   3. 编辑 sudo crontab -e，加一行：
#      0 3 * * * /opt/legal-ai-advisor/deploy/backup.sh >> /var/log/legal-ai-advisor-backup.log 2>&1
#
# 备份内容：
#   - SQLite 数据库（含所有用户、聊天、问答缓存）
#   - uploads/  知识库文档
#   - chat_images/  聊天图片
#   - doc_images/   文档内嵌图片
#   - indexes/      FAISS 向量索引
#
# 不备份：venv/、__pycache__/、node_modules/、frontend/dist/（可重建）
#
# ⚠️ Hermes 轻量服务器只有 1 块系统盘，本地保留 7 天后自动清理。
#    强烈建议额外把备份同步到对象存储（S3/COS/OSS），脚本里有可选段。
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/legal-ai-advisor}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/legal-ai-advisor}"
KEEP_DAYS="${KEEP_DAYS:-7}"
DATE="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/legal-ai-advisor-${DATE}.tar.gz"

mkdir -p "${BACKUP_DIR}"

# 检查 systemd 服务在跑就先停掉，确保 SQLite 写完
if systemctl is-active --quiet legal-ai-advisor-backend; then
  echo "[$(date)] 暂停后端以保证 SQLite 一致性"
  systemctl stop legal-ai-advisor-backend
  RESTART_AFTER=1
else
  RESTART_AFTER=0
fi

trap 'if [[ "${RESTART_AFTER}" == "1" ]]; then systemctl start legal-ai-advisor-backend; fi' EXIT

echo "[$(date)] 开始备份: ${BACKUP_FILE}"
cd "${DEPLOY_ROOT}/backend"
tar -czf "${BACKUP_FILE}" \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    data/

echo "[$(date)] 备份完成: $(du -h "${BACKUP_FILE}" | cut -f1)"

# 清理 N 天前的旧备份
find "${BACKUP_DIR}" -name "legal-ai-advisor-*.tar.gz" -mtime +${KEEP_DAYS} -delete
echo "[$(date)] 已清理 ${KEEP_DAYS} 天前的旧备份"

# ========== 可选：把备份同步到对象存储 ==========
# 取消下面需要的段并配置好 awscli/coscli/ossutil：
#
# AWS S3:
#   aws s3 cp "${BACKUP_FILE}" s3://your-bucket/legal-ai-advisor/
# 腾讯云 COS（用 coscli）:
#   coscli cp "${BACKUP_FILE}" cos://your-bucket/legal-ai-advisor/
# 阿里云 OSS（用 ossutil）:
#   ossutil cp "${BACKUP_FILE}" oss://your-bucket/legal-ai-advisor/
#
# 建议再加一条 cron 把昨天那份也同步上去（每小时一次）：
#   0 * * * * /opt/legal-ai-advisor/deploy/sync-backup.sh

echo "[$(date)] 备份脚本结束"
