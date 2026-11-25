# 版本迁移速查

> 最后核对：2026-11-23，对应官方 `migration.md` / `deprecated.md` 的 v1.14.4 快照。
> 先跑 `sing-box version` 确定目标版本；本文的「已移除」表示该版本不再接受，
> 「已废弃」表示仍能运行但计划在未来版本移除。最终以 `sing-box check` 和对应 tag 文档为准。

## 目录

- [先看总表](#先看总表)
- [1.8：GeoIP / Geosite → rule-set](#18geoip--geosite--rule-set)
- [1.8：Clash API 缓存 → cache_file](#18clash-api-缓存--cache_file)
- [1.10：TUN 地址字段合并](#110tun-地址字段合并)
- [1.11：特殊 outbound → rule action](#111特殊-outbound--rule-action)
- [1.11：inbound 嗅探 / 域名策略 → route action](#111inbound-嗅探--域名策略--route-action)
- [1.11：direct 覆写 → route-options](#111direct-覆写--route-options)
- [1.11：WireGuard outbound → endpoint](#111wireguard-outbound--endpoint)
- [1.12：旧 DNS server 格式](#112旧-dns-server-格式)
- [1.12：DNS 规则 outbound → domain_resolver](#112dns-规则-outbound--domain_resolver)
- [1.14：远程 rule-set 的 HTTP 客户端](#114远程-rule-set-的-http-客户端)
- [1.14：DNS 缓存与响应匹配](#114dns-缓存与响应匹配)
- [1.14：FakeIP 与内联 ACME](#114fakeip-与内联-acme)
- [迁移后的检查顺序](#迁移后的检查顺序)

## 先看总表

| 版本 | 旧写法 | 新写法 | 状态 |
| --- | --- | --- | --- |
| 1.8 | `route.geoip` / `route.geosite` / 规则内 `geoip` / `geosite` | `route.rule_set` + `rule_set` 匹配 | 1.12.0 已移除 |
| 1.8 | `experimental.clash_api.cache_file` / `store_*` / `cache_id` | `experimental.cache_file` | 已废弃 |
| 1.10 | `inet4_address` / `inet6_address` / `inet4_route_address` / `inet6_route_address` | `address` / `route_address` / `route_exclude_address` | 1.12.0 已移除 |
| 1.10 | `rule_set_ipcidr_match_source` | `rule_set_ip_cidr_match_source` | 1.11.0 已移除 |
| 1.11 | `outbounds[].type: "block"` / `"dns"` | `action: "reject"` / `action: "hijack-dns"` | 1.13.0 已移除 |
| 1.11 | inbound `sniff*` / `domain_strategy` | `action: "sniff"` / `action: "resolve"` | 1.13.0 已移除 |
| 1.11 | direct 的 `override_address` / `override_port` | `action: "route-options"` | 1.13.0 已移除 |
| 1.11 | `outbounds[].type: "wireguard"` | `endpoints[]` 中 `type: "wireguard"` | 1.13.0 已移除 |
| 1.11 | TUN `gso` | 删除；透明代理没有收益 | 1.13.0 已移除 |
| 1.12 | `dns.servers[].address` 旧格式 | `type` + `server` / `path` | 1.14.0 已移除 |
| 1.12 | DNS 规则 `outbound` | dial `domain_resolver` / `route.default_domain_resolver` | 已废弃；1.14 schema 不再接受 |
| 1.12 | TLS `pq_signature_schemes_enabled` / `dynamic_record_sizing_disabled` | 删除 | 1.13.0 已移除 |
| 1.14 | rule-set `download_detour` | `http_client` | 1.16.0 将移除 |
| 1.14 | 隐式默认 HTTP 客户端 | `http_clients` + `route.default_http_client` | 1.16.0 将移除 |
| 1.14 | `dns.independent_cache` | 删除字段 | 1.16.0 将移除 |
| 1.14 | `experimental.cache_file.store_rdrc` | `store_dns` | 1.16.0 将移除 |
| 1.14 | DNS 规则 `strategy` | `dns.servers[].strategy` | 1.16.0 将移除 |
| 1.14 | DNS 规则 `ip_cidr` / `ip_is_private`（无 `match_response`） | `evaluate` + `match_response` | 1.16.0 将移除 |
| 1.14 | TLS 内联 `acme` | `certificate_providers` 的 ACME | 1.16.0 将移除 |
| 1.14 | 顶层 `dns.fakeip` | `dns.servers[]` 中 `type: "fakeip"` | 1.14.0 已移除 |

## 1.8：GeoIP / Geosite → rule-set

旧字段在 1.12.0 已移除；新配置不要再下载 `.dat`。远程 rule-set 需要缓存文件。

```jsonc
{
  "http_clients": [{ "tag": "http" }],
  "route": {
    "default_http_client": "http",
    "rule_set": [
      {
        "type": "remote",
        "tag": "geoip-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
        "http_client": "http"
      }
    ],
    "rules": [
      { "ip_is_private": true, "action": "route", "outbound": "direct" },
      { "rule_set": "geoip-cn", "action": "route", "outbound": "direct" }
    ]
  },
  "experimental": { "cache_file": { "enabled": true } }
}
```

Geosite 同理，把 URL 换成 `sing-geosite/rule-set/geosite-cn.srs`，规则键仍是 `rule_set`。

## 1.8：Clash API 缓存 → cache_file

```jsonc
{
  "experimental": {
    "clash_api": { "external_controller": "127.0.0.1:9090" },
    "cache_file": { "enabled": true, "path": "cache.db", "store_fakeip": true }
  }
}
```

旧 `store_mode` / `store_selected` / `store_fakeip` / `cache_file` / `cache_id` 在 `clash_api` 下已废弃。

## 1.10：TUN 地址字段合并

```jsonc
{
  "type": "tun",
  "address": ["172.19.0.1/30", "fdfe:dcba:9876::1/126"],
  "route_address": ["0.0.0.0/1", "128.0.0.0/1", "::/1", "8000::/1"],
  "route_exclude_address": ["192.168.0.0/16", "fc00::/7"]
}
```

`inet4_address` / `inet6_address` / `inet4_route_address` / `inet6_route_address` /
`inet4_route_exclude_address` / `inet6_route_exclude_address` 已在 1.12.0 移除。

## 1.11：特殊 outbound → rule action

```jsonc
{
  "route": {
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "action": "reject" }
    ]
  }
}
```

`block` 对应 `reject`，`dns` 对应 `hijack-dns`。不要再用 `outbounds[].type: "block"` / `"dns"`。

## 1.11：inbound 嗅探 / 域名策略 → route action

```jsonc
{
  "inbounds": [{ "type": "mixed", "tag": "in" }],
  "route": {
    "rules": [
      { "inbound": "in", "action": "resolve", "strategy": "prefer_ipv4" },
      { "inbound": "in", "action": "sniff", "timeout": "1s" }
    ]
  }
}
```

inbound 上的 `sniff` / `sniff_timeout` / `sniff_override_destination` / `domain_strategy`
在 1.13.0 已移除。

## 1.11：direct 覆写 → route-options

```jsonc
{
  "route": {
    "rules": [
      { "action": "route-options", "override_address": "1.1.1.1", "override_port": 443 }
    ]
  }
}
```

## 1.11：WireGuard outbound → endpoint

```jsonc
{
  "endpoints": [
    {
      "type": "wireguard",
      "tag": "wg-ep",
      "address": ["10.0.0.2/32"],
      "private_key": "<private_key>",
      "peers": [
        {
          "address": "127.0.0.1",
          "port": 51820,
          "public_key": "<peer_public_key>",
          "allowed_ips": ["0.0.0.0/0"],
          "persistent_keepalive_interval": 30
        }
      ]
    }
  ]
}
```

WireGuard 作为 endpoint 时，`route.final` / `outbound` 可以直接引用它的 tag。

## 1.12：旧 DNS server 格式

```jsonc
{
  "dns": {
    "servers": [
      { "type": "local", "tag": "local" },
      { "type": "udp", "tag": "remote", "server": "1.1.1.1", "detour": "proxy" },
      { "type": "tls", "tag": "tls", "server": "1.1.1.1", "detour": "proxy" }
    ]
  }
}
```

旧格式 `{ "address": "1.1.1.1" }`、`{ "address": "tls://1.1.1.1" }` 在 1.14.0 已移除。
`local` 新旧都只需要 type；`detour` 仍可用。

## 1.12：DNS 规则 outbound → domain_resolver

旧 DNS 规则用一个 `outbound` 决定解析走哪个出口；新做法是在需要解析的 outbound/dial 字段上
声明 `domain_resolver`，或设置全局 `route.default_domain_resolver`。

```jsonc
{
  "dns": {
    "servers": [{ "type": "local", "tag": "local" }]
  },
  "outbounds": [
    {
      "type": "socks",
      "tag": "proxy",
      "server": "example.org",
      "server_port": 2080,
      "domain_resolver": "local"
    }
  ],
  "route": {
    "default_domain_resolver": "local"
  }
}
```

## 1.14：远程 rule-set 的 HTTP 客户端

旧写法只配 `download_detour`；1.14 起应显式声明 HTTP 客户端，否则依赖默认 outbound 的行为会在 1.16 移除。

```jsonc
{
  "http_clients": [{ "tag": "http" }],
  "route": {
    "default_http_client": "http",
    "rule_set": [
      {
        "type": "remote",
        "tag": "geosite-cn",
        "format": "binary",
        "url": "https://example.com/geosite-cn.srs",
        "http_client": "http",
        "update_interval": "1d"
      }
    ]
  }
}
```

## 1.14：DNS 缓存与响应匹配

- `dns.independent_cache`：删除。
- `experimental.cache_file.store_rdrc` → `store_dns`。
- DNS 规则 `strategy` → 放到 `dns.servers[].strategy`（1.16 前仍可用旧字段，但会警告）。
- 旧 `ip_cidr` / `ip_is_private` 若想匹配 DNS 响应，需要先 `evaluate`，再用 `match_response: true`：

```jsonc
{
  "dns": {
    "servers": [
      { "type": "udp", "tag": "remote", "server": "1.1.1.1" },
      { "type": "local", "tag": "local" }
    ],
    "rules": [
      { "action": "evaluate", "server": "remote" },
      { "match_response": true, "rule_set": "geoip-cn", "action": "route", "server": "local" },
      { "action": "route", "server": "remote" }
    ],
    "final": "remote"
  }
}
```

## 1.14：FakeIP 与内联 ACME

FakeIP 不再是顶层 `dns.fakeip`，而是普通 DNS server：

```jsonc
{
  "dns": {
    "servers": [
      {
        "type": "fakeip",
        "tag": "fakeip",
        "inet4_range": "198.18.0.0/15",
        "inet6_range": "2001:2::/48"
      }
    ],
    "rules": [{ "query_type": ["A", "AAAA"], "server": "fakeip" }]
  }
}
```

TLS 内联 `acme` 在 1.14 废弃，改用 `certificate_providers` 的 ACME provider；
涉及域名、email、provider 等多个字段，建议直接对照官方
[Migration: inline ACME](https://sing-box.sagernet.org/migration/#migrate-inline-acme-to-certificate-provider)。

## 迁移后的检查顺序

1. `sing-box version` 确认目标版本。
2. `python3 scripts/validate.py config.jsonc -v <version>`：先看 E，再看 W。
3. 如果本机有对应版本：`sing-box check -c config.jsonc`。
4. 启动后看日志里的 `FATAL` / `ERROR`；schema 通过不等于运行期一定通过。

官方依据：
[migration](https://sing-box.sagernet.org/migration/) ·
[deprecated](https://sing-box.sagernet.org/deprecated/) ·
[rule-set](https://sing-box.sagernet.org/configuration/rule-set/)
