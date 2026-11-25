# 远程 rule-set 分流

适用版本：**1.14.0 及以上**（`http_clients` / `default_http_client` / `http_client`）。
1.11–1.13 用 `download_detour` 指定下载出口；1.14 起该字段废弃，1.16 移除。

依赖页面：
[Rule Set](https://sing-box.sagernet.org/configuration/rule-set/) ·
[Route Rule](https://sing-box.sagernet.org/configuration/route/rule/) ·
[HTTP Client](https://sing-box.sagernet.org/configuration/shared/http-client/) ·
[Migration 1.14](https://sing-box.sagernet.org/migration/)

已知限制：远程 rule-set 首次启动要联网下载；下载失败时规则集为空，分流会落到 `final`。
生产环境建议固定版本或自建镜像，不要依赖随时会变的 URL。

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
    "rules": [
      { "rule_set": "geosite-cn", "action": "route", "server": "dns-local" }
    ],
    "final": "dns-remote"
  },

  "inbounds": [
    {
      "type": "mixed",
      "tag": "mixed-in",
      "listen": "127.0.0.1",
      "listen_port": 2080
    }
  ],

  "outbounds": [
    {
      "type": "vless",
      "tag": "proxy",
      "server": "203.0.113.10",
      "server_port": 443,
      "uuid": "00000000-0000-4000-8000-000000000000",
      "tls": {
        "enabled": true,
        "server_name": "example.com",
        "utls": { "enabled": true, "fingerprint": "chrome" }
      }
    },
    { "type": "direct", "tag": "direct" }
  ],

  // 让 rule-set 走直连下载，避免“先有代理才能下规则、先有规则才能用代理”的死循环
  "http_clients": [
    {
      "tag": "http-direct",
      "detour": "direct"
    }
  ],

  "route": {
    "auto_detect_interface": true,
    "default_http_client": "http-direct",
    "default_domain_resolver": "dns-local",
    "rule_set": [
      {
        "type": "remote",
        "tag": "geosite-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cn.srs",
        "http_client": "http-direct",
        "update_interval": "1d"
      },
      {
        "type": "remote",
        "tag": "geoip-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
        "http_client": "http-direct",
        "update_interval": "1d"
      }
    ],
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "ip_is_private": true, "action": "route", "outbound": "direct" },
      { "rule_set": "geosite-cn", "action": "route", "outbound": "direct" },
      { "rule_set": "geoip-cn", "action": "route", "outbound": "direct" }
    ],
    "final": "proxy"
  },

  "experimental": {
    "cache_file": { "enabled": true }
  }
}
```

检查：

```bash
python3 scripts/validate.py config.jsonc -v 1.14.4
sing-box check -c config.jsonc
```

注意：

- 规则顺序：私网、国内域名、国内 IP 的直连规则要放在最终代理之前。
- `format: "binary"` 对应 `.srs`；源格式 `.json` 要用 `format: "source"`。
- `update_interval` 到期后会在后台更新；失败不会删除旧缓存，但日志会有错误。
- 本地规则可以再加一条 `{"type":"local","tag":"custom","format":"source","path":"./rules/custom.json"}`，
  路径相对工作目录，不是配置文件目录。
