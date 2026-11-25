# TUN 透明代理（Linux）

适用版本：**1.14.0 及以上**（用到 `$schema`、`http_clients`）。
1.11–1.13 可用同一结构，但删除 `$schema` 和 `http_clients`，把 rule-set 的
`http_client` 换成 `download_detour`（1.14 已废弃，1.16 移除）。

依赖页面：
[TUN](https://sing-box.sagernet.org/configuration/inbound/tun/) ·
[Route](https://sing-box.sagernet.org/configuration/route/) ·
[Rule Set](https://sing-box.sagernet.org/configuration/rule-set/) ·
[DNS](https://sing-box.sagernet.org/configuration/dns/) ·
[VLESS](https://sing-box.sagernet.org/configuration/outbound/vless/)

已知限制：需要 root 或 `CAP_NET_ADMIN`；容器还需 `/dev/net/tun`；`auto_route` 会接管默认路由，
不要在已经运行其他 TUN 的机器上直接套用。

```jsonc
{
  // 仅 1.14+ 需要；旧版本删掉这一行
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
      // 国内域名走本地 DNS，减少 fake-ip / 远端解析带来的分流误差
      { "rule_set": "geosite-cn", "action": "route", "server": "dns-local" }
    ],
    "final": "dns-remote"
  },

  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "address": ["172.19.0.1/30", "fdfe:dcba:9876::1/126"],
      "mtu": 9000,
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
    // rule-set 下载和出站域名解析走本地 DNS，避免先绕进代理造成自环
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
      // 先嗅探协议，再劫持发往 TUN 的 DNS
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

- `route.rules` 从上到下匹配，`sniff` / `hijack-dns` 必须放在分流规则之前。
- `auto_route` 依赖 `route.auto_detect_interface`，否则可能把代理自己的出站也圈进 TUN。
- 如果系统没有 gVisor 构建，`stack` 用 `system`；不要写 `mixed` 后假设一定有 gVisor。
- `address` 的网段不要和局域网冲突；IPv6 不启用可只留 IPv4 地址。
