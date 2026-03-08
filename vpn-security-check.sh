#!/bin/sh
# VPN 节点安全性 & AI 连通性周检脚本
# 部署: /usr/local/bin/vpn-security-check.sh
# 日志: /etc/openclash/security-check.log (保留最近4次)

LOG_DIR="/etc/openclash"
LOG_FILE="$LOG_DIR/security-check.log"
PROXY="http://Clash:ALgbUhlG@127.0.0.1:7890"
API="http://127.0.0.1:9090"
SECRET="Oe4sHjG1"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 保留最近4次报告(约1个月)
rotate_log() {
  if [ -f "$LOG_FILE" ]; then
    COUNT=$(grep -c '^========' "$LOG_FILE" 2>/dev/null)
    if [ "$COUNT" -ge 8 ]; then
      KEEP_FROM=$(grep -n '^========' "$LOG_FILE" | tail -6 | head -1 | cut -d: -f1)
      if [ -n "$KEEP_FROM" ]; then
        tail -n +$KEEP_FROM "$LOG_FILE" > "$LOG_FILE.tmp"
        mv "$LOG_FILE.tmp" "$LOG_FILE"
      fi
    fi
  fi
}

rotate_log

exec >> "$LOG_FILE" 2>&1

echo "========================================"
echo "VPN 安全性周检报告"
echo "时间: $TIMESTAMP"
echo "========================================"

# 1. 当前节点
echo ""
echo "--- 当前节点 ---"
CURRENT=$(curl -s -H "Authorization: Bearer $SECRET" "$API/proxies/TNTCloud" 2>/dev/null | sed -n 's/.*"now":"\([^"]*\)".*/\1/p')
echo "节点: $CURRENT"

# 2. 出口 IP
echo ""
echo "--- 出口 IP ---"
IP=$(curl -s --proxy "$PROXY" --max-time 10 https://api-ipv4.ip.sb/ip 2>/dev/null | tr -d '\n\r ')
if [ -z "$IP" ]; then
  echo "ERROR: 无法获取出口IP，代理可能不通"
  echo "========================================"
  echo ""
  exit 1
fi
echo "IP: $IP"

# 3. IP 风险检测 (多源)
echo ""
echo "--- IP 风险检测 ---"

echo "[ip-api.com]"
IPAPI=$(curl -s --noproxy '*' --max-time 8 "http://ip-api.com/json/${IP}?fields=country,city,isp,org,as,proxy,hosting,mobile" 2>/dev/null)
echo "$IPAPI"

sleep 2

echo "[proxycheck.io]"
PCHECK=$(curl -s --noproxy '*' --max-time 8 "https://proxycheck.io/v2/${IP}?vpn=1&asn=1&risk=1" 2>/dev/null)
PCHECK_PROXY=$(echo "$PCHECK" | sed -n 's/.*"proxy": *"\([^"]*\)".*/\1/p')
PCHECK_TYPE=$(echo "$PCHECK" | sed -n 's/.*"type": *"\([^"]*\)".*/\1/p')
PCHECK_RISK=$(echo "$PCHECK" | sed -n 's/.*"risk": *\([0-9]*\).*/\1/p')
echo "proxy=$PCHECK_PROXY type=$PCHECK_TYPE risk=$PCHECK_RISK"

sleep 2

echo "[ipapi.is]"
IPAPIS=$(curl -s --noproxy '*' --max-time 8 "https://api.ipapi.is/?q=${IP}" 2>/dev/null)
IS_DC=$(echo "$IPAPIS" | sed -n 's/.*"is_datacenter": *\([a-z]*\).*/\1/p')
IS_PROXY=$(echo "$IPAPIS" | sed -n 's/.*"is_proxy": *\([a-z]*\).*/\1/p')
IS_VPN=$(echo "$IPAPIS" | sed -n 's/.*"is_vpn": *\([a-z]*\).*/\1/p')
ABUSE=$(echo "$IPAPIS" | sed -n 's/.*"abuser_score": *"\([^"]*\)".*/\1/p' | head -1)
echo "datacenter=$IS_DC proxy=$IS_PROXY vpn=$IS_VPN abuser=$ABUSE"

# 4. 综合风险判定
echo ""
echo "--- 综合风险判定 ---"
RISK="LOW"
REASONS=""

echo "$IPAPI" | grep -q '"proxy":true' && { RISK="MEDIUM"; REASONS="${REASONS}ip-api:proxy=true; "; }
echo "$IPAPI" | grep -q '"hosting":true' && { RISK="HIGH"; REASONS="${REASONS}ip-api:hosting=true; "; }

[ "$PCHECK_PROXY" = "yes" ] && { [ "$RISK" = "LOW" ] && RISK="MEDIUM"; REASONS="${REASONS}proxycheck:proxy=yes; "; }
[ -n "$PCHECK_RISK" ] && [ "$PCHECK_RISK" -gt 50 ] 2>/dev/null && { RISK="HIGH"; REASONS="${REASONS}proxycheck:risk=${PCHECK_RISK}; "; }

[ "$IS_DC" = "true" ] && { REASONS="${REASONS}ipapi.is:datacenter=true; "; }
[ "$IS_VPN" = "true" ] && { RISK="HIGH"; REASONS="${REASONS}ipapi.is:vpn=true; "; }

if [ "$RISK" = "LOW" ]; then
  echo "风险: LOW - 所有检测源均未标记异常"
else
  echo "风险: $RISK - $REASONS"
fi

# 5. AI 服务连通性
echo ""
echo "--- AI 服务连通性 ---"
for SERVICE in \
  "Claude_API|https://api.anthropic.com/v1/messages|401,405" \
  "Gemini|https://gemini.google.com/|200" \
  "OpenAI_API|https://api.openai.com/v1/models|401" \
  "GH_Copilot|https://api.individual.githubcopilot.com/|404" \
  "ChatGPT|https://chatgpt.com/|200,302,403"
do
  NAME=$(echo "$SERVICE" | cut -d'|' -f1)
  URL=$(echo "$SERVICE" | cut -d'|' -f2)
  EXPECT=$(echo "$SERVICE" | cut -d'|' -f3)

  RESULT=$(curl -s --proxy "$PROXY" --max-time 12 -o /dev/null -w "%{http_code}|%{time_starttransfer}" "$URL" 2>/dev/null)
  CODE=$(echo "$RESULT" | cut -d'|' -f1)
  TTFB=$(echo "$RESULT" | cut -d'|' -f2)

  if [ "$CODE" = "000" ]; then
    STATUS="TIMEOUT"
  elif echo ",$EXPECT," | grep -q ",$CODE,"; then
    STATUS="OK"
  else
    STATUS="UNEXPECTED($CODE)"
  fi

  printf "%-16s code=%-3s  TTFB=%-6s  %s\n" "$NAME" "$CODE" "${TTFB}s" "$STATUS"
done

# 6. DNS 健康
echo ""
echo "--- DNS 健康 ---"
ACTIVE_CONF=$(uci get openclash.config.config_path 2>/dev/null)
PSNR=$(grep 'proxy-server-nameserver' "$ACTIVE_CONF" 2>/dev/null | head -1)
echo "proxy-server-nameserver: $PSNR"
echo "$PSNR" | grep -qE '8\.8\.8\.8|1\.1\.1\.1|8\.8\.4\.4' && echo "WARNING: 海外DNS混入proxy-server-nameserver" || echo "OK: 纯国内DNS"

# 7. 内核日志健康
echo ""
echo "--- 内核日志健康 ---"
WARNS=$(grep -c 'level=warning' /tmp/openclash.log 2>/dev/null)
ERRORS=$(grep -c 'level=error' /tmp/openclash.log 2>/dev/null)
FATALS=$(grep -c 'level=fatal' /tmp/openclash.log 2>/dev/null)
echo "warnings=$WARNS errors=$ERRORS fatals=$FATALS"
if [ "$FATALS" -gt 0 ] 2>/dev/null; then
  echo "CRITICAL: 存在 fatal 错误!"
  grep 'level=fatal' /tmp/openclash.log 2>/dev/null | tail -3
elif [ "$WARNS" -gt 20 ] 2>/dev/null; then
  echo "WARNING: warning 数量偏多，最近的:"
  grep 'level=warning' /tmp/openclash.log 2>/dev/null | tail -3
else
  echo "OK: 日志健康"
fi

# 8. IPv6 泄漏检查
echo ""
echo "--- IPv6 泄漏检查 ---"
V6_DHCP=$(uci get dhcp.lan.dhcpv6 2>/dev/null)
V6_RA=$(uci get dhcp.lan.ra 2>/dev/null)
V6_OC=$(uci get openclash.config.ipv6_enable 2>/dev/null)
if [ "$V6_DHCP" = "disabled" ] && [ "$V6_RA" = "disabled" ] && [ "$V6_OC" = "0" ]; then
  echo "OK: IPv6 已正确关闭"
else
  echo "WARNING: IPv6 可能泄漏 (dhcpv6=$V6_DHCP ra=$V6_RA oc_ipv6=$V6_OC)"
fi

# 9. TLS 配置安全
echo ""
echo "--- TLS 配置安全 ---"
SKIP_CERT=$(grep -c 'skip-cert-verify: true' "$ACTIVE_CONF" 2>/dev/null)
HAS_FP=$(grep -c 'client-fingerprint' "$ACTIVE_CONF" 2>/dev/null)
echo "skip-cert-verify=true 节点数: $SKIP_CERT"
echo "client-fingerprint 配置数: $HAS_FP"
[ "$SKIP_CERT" -gt 0 ] && echo "WARNING: skip-cert-verify=true 存在中间人风险"
[ "$HAS_FP" -eq 0 ] && echo "WARNING: 未设置 client-fingerprint，TLS指纹可被GFW识别"

echo ""
echo "========================================"
echo ""
