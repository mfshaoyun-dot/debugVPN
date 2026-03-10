# 主节点-日本-sy 配置说明

> 配置日期：2026-03-10
> 路由器：192.168.2.1（OpenWrt + OpenClash/Mihomo）

---

## 节点信息

| 项目 | 值 |
|------|----|
| 名称 | 主节点-日本-sy |
| 协议 | Trojan |
| 服务器 | cdn.magicfind.vc |
| 出口 IP | 167.179.67.171 |
| 端口 | 443 |
| 地理 | 日本 东京（South Shinagawa，Vultr）|
| ISP | The Constant Company, LLC |
| SNI | cdn.magicfind.vc |
| ALPN | h2, http/1.1 |
| skip-cert-verify | true |

---

## 用途

**专用于 AI 服务流量分流**，挂载在 `AI流量` 代理组下。

AI流量 代理组覆盖的域名规则（`/etc/openclash/custom/openclash_custom_rules.list`）：

```
anthropic.com / claude.ai / platform.claude.com / openai.com / chatgpt.com
oaistatic.com / oaiusercontent.com
generativelanguage.googleapis.com / gemini.google.com / aistudio.google.com
perplexity.ai / huggingface.co
```

---

## 路由器侧配置文件

### 1. 覆写脚本：`/etc/openclash/custom/openclash_custom_overwrite.sh`

在 OpenClash 每次启动时自动执行，调用注入脚本：

```sh
ruby_edit "$CONFIG_FILE" "['tcp-concurrent']" "true"
ruby_edit "$CONFIG_FILE" "['unified-delay']" "true"
ruby_edit "$CONFIG_FILE" "['keep-alive-interval']" "30"
ruby /etc/openclash/custom/inject_ai_group.rb "$CONFIG_FILE" 2>/dev/null || true
```

### 2. 注入脚本：`/etc/openclash/custom/inject_ai_group.rb`

完整内容：

```ruby
require 'yaml'

config_file = ARGV[0]
c = YAML.load_file(config_file)

# 1. 注入节点
np = {
  'name'             => '主节点-日本-sy',
  'type'             => 'trojan',
  'server'           => 'cdn.magicfind.vc',
  'port'             => 443,
  'password'         => 'bAlkAx3I5o',
  'udp'              => true,
  'sni'              => 'cdn.magicfind.vc',
  'alpn'             => ['h2', 'http/1.1'],
  'skip-cert-verify' => true
}
(c['proxies'] ||= []) << np unless (c['proxies'] || []).any? { |p| p['name'] == '主节点-日本-sy' }

# 2. 注入 AI流量 代理组（置顶）
ag = {
  'name'    => 'AI流量',
  'type'    => 'select',
  'proxies' => ['主节点-日本-sy', 'TNTCloud']
}
unless (c['proxy-groups'] || []).any? { |g| g['name'] == 'AI流量' }
  (c['proxy-groups'] ||= []).unshift(ag)
end

# 3. 将节点域名加入 fake-ip-filter，防止被 Fake-IP 污染导致连接失败
fif = c.dig('dns', 'fake-ip-filter') || []
node_domain = 'cdn.magicfind.vc'
unless fif.include?(node_domain)
  fif << node_domain
  c['dns'] ||= {}
  c['dns']['fake-ip-filter'] = fif
end

File.write(config_file, c.to_yaml)
puts "注入完成: #{(c['proxies']||[]).length} 个节点, #{(c['proxy-groups']||[]).length} 个代理组, fake-ip-filter: #{fif.length} 条"
```

### 3. 规则文件：`/etc/openclash/custom/openclash_custom_rules.list`

放在订阅规则之前，确保 AI 域名优先命中 AI流量 组：

```
- DOMAIN-SUFFIX,anthropic.com,AI流量
- DOMAIN-SUFFIX,claude.ai,AI流量
- DOMAIN-SUFFIX,platform.claude.com,AI流量
- DOMAIN-SUFFIX,openai.com,AI流量
- DOMAIN-SUFFIX,chatgpt.com,AI流量
- DOMAIN-SUFFIX,oaistatic.com,AI流量
- DOMAIN-SUFFIX,oaiusercontent.com,AI流量
- DOMAIN-SUFFIX,generativelanguage.googleapis.com,AI流量
- DOMAIN-SUFFIX,gemini.google.com,AI流量
- DOMAIN-SUFFIX,aistudio.google.com,AI流量
- DOMAIN-SUFFIX,perplexity.ai,AI流量
- DOMAIN-SUFFIX,huggingface.co,AI流量
```

---

## 关键修复：fake-ip-filter 防污染

**问题**：`cdn.magicfind.vc` 被 Clash Fake-IP 池解析为内部虚假 IP（`198.18.x.x`），Trojan 拿着假 IP 建连失败。

**原因链**：OpenClash 启用 `respect-rules` 时，自动向 `proxy-server-nameserver` 补入 `8.8.8.8/1.1.1.1`，这两个 DNS 本身要走代理，但代理还没建立，死锁导致节点域名解析退化到 Fake-IP。

**修复**：在 `inject_ai_group.rb` 中将 `cdn.magicfind.vc` 加入 `dns.fake-ip-filter`，让该域名绕过 Fake-IP 直接走真实 DNS 解析。

---

## 在新机器上部署

### 前提

- OpenWrt 路由器已安装 OpenClash（Mihomo 内核）
- SSH 可免密登录路由器

### 部署步骤

```bash
ROUTER="root@192.168.2.1"

# 1. 上传注入脚本
scp 主节点-日本-sy-配置说明.md $ROUTER:/tmp/  # 参考用

# 2. 在路由器上创建注入脚本
ssh $ROUTER "cat > /etc/openclash/custom/inject_ai_group.rb" << 'EOF'
# （粘贴上面 inject_ai_group.rb 完整内容）
EOF

# 3. 在路由器上创建规则文件
ssh $ROUTER "cat > /etc/openclash/custom/openclash_custom_rules.list" << 'EOF'
# （粘贴上面规则内容）
EOF

# 4. 修改覆写脚本，添加 ruby 调用行
# 在 /etc/openclash/custom/openclash_custom_overwrite.sh 末尾 exit 0 之前添加：
# ruby /etc/openclash/custom/inject_ai_group.rb "$CONFIG_FILE" 2>/dev/null || true

# 5. 重启 OpenClash
ssh $ROUTER "/etc/init.d/openclash restart"
```

### OpenClash Web 界面设置

| 设置项 | 值 |
|--------|-----|
| 覆写设置 → 启用自定义覆写 | ✅ 开启 |
| 覆写设置 → 启用自定义规则 | ✅ 开启 |
| DNS 设置 → Fake-IP 模式 | 开启（由脚本自动加 filter） |
| respect-rules | 开启（覆写脚本中已处理副作用） |

---

## 验证方法

### 1. 确认 DNS 解析正常（不再返回 Fake-IP）

```bash
ssh root@192.168.2.1 "nslookup cdn.magicfind.vc"
# 期望：返回 167.179.67.171，而非 198.18.x.x
```

### 2. 测试节点延迟

```bash
ssh root@192.168.2.1 "curl -s 'http://127.0.0.1:9090/proxies/%E4%B8%BB%E8%8A%82%E7%82%B9-%E6%97%A5%E6%9C%AC-sy/delay?timeout=5000&url=http://www.gstatic.com/generate_204' -H 'Authorization: Bearer Oe4sHjG1'"
# 期望：{"delay": 数字}，不是 {"message":"timeout"}
```

### 3. 确认 AI 流量走该节点

```bash
ssh root@192.168.2.1 "curl -s 'http://127.0.0.1:9090/connections' -H 'Authorization: Bearer Oe4sHjG1' | tr ',' '\n' | grep -A2 '日本-sy'"
# 期望：出现 "chains":["主节点-日本-sy","AI流量"]
```

### 4. Clash 控制台直接查看

浏览器打开 `http://192.168.2.1:9090/ui` → Connections 标签，实时可见每条连接的节点链路。

---

## AI 服务测试结果（2026-03-10）

| 服务 | 主节点-日本-sy | TNTCloud 日本-04 |
|------|:------------:|:--------------:|
| Claude API | 219ms ✅ | 247ms ✅ |
| OpenAI API | 877ms | 271ms |
| Gemini | 556ms | 343ms |
| GH Copilot | 703ms | 273ms |

**结论**：Claude API 略优（219ms vs 247ms），其他服务 TNTCloud 更快。专用于 Claude/Anthropic 场景时选主节点-日本-sy。

---

## Clash API 参考

| 操作 | 命令 |
|------|------|
| 查看 AI流量 当前节点 | `curl -s 'http://127.0.0.1:9090/proxies/AI%E6%B5%81%E9%87%8F' -H 'Authorization: Bearer Oe4sHjG1'` |
| 切换到主节点 | `curl -X PUT 'http://127.0.0.1:9090/proxies/AI%E6%B5%81%E9%87%8F' -d '{"name":"主节点-日本-sy"}'` |
| 切换到 TNTCloud | `curl -X PUT 'http://127.0.0.1:9090/proxies/AI%E6%B5%81%E9%87%8F' -d '{"name":"TNTCloud"}'` |
| 测节点延迟 | `curl -s 'http://127.0.0.1:9090/proxies/%E4%B8%BB%E8%8A%82%E7%82%B9-%E6%97%A5%E6%9C%AC-sy/delay?timeout=5000&url=http://www.gstatic.com/generate_204'` |
