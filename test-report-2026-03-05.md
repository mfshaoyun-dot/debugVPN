# OpenClash 测试报告

- 日期: 2026-03-05 11:26
- 路由器: 192.168.5.1 (AE86Wrt JCG-Q30Pro)
- 内核: Mihomo Meta v1.19.20 linux arm64
- 出口IP: 103.220.218.92 (台北, 台湾)

---

## 代理出口 IP 安全检测

| 项目 | 值 |
|------|-----|
| IP | 103.220.218.92 |
| 位置 | Taipei, Taiwan |
| ISP | Radishcloud Technology LLC |
| ASN | AS201217 |
| proxy | false |
| hosting | false |
| 风险等级 | 低 |

---

## 国内连通性 & 速度

| 目标 | HTTP | TTFB | 速度 | 说明 |
|------|------|------|------|------|
| 百度 | 200 | 107ms | - | 正常 |
| 淘宝 | 200 | 80ms | - | 正常 |
| 腾讯 | 501 | 89ms | - | 连通, curl UA问题 |
| 阿里云镜像 | 200 | - | 1.67 MB/s | 直连下载正常 |

## 海外连通性 & 速度

| 目标 | HTTP | TTFB | 速度 | 说明 |
|------|------|------|------|------|
| Google | 200 | 303ms | - | 正常 |
| YouTube | 200 | 286ms | - | 正常 |
| GitHub | 403 | 290ms | - | 连通, curl无UA被拦 |
| Cloudflare 10MB | 200 | - | 15.3 MB/s | 代理下载速度优秀 |

## AI 服务连通性

| 服务 | HTTP | TTFB | 状态 | 说明 |
|------|------|------|------|------|
| ChatGPT (OpenAI) | 308 | 241ms | OK | 308重定向, 正常 |
| OpenAI API | 421 | 249ms | OK | 连通, API端点可用 |
| Claude (Anthropic) | 403 | 184ms | OK | 连通, curl无cookie |
| Anthropic API | 404 | 150ms | OK | 连通, 根路径无内容 |
| Google Gemini | 200 | 345ms | OK | 正常 |
| Google AI Studio | 302 | 611ms | OK | 302重定向, 正常 |
| Copilot (Bing) | 000 | - | FAIL | 连接失败, 疑似被分流到DIRECT |
| HuggingFace | 200 | 259ms | OK | 正常 |
| Perplexity | 403 | 232ms | OK | 连通, 反爬机制 |
| Grok (xAI) | 403 | 241ms | OK | 连通, 反爬机制 |

---

## 已完成的优化配置

### 基础设置
- [x] 运行模式: fake-ip + rule
- [x] china_ip_route: 开启
- [x] IPv6: 已关闭 (ipv6_enable=0, ra/dhcpv6/ndp=disabled)
- [x] AAAA 过滤: 开启
- [x] append_wan_dns: 关闭
- [x] DNS 劫持: Dnsmasq 转发
- [x] dnsmasq noresolv: 开启 (不读运营商DNS)

### DNS 配置
- [x] Nameserver: 114.114.114.114, 119.29.29.29, 223.5.5.5 (UDP)
- [x] Fallback: dns.google/dns-query, dns.cloudflare.com/dns-query (HTTPS)
- [x] Default: 114.114.114.114, 119.29.29.29, 223.5.5.5 (UDP)
- [x] Nameserver DoH 已关闭 (doh.pub, dns.alidns.com)

### 自定义规则
- [x] DOMAIN-KEYWORD,github -> 代理
- [x] DOMAIN-KEYWORD,oculus -> 代理
- [x] DOMAIN-KEYWORD,facebook -> 代理

### 性能优化
- [x] tcp-concurrent: true
- [x] unified-delay: true
- [x] keep-alive-interval: 30
- [x] tcp_max_syn_backlog: 1024
- [x] tcp_fastopen: 3
- [x] nf_conntrack_max: 131072
- [x] Dnsmasq 缓存: 8000
- [x] Fake-IP 缓存持久化: 开启

### 自动更新
- [x] GeoIP/GeoSite/GeoASN/中国IP列表: 每天凌晨5点

### 内核
- [x] 已从 alpha-g34de62d (2025-05-24) 升级到 v1.19.20 (2026-02-08)
- [x] 旧内核备份: /etc/openclash/core/clash_meta.bak

---

## 待处理

- [ ] Copilot (copilot.microsoft.com) 连接失败, 需加前置规则走代理
