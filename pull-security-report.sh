#!/bin/bash
# 从路由器拉取最新 VPN 安全检查报告
# Windows 计划任务调用: bash E:\debugVPN\pull-security-report.sh

ROUTER="root@192.168.2.1"
REMOTE_LOG="/etc/openclash/security-check.log"
LOCAL_DIR="E:/debugVPN/reports"
TIMESTAMP=$(date "+%Y-%m-%d")
LOCAL_FILE="$LOCAL_DIR/security-check-${TIMESTAMP}.log"

mkdir -p "$LOCAL_DIR"

# 拉取报告
scp "$ROUTER:$REMOTE_LOG" "$LOCAL_FILE" 2>/dev/null

if [ $? -eq 0 ] && [ -s "$LOCAL_FILE" ]; then
  echo "========================================"
  echo " VPN 安全报告已拉取: $LOCAL_FILE"
  echo "========================================"
  echo ""
  # 显示最新一次报告
  awk '/^========/{n++} n>=('$(grep -c '^========' "$LOCAL_FILE")')' "$LOCAL_FILE"
else
  echo "ERROR: 拉取失败，路由器可能不在线"
  exit 1
fi
