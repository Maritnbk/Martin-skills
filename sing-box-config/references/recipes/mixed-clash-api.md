# mixed + Clash API 客户端

适用版本：**1.14.0 及以上**（用到 `$schema`）。
1.11–1.13 删除 `$schema` 即可；`clash_api` 和 `cache_file` 在这些版本可用。

依赖页面：
[Mixed](https://sing-box.sagernet.org/configuration/inbound/mixed/) ·
[Selector](https://sing-box.sagernet.org/configuration/outbound/selector/) ·
[URLTest](https://sing-box.sagernet.org/configuration/outbound/urltest/) ·
[Clash API](https://sing-box.sagernet.org/configuration/experimental/clash-api/) ·
[Cache File](https://sing-box.sagernet.org/configuration/experimental/cache-file/)

已知限制：`external_controller` 默认只监听本机；要暴露到局域网必须同时设 `secret`，
并确认防火墙。Clash API 的 `secret` 不是传输加密，公网暴露应加反向代理和 TLS。

```jsonc
{
  "$schema": "https://sing-box.sagernet.org/schema.json",

  "log": {
    "level": "info",
    "timestamp": true
  },

  "dns": {
    "servers": [
      { "type": "local", "tag": "dns-local" },
      {
        "type": "udp",
        "tag": "dns-remote",
        "server": "1.1.1.1",
        "detour": "proxy"
      }
    ],
    "final": "dns-remote"
  },

  "inbounds": [
    {
      "type": "mixed",
      "tag": "mixed-in",
      "listen": "127.0.0.1",
      "listen_port": 2080,
      "set_system_proxy": false
    }
  ],

  "outbounds": [
    {
      "type": "selector",
      "tag": "proxy",
      "outbounds": ["auto", "direct"],
      "default": "auto"
    },
    {
      "type": "urltest",
      "tag": "auto",
      "outbounds": ["vless-a", "vless-b"],
      "url": "https://www.gstatic.com/generate_204",
      "interval": "3m",
      "tolerance": 50
    },
    {
      "type": "vless",
      "tag": "vless-a",
      "server": "203.0.113.10",
      "server_port": 443,
      "uuid": "00000000-0000-4000-8000-000000000000",
      "tls": {
        "enabled": true,
        "server_name": "a.example.com",
        "utls": { "enabled": true, "fingerprint": "chrome" }
      }
    },
    {
      "type": "vless",
      "tag": "vless-b",
      "server": "203.0.113.11",
      "server_port": 443,
      "uuid": "00000000-0000-4000-8000-000000000001",
      "tls": {
        "enabled": true,
        "server_name": "b.example.com",
        "utls": { "enabled": true, "fingerprint": "chrome" }
      }
    },
    { "type": "direct", "tag": "direct" }
  ],

  "route": {
    "rules": [
      { "ip_is_private": true, "action": "route", "outbound": "direct" }
    ],
    "final": "proxy"
  },

  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:9090",
      "default_mode": "rule"
      // 需要局域网访问时再加：
      // "external_controller": "0.0.0.0:9090",
      // "secret": "<随机长密码>"
    },
    "cache_file": {
      "enabled": true
    }
  }
}
```

检查：

```bash
python3 scripts/validate.py config.jsonc -v 1.14.4
sing-box check -c config.jsonc
```

注意：

- `selector` 的 `default` 必须是 `outbounds` 里的 tag；`urltest` 的 `outbounds` 不能为空。
- `interval` 太短会频繁测速，移动网络下更耗电；`tolerance` 用来避免节点来回抖动。
- Clash API 面板的“全局/规则/直连”模式会覆盖部分行为，排错时先看当前模式。
- 如果客户端只支持 SOCKS/HTTP，不要开 TUN；mixed 已经同时支持两者。
