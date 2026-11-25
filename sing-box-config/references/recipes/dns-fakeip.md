# FakeIP DNS + TUN

适用版本：**1.14.0 及以上**（`$schema`、`http_clients`、FakeIP server 的当前写法）。
1.12–1.13 可以用 `type: "fakeip"` 的 server，但顶层 `dns.fakeip` 已在 1.14 移除，
不要把旧教程里的 `dns.fakeip` 抄进来。

依赖页面：
[FakeIP server](https://sing-box.sagernet.org/configuration/dns/server/fakeip/) ·
[DNS](https://sing-box.sagernet.org/configuration/dns/) ·
[DNS Rule](https://sing-box.sagernet.org/configuration/dns/rule/) ·
[TUN](https://sing-box.sagernet.org/configuration/inbound/tun/) ·
[Rule Set](https://sing-box.sagernet.org/configuration/rule-set/)

已知限制：FakeIP 只对 A/AAAA 生效；需要 TUN/redirect 把 DNS 查询送进 sing-box。
`198.18.0.0/15` 是保留网段，不要和真实内网重叠。

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
      },
      {
        "type": "fakeip",
        "tag": "dns-fakeip",
        "inet4_range": "198.18.0.0/15",
        "inet6_range": "2001:2::/48"
      }
    ],
    "rules": [
      // 国内域名先走本地 DNS，避免也被分配 fake-ip
      { "rule_set": "geosite-cn", "action": "route", "server": "dns-local" },
      // 其余 A/AAAA 交给 FakeIP
      { "query_type": ["A", "AAAA"], "action": "route", "server": "dns-fakeip" },
      { "action": "route", "server": "dns-remote" }
    ],
    "final": "dns-remote"
  },

  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "address": ["172.19.0.1/30", "fdfe:dcba:9876::1/126"],
      "auto_route": true,
      "strict_route": true,
      "stack": "system"
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

  "http_clients": [{ "tag": "http" }],

  "route": {
    "auto_detect_interface": true,
    "default_http_client": "http",
    // rule-set 下载和出站域名解析不要绕进 fake-ip，否则会自环
    "default_domain_resolver": "dns-local",
    "rule_set": [
      {
        "type": "remote",
        "tag": "geosite-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cn.srs",
        "http_client": "http",
        "update_interval": "1d"
      },
      {
        "type": "remote",
        "tag": "geoip-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
        "http_client": "http",
        "update_interval": "1d"
      }
    ],
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "ip_is_private": true, "action": "route", "outbound": "direct" },
      // 国内 IP 直连；其余（含 fake-ip 映射的境外域名）走代理
      { "rule_set": "geoip-cn", "action": "route", "outbound": "direct" }
    ],
    "final": "proxy"
  },

  "experimental": {
    "cache_file": {
      "enabled": true,
      // 让 fake-ip 映射在重启后仍然有效
      "store_fakeip": true
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

- DNS 规则顺序很关键：`geosite-cn -> local` 必须在 `A/AAAA -> fakeip` 之前。
- `default_domain_resolver` 指向本地 DNS，避免下载 rule-set 时先被 fake-ip 接管。
- 只对需要代理的域名使用 FakeIP；全部域名都 fake 会让国内直连也失去真实 IP。
- 清理 `cache.db` 可以重置 fake-ip 映射；不要把它提交到版本库。
