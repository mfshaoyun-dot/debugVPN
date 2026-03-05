# OpenClash 配置优化指南

基于实际调试经验总结，适用于 OpenWrt + OpenClash (Mihomo 内核) 环境。

---

## 一、整体架构：三层分流

配置好后的流量处理顺序：

```
客户端流量
  │
  ├─ 第一层：防火墙（china_ip_route）
  │    中国 IP → 直接放行，不进入 Clash
  │
  ├─ 第二层：自定义前置规则
  │    仅做安全兜底（如 github/oculus/facebook 走代理）
  │
  ├─ 第三层：订阅规则（机场提供）
  │    域名级精细分流（google 代理、microsoft.com 直连、bing 代理等）
  │
  └─ 兜底：MATCH → 代理组
       以上都没匹配的，走代理
```

### 关键设置

| 设置项 | 位置 | 推荐值 |
|--------|------|--------|
| 中国 IP 绕过 | 插件设置 → 模式设置 | `china_ip_route` 开启 |
| DNS 劫持 | 插件设置 → DNS 设置 | Dnsmasq 转发（`enable_redirect_dns=1`） |
| IPv6 代理 | 插件设置 | 关闭（`ipv6_enable=0`） |
| 自定义规则 | 插件设置 → 规则设置 | 开启 |
| WAN DNS 追加 | 插件设置 → DNS 设置 | **关闭**（`append_wan_dns=0`，避免运营商 DNS 混入） |
| AAAA 过滤 | DHCP/DNS → 高级设置 | **开启**（IPv6 已禁用，过滤无用 AAAA 记录） |
| Dnsmasq noresolv | DHCP/DNS | **开启**（不读运营商 DNS） |
| Fake-IP 缓存持久化 | 插件设置 | **开启**（`store_fakeip=1`，重启后不丢缓存） |
| Dnsmasq 缓存 | 插件设置 → DNS 设置 | `8000`（由 OpenClash 管理） |

---

## 二、自定义规则

文件路径：`/etc/openclash/custom/openclash_custom_rules.list`

### 开启了 `china_ip_route` 时（推荐）

防火墙层已处理中国 IP 绕过，自定义规则只需做安全兜底：

```
# --- 自定义前置规则 ---
# 防火墙层已开启 china_ip_route（中国 IP 绕过）
# 订阅规则已包含完整的国内外分流
# 此处仅作为安全兜底

- DOMAIN-KEYWORD,github,代理组名
- DOMAIN-KEYWORD,oculus,代理组名
- DOMAIN-KEYWORD,facebook,代理组名
- DOMAIN-KEYWORD,copilot,代理组名

# --- 结束 ---
```

> 将 `代理组名` 替换为你的实际代理组名称（如 `TNTCloud`、`Proxy` 等）。
>
> `oculus` / `facebook`：Meta 系服务的部分域名 IP 被 GeoIP 误判为中国 → DIRECT，实际国内不通。前置规则兜底走代理。
>
> `copilot`：`copilot.microsoft.com` 被订阅规则中的微软域名匹配到 DIRECT，但国内直连不通。前置规则兜底走代理。

### 未开启 `china_ip_route` 时

需要在规则层自行处理国内分流：

```
# 1. 局域网直连
- IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
- IP-CIDR,10.0.0.0/8,DIRECT,no-resolve

# 2. GitHub 走代理（必须在 microsoft 之前）
- DOMAIN-KEYWORD,github,代理组名

# 3. 国内服务直连
- GEOSITE,cn,DIRECT
- GEOSITE,apple,DIRECT
- GEOSITE,microsoft,DIRECT

# 4. 中国 IP 兜底直连
- GEOIP,cn,DIRECT,no-resolve
```

### 不要在自定义规则中放 `GEOSITE,microsoft,DIRECT`

订阅规则通常对微软服务做了精细分流：

| 域名 | 订阅路由 | 原因 |
|------|----------|------|
| `microsoft.com` | DIRECT | 国内可用 |
| `office.com` | DIRECT | 国内可用 |
| `bing.com` | **代理** | 国际版 Bing/Copilot 需要代理 |
| `outlook.com` | **代理** | 国际版需要代理 |
| `onedrive.com` | **代理** | 需要代理 |
| `live.com` | **代理** | 需要代理 |
| `github.com` | **代理** | 需要代理 |

自定义规则的 `GEOSITE,microsoft,DIRECT` 会在订阅规则之前加载，**把以上全部强制直连**，覆盖订阅的精细分流。所以不要加这条规则。

---

## 三、DNS 配置（最关键）

### 核心原则
- **Nameserver**（国内解析）：只放国内 DNS，直连可达
- **Fallback**（国外解析）：放海外 DNS，会走代理，至少 2 个保证冗余
- **proxy-server-nameserver**（解析代理节点域名）：只放国内 DNS，打破鸡生蛋死锁

### 推荐配置

#### Nameserver（必须手动设置，不要依赖自动补全）
| 地址 | 类型 |
|------|------|
| `223.5.5.5` | UDP |
| `119.29.29.29` | UDP |

#### Fallback（至少两个海外 DNS，互相备份）
| 地址 | 类型 |
|------|------|
| `https://dns.google/dns-query` | HTTPS (DoH) |
| `https://dns.cloudflare.com/dns-query` | HTTPS (DoH) |

#### Default
| 地址 | 类型 |
|------|------|
| `223.5.5.5` | UDP |
| `114.114.114.114` | UDP |
| `119.29.29.29` | UDP |

#### 不要在 Fallback 中放的
| 地址 | 原因 |
|------|------|
| `1.1.1.1` (UDP) | 会被兜底规则匹配走代理，代理不稳定时产生大量报错 |
| `doh.dns.sb` | TLS 证书经常异常 |
| `8.8.8.8` (UDP) | 国内直连不通，走代理又依赖代理本身 |
| `doh.pub/dns-query` | **国内 DoH 服务**，放在 fallback 失去防污染意义 |

#### Fallback Filter
```yaml
fallback-filter:
  geoip: true
  geoip-code: CN
  ipcidr:
    - 240.0.0.0/4
```

### DNS 死锁问题

```
代理节点域名需要 DNS 解析
  → DNS 配置了海外 DoH
    → 海外 DoH 需要走代理
      → 代理需要先解析节点域名
        → 死循环
```

**解决方法：** 确保 `proxy-server-nameserver` 只包含国内可直连的 DNS：
```yaml
proxy-server-nameserver:
  - 114.114.114.114
  - 119.29.29.29
```

如果开启了 `respect-rules`，OpenClash 会自动填充此项，注意检查是否混入了 `8.8.8.8` 和 `1.1.1.1`。

### 关闭 WAN DNS 追加

`append_wan_dns=1` 会把 WAN 口获取到的运营商 DNS 自动加入解析列表，导致每次 DNS 查询多一次无用请求。

```bash
uci set openclash.config.append_wan_dns='0'
uci commit openclash
```

---

## 四、关闭 IPv6（防止绕过代理）

### 问题
客户端获取到 IPv6 地址后会绕过 OpenClash 直接出网，导致：
- 部分网站走 IPv6 直连而非代理，出现连接异常
- OpenClash 启动时警告：`检测到您启用了IPv6的DHCP服务，可能会造成连接异常`

### 检测逻辑
OpenClash 在 `/etc/init.d/openclash` 中检查 `dhcp.lan.dhcpv6`：
- 值为空或 `disabled` → 正常启动，无警告
- 值不为 `disabled` 且 OpenClash 未开启 IPv6 代理（`ipv6_enable=0`）→ 警告

### SSH 操作

```bash
# 1. 关闭 LAN 侧 IPv6 分发
uci set dhcp.lan.ra='disabled'
uci set dhcp.lan.dhcpv6='disabled'
uci set dhcp.lan.ndp='disabled'
uci set dhcp.lan.ra_management='0'
uci delete dhcp.lan.ra_flags 2>/dev/null
uci commit dhcp

# 2. 禁用 WAN6 接口
uci set network.wan6.auto='0'
uci commit network

# 3. 开启 AAAA 记录过滤（IPv6 已禁用，过滤无用记录）
uci set dhcp.@dnsmasq[0].filter_aaaa='1'
uci commit dhcp

# 4. 重启服务
/etc/init.d/odhcpd restart
/etc/init.d/network restart
/etc/init.d/openclash restart
```

### LuCI 界面操作（等效）
1. **网络 → 接口 → LAN → DHCP 服务器 → IPv6 设置**：
   - RA 服务：已禁用
   - DHCPv6 服务：已禁用
   - NDP 代理：已禁用
2. **网络 → 接口 → WAN6**：勾选「不启动」或直接删除该接口

### 配置前后对比

| 配置项 | 改前 | 改后 |
|--------|------|------|
| `dhcp.lan.ra` | `hybrid` / `server` | `disabled` |
| `dhcp.lan.dhcpv6` | `hybrid` / `server` | `disabled` |
| `dhcp.lan.ndp` | `hybrid` | `disabled` |
| `dhcp.lan.ra_management` | `1` | `0` |
| `dhcp.@dnsmasq[0].filter_aaaa` | `0` | `1` |
| `network.wan6.auto` | (启用) | `0` |

---

## 五、Mihomo 性能优化

### 覆盖脚本

文件路径：`/etc/openclash/custom/openclash_custom_overwrite.sh`

通过此脚本在每次启动时注入 Mihomo 高级特性：

```bash
# --- 自定义性能优化 ---
# TCP 并发：同时尝试多个 IP，取最快响应
ruby_edit "$CONFIG_FILE" "['tcp-concurrent']" "true"
# 统一延迟：让节点测速更准确
ruby_edit "$CONFIG_FILE" "['unified-delay']" "true"
# 连接保活间隔（秒）
ruby_edit "$CONFIG_FILE" "['keep-alive-interval']" "30"
```

### TCP 内核参数优化

```bash
# 提升 TCP SYN 队列（默认 128，高并发时不够）
sysctl -w net.ipv4.tcp_max_syn_backlog=1024
# 启用 TFO 客户端+服务端（默认仅客户端 =1）
sysctl -w net.ipv4.tcp_fastopen=3
# 提升连接跟踪表（默认 65536，代理场景连接数多）
sysctl -w net.netfilter.nf_conntrack_max=131072

# 持久化到 /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog=1024' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_fastopen=3' >> /etc/sysctl.conf
echo 'net.netfilter.nf_conntrack_max=131072' >> /etc/sysctl.conf
```

### Geo 数据库自动更新

建议统一更新时间，避免分散在不同时间段反复重启：

```bash
# 开启自动更新
uci set openclash.config.geo_auto_update='1'
uci set openclash.config.geoip_auto_update='1'
uci set openclash.config.geosite_auto_update='1'
uci set openclash.config.geoasn_auto_update='1'
uci set openclash.config.chnr_auto_update='1'

# 统一到凌晨 5 点更新
uci set openclash.config.geosite_update_day_time='5'
uci set openclash.config.geoip_update_day_time='5'
uci set openclash.config.geo_update_day_time='5'
uci set openclash.config.chnr_update_day_time='5'
uci commit openclash
```

---

## 六、GeoSite 数据库

### 常见坑
- `GeoSite.dat` 默认版本可能不包含 `microsoft-cn`、`apple-cn` 等细分标签，使用会导致内核 FATAL 崩溃
- 应使用通用标签：`microsoft`、`apple`、`cn`
- 建议更新为 Loyalsoldier 增强版（包含更多分类）

---

## 七、Mihomo 内核更新

### 更新前必做：备份旧内核

```bash
cp /etc/openclash/core/clash_meta /etc/openclash/core/clash_meta.bak
```

### 回滚（出问题时一条命令恢复）

```bash
# 恢复旧内核
cp /etc/openclash/core/clash_meta.bak /etc/openclash/core/clash_meta
# 重启 OpenClash
/etc/init.d/openclash restart
```

### 更新方式

在 OpenClash 后台 → 插件设置 → 版本更新 → 检查并更新 Meta 内核。

### 为什么要更新

以 v1.19.20（2026-02-08）相比旧版 alpha（2025-07）为例：

| 类型 | 内容 | 影响 |
|------|------|------|
| 安全修复 | CVE-2025-68121 crypto/tls 漏洞 | TLS 是所有加密连接的基础（trojan 代理、DoH、HTTPS），不修可能被劫持/窃听 |
| Bug 修复 | tcp-concurrent 竞态条件 | 多连接并发拨号时线程互相干扰，可能连接失败或崩溃 |
| Bug 修复 | trojan 监听器 SNAT panic | trojan 协议数据包处理的致命 bug，特定条件下内核直接崩溃退出 |
| 新功能 | `proxy-server-nameserver-policy` | 可按策略组分配不同 DNS 解析 |
| 新功能 | DoT 连接复用 | DNS-over-TLS 性能提升 |
| 优化 | DoH TLS 探测超时控制 | 减少 DNS 超时等待时间 |

---

## 八、常见报错速查

| 报错关键词 | 原因 | 解决 |
|-----------|------|------|
| `list xxx not found in GeoSite.dat` | GeoSite 数据库缺少该分类 | 更新数据库或改用存在的标签名 |
| `dns resolve failed: context deadline exceeded` | DNS 服务器不可达或超时 | 检查 DNS 配置，国内外分离 |
| `fake DNS record xxx missing` | 重启后 Fake-IP 缓存丢失 | 开启 `store_fakeip=1` 持久化缓存 |
| `tls: failed to verify certificate` | DoH 服务器证书异常 | 换掉该 DNS（如 doh.dns.sb） |
| `operation was canceled` | 代理节点连接被取消 | 节点不稳定，换节点或检查端口 |
| `because 自动选择 failed multiple times` | 自动选择组健康检查失败 | 手动选可用节点或缩小自动选择范围 |
| `Nameserver 未设置服务器，开始补全` | DNS Nameserver 为空 | 手动在 DNS 设置中填入国内 DNS |
| `match GeoSite/microsoft → github.com DIRECT` | GitHub 被微软规则拦截 | 在 microsoft 前加 github 代理规则 |
| `IPv6's DHCP Server` 警告 | LAN 侧 DHCPv6 未关闭 | 见第四节关闭 IPv6 |
| `https://https://dns.google/...` | DNS 配置 type=udp 但 ip 填了完整 URL | 修正 type 为 https 或修正 ip 为纯地址 |
| `graph.oculus.com i/o timeout DIRECT` | Meta 系域名 IP 被 GeoIP 误判为中国 | 添加 `DOMAIN-KEYWORD,oculus,代理组名` 前置规则 |
| `copilot.microsoft.com` 连接失败 | 被订阅规则中的微软域名匹配到 DIRECT | 添加 `DOMAIN-KEYWORD,copilot,代理组名` 前置规则 |

---

## 九、配置变更操作参考 (SSH)

```bash
# 查看当前 DNS 配置
uci show openclash | grep dns_servers

# 禁用某个 DNS 服务器（如 1.1.1.1）
uci show openclash | grep "1.1.1.1"   # 找到对应 cfg ID
uci set openclash.cfgXXXXXX.enabled='0'
uci commit openclash

# 查看当前自定义规则
cat /etc/openclash/custom/openclash_custom_rules.list

# 编辑自定义规则
vi /etc/openclash/custom/openclash_custom_rules.list

# 查看当前订阅配置的规则部分
grep -n 'rules:' /etc/openclash/config/*.yaml
grep -E 'DOMAIN|GEOSITE|GEOIP|MATCH' /etc/openclash/config/*.yaml

# 查看绕过和代理相关设置
uci show openclash.config | grep -i 'china_ip\|bypass\|ipv6\|dns'

# 重启 OpenClash
/etc/init.d/openclash restart

# 查看实时内核日志
tail -f /tmp/openclash.log

# 统计 warning 数量（0 为正常）
grep -c 'level=warning' /tmp/openclash.log

# 查看插件启动日志
logread | grep openclash

# 内核备份与回滚
cp /etc/openclash/core/clash_meta /etc/openclash/core/clash_meta.bak   # 备份
cp /etc/openclash/core/clash_meta.bak /etc/openclash/core/clash_meta   # 回滚
```

---

## 十、验证清单

配置完成后，检查日志确认以下几点：

- [ ] 无 `level=fatal` 错误
- [ ] `level=warning` 数量为 0 或极少
- [ ] 国内 DNS（119.29.29.29、223.5.5.5）显示 `using DIRECT`
- [ ] **不出现** `192.168.71.x`（运营商 DNS）的查询
- [ ] 海外网站（google、youtube、facebook）显示 `using 代理组名[节点名]`
- [ ] `github.com` 匹配 `DomainKeyword(github)` 走代理，而非 `GeoSite(microsoft)` 直连
- [ ] `graph.oculus.com` 匹配 `DomainKeyword(oculus)` 走代理，而非 `GeoIP(cn)` 直连
- [ ] `copilot.microsoft.com` 匹配 `DomainKeyword(copilot)` 走代理，而非微软域名直连
- [ ] `bing.com`、`outlook.com`、`onedrive.com` 走代理（非直连）
- [ ] 无大量 `1.1.1.1:53 operation was canceled` 报错
- [ ] 国内网站（baidu、qq、taobao）显示 `using DIRECT`
- [ ] 启动日志显示 `OpenClash Start Successful!`（无 IPv6 DHCP 警告）

---

## 十一、代理出口 IP 安全检测

### 为什么要检查

使用代理访问 Google Gemini、ChatGPT 等 AI 服务时，如果出口 IP 被标记为 VPN/代理/数据中心 IP，可能导致：
- 账号被封禁或限制
- 触发额外的人机验证
- 服务不可用

### 检测方法

```bash
# 1. 查看出口 IP
curl -s https://api-ipv4.ip.sb/ip

# 2. 查看 IP 详细信息（地理位置、ISP、ASN）
curl -s https://ipinfo.io

# 3. 检测是否被标记为代理/数据中心（关键）
curl -s 'http://ip-api.com/json/<你的出口IP>?fields=status,country,city,isp,org,as,hosting,proxy'

# 4. 查看 IP 归属详情
curl -s 'https://ipwhois.app/json/<你的出口IP>'
```

### 关键指标解读

| 字段 | 安全值 | 危险值 | 说明 |
|------|--------|--------|------|
| `proxy` | `false` | `true` | 是否被识别为代理 IP |
| `hosting` | `false` | `true` | 是否为数据中心/云服务商 IP |
| ISP | 本地运营商名称 | AWS/GCP/Vultr/搬瓦工等 | 云厂商 IP 容易被封 |
| 主机名 | 含 `dynamic-ip`/`residential` | 含 `vps`/`server`/`cloud` | 住宅 IP 特征更安全 |

### 风险等级判断

| 等级 | 条件 | 建议 |
|------|------|------|
| 低风险 | `proxy=false` + `hosting=false` + 本地 ISP | 放心使用 |
| 中风险 | `proxy=true` + `hosting=false` | 可用，但避免频繁切换节点 |
| 高风险 | `hosting=true` 或 ISP 为知名云厂商 | 建议换节点 |

### 降低被封风险的建议

1. **选择住宅 IP 节点** — `hosting=false` 的节点优先
2. **避免频繁切换节点** — IP 跳动是最大的风控触发因素
3. **选择小众 ISP** — 不在主流 VPN 黑名单上的本地小运营商
4. **地区一致性** — 尽量固定使用同一地区（如台湾）的节点
5. **避开热门 VPN 段** — AWS、GCP、Vultr、DigitalOcean 等云厂商 IP 段被重点监控

### 实测参考（台湾节点）

```
IP:       103.137.247.55
位置:     台北，台湾 (TW)
ISP:      Pittqiao Network Information Co., Ltd.
ASN:      AS131642
主机名:   103-137-247-55.dynamic-ip.pni.tw
proxy:    true（有代理使用记录）
hosting:  false（非数据中心）
风险等级: 中等 — 非机房 IP、小众 ISP、dynamic-ip 住宅特征
```

---

## 十二、网络性能基准测试

### 测试方法

```bash
# 国内下载速度（直连）
curl -o /dev/null -s -w 'speed: %{speed_download} bytes/s\n' \
  'http://mirrors.aliyun.com/debian/dists/bookworm/Release' --max-time 15

# 海外下载速度（走代理）
curl -o /dev/null -s -w 'speed: %{speed_download} bytes/s\n' \
  'https://speed.cloudflare.com/__down?bytes=10000000' --max-time 20

# 首字节延迟 TTFB（更准确的延迟指标）
curl -o /dev/null -s -w 'TTFB: %{time_starttransfer}s\n' \
  'https://www.google.com' --max-time 10
```

### 实测基准

#### 2026-03-05 (优化后，v1.19.20，出口 103.220.218.92 台北)

**下载速度**

| 目标 | 路径 | 速度 |
|------|------|------|
| 阿里云镜像 | DIRECT | 1.67 MB/s |
| Cloudflare 10MB | 代理 | **15.3 MB/s** |

**首字节延迟 (TTFB)**

| 目标 | 路径 | 延迟 |
|------|------|------|
| 淘宝 | DIRECT | 80ms |
| 百度 | DIRECT | 107ms |
| Anthropic API | 代理 | 150ms |
| Claude | 代理 | 184ms |
| ChatGPT | 代理 | 241ms |
| HuggingFace | 代理 | 259ms |
| YouTube | 代理 | 286ms |
| Google | 代理 | 303ms |
| Google Gemini | 代理 | 345ms |

**AI 服务连通性**

| 服务 | 状态 | 说明 |
|------|------|------|
| ChatGPT / OpenAI API | OK | |
| Claude / Anthropic API | OK | |
| Google Gemini / AI Studio | OK | |
| HuggingFace | OK | |
| Perplexity | OK | |
| Grok (xAI) | OK | |
| Copilot | FAIL | 需加前置规则 `DOMAIN-KEYWORD,copilot` |

#### 2025 首次调试 (台湾-05 节点，旧内核)

**下载速度**

| 目标 | 路径 | 速度 |
|------|------|------|
| 阿里云镜像 | DIRECT | 1.02 MB/s |
| 华为云镜像 | DIRECT | 0.89 MB/s |
| Cloudflare 10MB | 代理 | **11.3 MB/s** |

**首字节延迟 (TTFB)**

| 目标 | 路径 | 延迟 |
|------|------|------|
| 阿里云 | DIRECT | 18ms |
| 百度 | DIRECT | 28ms |
| Google | 代理 | 261ms |
| Cloudflare | 代理 | 313ms |
| YouTube | 代理 | 376ms |

> 优化后代理下载速度从 11.3 MB/s 提升到 15.3 MB/s，代理延迟整体下降。
