#!/usr/bin/env python3
"""
工作室路由器部署主节点-日本-sy 及 AI流量 分流组
路由器: root@192.168.2.1  Clash API Bearer: Oe4sHjG1
"""
import paramiko, time, io, json, urllib.request

ROUTER_IP   = '192.168.5.1'
SSH_USER    = 'root'
SSH_PASS    = '86461009'
API_BASE    = 'http://127.0.0.1:9090'   # 在路由器本地执行 curl
BEARER      = 'BeteqZ3V'

CUSTOM_DIR  = '/etc/openclash/custom'
OVERWRITE_SH = f'{CUSTOM_DIR}/openclash_custom_overwrite.sh'
INJECT_RB    = f'{CUSTOM_DIR}/inject_ai_group.rb'
RULES_LIST   = f'{CUSTOM_DIR}/openclash_custom_rules.list'

RUBY_CALL    = 'ruby /etc/openclash/custom/inject_ai_group.rb "$CONFIG_FILE" 2>/dev/null || true'

# ── 文件内容 ────────────────────────────────────────────────────────────────

INJECT_RB_CONTENT = """\
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
"""

RULES_LIST_CONTENT = """\
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
"""

# ── 工具函数 ────────────────────────────────────────────────────────────────

def ssh_run(client, cmd):
    _, out, err = client.exec_command(cmd)
    stdout = out.read().decode('utf-8', errors='replace').strip()
    stderr = err.read().decode('utf-8', errors='replace').strip()
    return stdout, stderr

def sftp_write(client, remote_path, content: str):
    """以 binary 模式上传文件，保留 LF 换行"""
    sftp = client.open_sftp()
    with sftp.open(remote_path, 'wb') as f:
        f.write(content.encode('utf-8'))
    sftp.close()

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def info(msg): print(f"  [INFO] {msg}")
def err(msg):  print(f"  [ERR]  {msg}")

# ── 阶段 A：检测 ─────────────────────────────────────────────────────────────

def phase_a(c):
    section("阶段 A：检测当前状态")
    status = {}

    # 1. custom 目录
    out, _ = ssh_run(c, f'test -d {CUSTOM_DIR} && echo exists || echo missing')
    status['custom_dir'] = (out == 'exists')
    (ok if status['custom_dir'] else warn)(f'{CUSTOM_DIR}: {out}')

    # 2. 三个文件
    for key, path in [('inject_rb', INJECT_RB), ('rules_list', RULES_LIST), ('overwrite_sh', OVERWRITE_SH)]:
        out, _ = ssh_run(c, f'test -f {path} && echo exists || echo missing')
        status[key] = (out == 'exists')
        (ok if status[key] else warn)(f'{path}: {out}')

    # 3. overwrite.sh 是否已含 ruby 调用行
    if status['overwrite_sh']:
        out, _ = ssh_run(c, f'grep -q "inject_ai_group.rb" {OVERWRITE_SH} && echo found || echo not_found')
        status['ruby_call'] = (out == 'found')
        (ok if status['ruby_call'] else warn)(f'ruby 调用行: {out}')
        if status['ruby_call']:
            info("overwrite.sh 已含 inject_ai_group.rb 调用，无需再次追加")
    else:
        status['ruby_call'] = False
        warn("overwrite.sh 不存在，稍后需创建")

    # 4. Clash API：AI流量 组是否存在
    out, _ = ssh_run(c, f'curl -s -H "Authorization: Bearer {BEARER}" '
                        f'http://127.0.0.1:9090/proxies/AI%E6%B5%81%E9%87%8F')
    try:
        d = json.loads(out)
        if 'name' in d:
            status['ai_group'] = True
            ok(f"AI流量 组已存在，当前节点: {d.get('now', '?')}")
        else:
            status['ai_group'] = False
            info(f"AI流量 组不存在（API 返回: {out[:80]}）")
    except Exception:
        status['ai_group'] = False
        info(f"API 响应非 JSON: {out[:80]}")

    # 5. 主节点-日本-sy 延迟（只在组已存在时测）
    if status['ai_group']:
        delay_url = ('http://127.0.0.1:9090/proxies/'
                     '%E4%B8%BB%E8%8A%82%E7%82%B9-%E6%97%A5%E6%9C%AC-sy'
                     '/delay?timeout=5000&url=http://www.gstatic.com/generate_204')
        out, _ = ssh_run(c, f'curl -s -H "Authorization: Bearer {BEARER}" "{delay_url}"')
        info(f"节点延迟: {out}")
    else:
        info("节点尚未注入，跳过延迟测试")

    return status

# ── 阶段 B：部署 ─────────────────────────────────────────────────────────────

def phase_b(c, status):
    section("阶段 B：部署文件")
    deployed = False

    # 确保 custom 目录存在
    if not status['custom_dir']:
        ssh_run(c, f'mkdir -p {CUSTOM_DIR}')
        ok(f"已创建 {CUSTOM_DIR}")

    # 1. inject_ai_group.rb
    if not status['inject_rb']:
        sftp_write(c, INJECT_RB, INJECT_RB_CONTENT)
        # 验证
        out, _ = ssh_run(c, f'head -1 {INJECT_RB}')
        ok(f"已上传 {INJECT_RB}  (head: {out})")
        deployed = True
    else:
        info(f"{INJECT_RB} 已存在，跳过上传")

    # 2. openclash_custom_rules.list
    if not status['rules_list']:
        sftp_write(c, RULES_LIST, RULES_LIST_CONTENT)
        out, _ = ssh_run(c, f'wc -l {RULES_LIST}')
        ok(f"已上传 {RULES_LIST}  ({out})")
        deployed = True
    else:
        info(f"{RULES_LIST} 已存在，跳过上传")

    # 3. openclash_custom_overwrite.sh：追加 ruby 调用行
    if not status['ruby_call']:
        if status['overwrite_sh']:
            # 读取现有内容
            out, _ = ssh_run(c, f'cat {OVERWRITE_SH}')
            existing = out
        else:
            existing = '#!/bin/sh\n'

        # 在 exit 0 之前插入（或追加到末尾）
        if 'exit 0' in existing:
            new_content = existing.replace('exit 0', f'{RUBY_CALL}\nexit 0', 1)
        else:
            # 末尾追加
            new_content = existing.rstrip('\n') + f'\n{RUBY_CALL}\n'

        sftp_write(c, OVERWRITE_SH, new_content)
        # 验证注入成功
        out2, _ = ssh_run(c, f'grep -c "inject_ai_group.rb" {OVERWRITE_SH}')
        ok(f"已修改 {OVERWRITE_SH}，ruby 调用行数: {out2}")
        deployed = True
    else:
        info("ruby 调用行已在 overwrite.sh 中，跳过")

    return deployed

# ── 阶段 C：重启 + 验证 ──────────────────────────────────────────────────────

def phase_c(c, skip_restart=False):
    section("阶段 C：重启 OpenClash 并验证")

    if skip_restart:
        info("（跳过重启，直接验证）")
    else:
        info("正在重启 OpenClash……")
        ssh_run(c, '/etc/init.d/openclash restart')
        info("等待 15 秒让服务启动……")
        time.sleep(15)

    # 1. DNS 验证
    out, _ = ssh_run(c, 'nslookup cdn.magicfind.vc 2>&1 | grep -E "Address|address"')
    if '167.179.67.171' in out:
        ok(f"DNS 正常：{out}")
    else:
        warn(f"DNS 返回: {out}  （期望 167.179.67.171，若含 198.18.x.x 说明 Fake-IP 污染未解）")

    # 2. 节点延迟
    delay_url = ('http://127.0.0.1:9090/proxies/'
                 '%E4%B8%BB%E8%8A%82%E7%82%B9-%E6%97%A5%E6%9C%AC-sy'
                 '/delay?timeout=5000&url=http://www.gstatic.com/generate_204')
    out, _ = ssh_run(c, f'curl -s -H "Authorization: Bearer {BEARER}" "{delay_url}"')
    try:
        d = json.loads(out)
        if 'delay' in d:
            ok(f"节点延迟: {d['delay']} ms")
        else:
            warn(f"延迟 API 响应: {out}")
    except Exception:
        warn(f"延迟 API 响应（非JSON）: {out[:120]}")

    # 3. AI流量 组
    out, _ = ssh_run(c, f'curl -s -H "Authorization: Bearer {BEARER}" '
                        f'http://127.0.0.1:9090/proxies/AI%E6%B5%81%E9%87%8F')
    try:
        d = json.loads(out)
        if 'name' in d:
            ok(f"AI流量 组存在，proxies: {d.get('all', [])}")
        else:
            warn(f"AI流量 组不存在: {out[:120]}")
    except Exception:
        warn(f"AI流量 API 响应（非JSON）: {out[:120]}")

# ── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    print(f"\n>>> 工作室路由器部署脚本  目标: {ROUTER_IP}")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(ROUTER_IP, username=SSH_USER, password=SSH_PASS, timeout=10)
        ok(f"SSH 已连接到 {ROUTER_IP}")
    except Exception as e:
        err(f"SSH 连接失败: {e}")
        return

    try:
        status   = phase_a(c)
        deployed = phase_b(c, status)

        if deployed:
            phase_c(c, skip_restart=False)
        else:
            section("无需部署")
            info("所有文件已存在且配置完整，检测现有运行状态……")
            phase_c(c, skip_restart=True)

    finally:
        c.close()
        print("\n>>> 完成\n")

if __name__ == '__main__':
    main()
