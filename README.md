# debugVPN

OpenWrt + OpenClash (Mihomo) 环境下的 VPN 安全检测与调试工具集。

---

## 目录结构

```
E:\debugVPN\
├── README.md                          # 本文件
├── OpenClash-配置优化指南.md           # OpenClash 配置最佳实践
├── vpn-security-check.sh              # 安全检查脚本（部署在路由器上）
├── pull-security-report.sh            # 本机拉取报告脚本
├── reports/                           # 每周报告存放目录
│   └── security-check-YYYY-MM-DD.log
├── node-test-*.log                    # 全量节点测试记录
└── OpenClash-*.log                    # 历史调试日志
```

---

## 每周自动安全检查

### 工作流程

```
每周一 05:10  路由器 cron 执行安全检查，写入日志
每周一 05:15  本机 Windows 计划任务拉取报告到 reports/
```

### 检查项（共 9 项）

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | 当前节点 | 确认正在使用的代理节点 |
| 2 | 出口 IP | 获取代理出口的公网 IP |
| 3 | IP 风险检测 | 三源交叉验证（ip-api.com / proxycheck.io / ipapi.is） |
| 4 | 综合风险判定 | 自动归类 LOW / MEDIUM / HIGH 并给出原因 |
| 5 | AI 服务连通性 | Claude / Gemini / OpenAI / GitHub Copilot / ChatGPT |
| 6 | DNS 健康 | 检查 proxy-server-nameserver 是否混入海外 DNS |
| 7 | 内核日志健康 | warning / error / fatal 计数 |
| 8 | IPv6 泄漏 | DHCPv6 / RA / OpenClash IPv6 是否正确关闭 |
| 9 | TLS 配置安全 | skip-cert-verify 和 client-fingerprint 检查 |

### 风险判定逻辑

| 等级 | 触发条件 |
|------|----------|
| LOW | 所有检测源均未标记 proxy/hosting/vpn |
| MEDIUM | 任一源标记 proxy=true，但 hosting=false |
| HIGH | hosting=true 或 vpn=true 或 risk>50 |

### AI 服务期望状态码

| 服务 | 正常状态码 | 说明 |
|------|-----------|------|
| Claude API | 405 | 未带 key，返回 Method Not Allowed = 可达 |
| Gemini | 200 | 页面正常加载 |
| OpenAI API | 401 | 未带 key，返回 Unauthorized = 可达 |
| GitHub Copilot | 404 | API 端点可达 |
| ChatGPT | 200/302/403 | 均表示可达（403 可能有风控但非不通） |

---

## 部署信息

### 路由器侧（192.168.2.1）

| 项目 | 路径 |
|------|------|
| 检查脚本 | `/usr/local/bin/vpn-security-check.sh` |
| 检查日志 | `/etc/openclash/security-check.log`（自动轮转，保留最近 4 次） |
| cron 任务 | `10 5 * * 1 /usr/local/bin/vpn-security-check.sh` |

### 本机侧（Windows）

| 项目 | 路径/名称 |
|------|-----------|
| 拉取脚本 | `E:\debugVPN\pull-security-report.sh` |
| 报告目录 | `E:\debugVPN\reports\` |
| 计划任务 | `VPN-Security-Report`（每周一 05:15） |

---

## 常用命令

### 手动拉取最新报告

```bash
bash E:\debugVPN\pull-security-report.sh
```

### 立即触发一次检查并拉取

```bash
ssh root@192.168.2.1 "/usr/local/bin/vpn-security-check.sh"
bash E:\debugVPN\pull-security-report.sh
```

### 在路由器上直接查看

```bash
ssh root@192.168.2.1 "cat /etc/openclash/security-check.log"
```

### 全量节点测试（切换每个节点逐一检测 IP 标记和 AI 可用性）

```bash
# 测试脚本在路由器 /tmp/test_nodes.sh，执行约 3-4 分钟
ssh root@192.168.2.1 "/tmp/test_nodes.sh"
```

### 管理 Windows 计划任务

```bash
# 查看任务状态
schtasks //Query //TN "VPN-Security-Report"

# 删除任务
schtasks //Delete //TN "VPN-Security-Report" //F

# 重建任务
schtasks //Create //TN "VPN-Security-Report" //TR "bash E:\\debugVPN\\pull-security-report.sh" //SC WEEKLY //D MON //ST 05:15 //F
```

---

## 节点选择建议

基于 2026-03-10 全量测试结果（详见 `node-test-2026-03-10.md`，共 110 节点）：

| 优先级 | 套餐/地区 | Claude | OpenAI | IP风险 | 说明 |
|--------|-----------|--------|--------|--------|------|
| ⭐⭐⭐ | **基础-台湾** 1-4 | ✅ | ✅ | LOW | 双通+最干净，首选 |
| ⭐⭐⭐ | **基础-新加坡** 1-8 | ✅ | ✅ | MED | 双通，部分IP标记proxy |
| ⭐⭐⭐ | **基础-日本/韩国/马来** | ✅ | ✅ | LOW | 双通，干净 |
| ⭐⭐⭐ | **基础-美国** 1-2 SS | ✅ | ✅ | LOW | 双通，干净 |
| ⭐⭐ | **高级/旗舰-台湾/新加坡** | ✅ | ❌ | LOW/MED | 仅Claude通，延迟最低 |
| ⭐ | **香港** HKT1/2、大带宽7/8 | ✅ | ❌ | LOW | Claude通但OpenAI封 |
| ❌ | **香港** HKT3/4 | ❌ | ❌ | LOW | Claude 403，禁用 |
| ❌ | **法国** | 部分 | ❌ | HIGH | hosting=Y，数据中心IP |
| ❌ | **直连节点**（Hysteria2） | ❌ | ❌ | - | 全部超时 |

**重要发现（2026-03-10）：**
- Gemini 全线超时（所有节点 000）
- OpenRouter 可达（HTTP 200）
- 基础套餐 OpenAI 可用，高级/旗舰 OpenAI 全部超时（IP段被封）
- 自动选择 URLTest 间隔 86400s（24h），建议改为 300s

---

## 已知安全注意事项

- **skip-cert-verify: true** — 所有 54 个节点均开启，这是机场订阅配置，存在理论上的中间人风险
- **client-fingerprint 未设置** — TLS 握手暴露 Go/Mihomo 指纹，GFW 可识别为非浏览器流量
- **代理中转架构** — 入口服务器为广州电信国内机器，GFW 可见你连接到该服务器的元数据，但无法解密内层流量
- 以上两项需要机场侧修改订阅配置才能根本解决
