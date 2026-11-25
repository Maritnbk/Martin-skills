# 排错手册

> 适用于 sing-box 1.11–1.15。先确认版本，再对照错误；不同版本的字段名可能完全不同。
> 日志和配置里可能有 UUID、密码、订阅地址，贴出来前先脱敏。

## 目录

- [先做这四步](#先做这四步)
- [1. unknown field：字段不存在或版本不对](#1-unknown-field字段不存在或版本不对)
- [2. legacy DNS server format：旧 DNS 格式](#2-legacy-dns-server-format旧-dns-格式)
- [3. dns.fakeip / geoip / geosite：已移除字段](#3-dnsfakeip--geoip--geosite已移除字段)
- [4. inbound sniff / domain_strategy：旧 inbound 字段](#4-inbound-sniff--domain_strategy旧-inbound-字段)
- [5. outbound not found / rule-set not found：tag 引用错](#5-outbound-not-found--rule-set-not-foundtag-引用错)
- [6. address already in use：端口或 TUN 冲突](#6-address-already-in-use端口或-tun-冲突)
- [7. operation not permitted：TUN 权限](#7-operation-not-permittedtun-权限)
- [8. TLS handshake failed：证书、时间、SNI](#8-tls-handshake-failed证书时间sni)
- [9. Hysteria2 authentication failed：密码或混淆](#9-hysteria2-authentication-failed密码或混淆)
- [10. context deadline exceeded：DNS、网络或下载](#10-context-deadline-exceededdns网络或下载)
- [11. duplicate tag：tag 重复](#11-duplicate-tagtag-重复)
- [12. http_client not found：1.14 的 HTTP 客户端](#12-http_client-not-found114-的-http-客户端)
- [13. 能启动但没分流：规则顺序和 final](#13-能启动但没分流规则顺序和-final)

## 先做这四步

1. **确认版本**：`sing-box version`。不要拿 1.15 的文档改 1.12 的配置。
2. **静态检查**：`python3 scripts/validate.py config.jsonc -v <version>`。
   `E` 是当前版本不接受的字段/引用；`W` 是仍可用但计划移除；`U` 是没验证到的层。
3. **官方 check**：`sing-box check -c config.jsonc`。注意 `-C` 才是配置目录，`-D` 是工作目录。
4. **看启动日志**：从第一条 `FATAL` / `ERROR` 看起，不要只看最后一行。

如果 check 通过但运行失败，问题通常在权限、端口、DNS、证书或上游服务器，不在 JSON 结构。

## 1. unknown field：字段不存在或版本不对

**现象**（类似）：

```text
decode config at config.json: unknown field "geoip"
```

**原因**：字段在目标版本不存在，常见于把新文档字段写进旧版本，或用了已移除的旧字段。
**修复**：

- 用 `sing-box version` 确认版本，再查对应 tag 的文档。
- `geoip` / `geosite` 已在 1.12 移除，改用 `rule_set`。
- 不要靠“删掉报错字段”硬试；先确认替代字段。
- 跑 `validate.py`，它会按版本标出 removed / deprecated。

**文档**：[Deprecated](https://sing-box.sagernet.org/deprecated/) ·
[Rule Set](https://sing-box.sagernet.org/configuration/rule-set/)

## 2. legacy DNS server format：旧 DNS 格式

**现象**（类似）：

```text
legacy DNS server format is deprecated
```

**原因**：1.12 起 DNS server 改为 `type` + `server`；旧 `address: "1.1.1.1"` /
`address: "tls://1.1.1.1"` 格式在 1.14 已移除。
**修复**：

```jsonc
{
  "dns": {
    "servers": [
      { "type": "udp", "tag": "remote", "server": "1.1.1.1", "detour": "proxy" },
      { "type": "local", "tag": "local" }
    ]
  }
}
```

`local` 不需要 `server`；`tls` / `https` / `quic` 用各自的 `server` / `path` 字段。

**文档**：[DNS Server](https://sing-box.sagernet.org/configuration/dns/server/) ·
[Migration 1.12](https://sing-box.sagernet.org/migration/#migrate-to-new-dns-server-formats)

## 3. dns.fakeip / geoip / geosite：已移除字段

**现象**（类似）：

```text
decode config: unknown field "fakeip"
```

**原因**：

- 顶层 `dns.fakeip` 在 1.14 移除；FakeIP 现在是 `dns.servers[]` 的一种 `type`。
- `route.geoip` / `route.geosite`、规则里的 `geoip` / `geosite` 在 1.12 移除。

**修复**：

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

GeoIP / Geosite 改用远程或本地 `rule_set`，不要再下载 `.dat`。

**文档**：[FakeIP](https://sing-box.sagernet.org/configuration/dns/server/fakeip/) ·
[GeoIP migration](https://sing-box.sagernet.org/migration/#migrate-geoip-to-rule-sets)

## 4. inbound sniff / domain_strategy：旧 inbound 字段

**现象**（类似）：

```text
unknown field "sniff" in inbound
```

**原因**：1.11 起 inbound 的 `sniff` / `sniff_timeout` / `sniff_override_destination` /
`domain_strategy` 迁移到 route action，1.13 移除。
**修复**：

```jsonc
{
  "inbounds": [{ "type": "mixed", "tag": "in" }],
  "route": {
    "rules": [
      { "inbound": "in", "action": "sniff" },
      { "inbound": "in", "action": "resolve", "strategy": "prefer_ipv4" }
    ]
  }
}
```

**文档**：[Rule Action](https://sing-box.sagernet.org/configuration/route/rule_action/) ·
[Migration 1.11](https://sing-box.sagernet.org/migration/#migrate-legacy-inbound-fields-to-rule-actions)

## 5. outbound not found / rule-set not found：tag 引用错

**现象**（类似）：

```text
route: outbound not found: proxy
route: rule-set not found: geosite-cn
```

**原因**：`route.final`、规则里的 `outbound`、`rule_set`、`detour` 引用了不存在的 tag；
或者 tag 写在 `endpoints` 里却按 `outbounds` 找。
**修复**：

- 逐个核对 `inbounds[].tag`、`outbounds[].tag`、`endpoints[].tag`、`route.rule_set[].tag`。
- WireGuard 作为 endpoint 时，`outbound` 仍可直接写它的 tag。
- `validate.py` 会检查 `route.final`、规则 `outbound`、`rule_set`、`dns.final`、`dns.server` 和常见 `detour`。

**文档**：[Route](https://sing-box.sagernet.org/configuration/route/) ·
[Rule Set](https://sing-box.sagernet.org/configuration/rule-set/)

## 6. address already in use：端口或 TUN 冲突

**现象**（类似）：

```text
start inbound: listen tcp 127.0.0.1:2080: bind: address already in use
```

**原因**：mixed/HTTP/SOCKS 端口被占用，或已经有另一个 TUN 实例。
**修复**：

```bash
ss -lntp | grep 2080
```

换端口，或停掉旧进程。TUN 场景确认没有同时开两个 sing-box / 其他代理的 TUN。

**文档**：[Mixed inbound](https://sing-box.sagernet.org/configuration/inbound/mixed/) ·
[Listen fields](https://sing-box.sagernet.org/configuration/shared/listen/)

## 7. operation not permitted：TUN 权限

**现象**（类似）：

```text
start inbound tun-in: operation not permitted
```

**原因**：创建 TUN、改路由或设置防火墙需要 root 或相应 capability；容器里还可能需要 `NET_ADMIN`。
**修复**：

- Linux：用 root 或 `sudo` 启动，或给二进制 `CAP_NET_ADMIN`。
- 容器：加 `--cap-add NET_ADMIN --device /dev/net/tun`。
- 先确认 `/dev/net/tun` 存在。
- 不要用 `auto_route` 和系统代理同时抢路由。

**文档**：[TUN](https://sing-box.sagernet.org/configuration/inbound/tun/)

## 8. TLS handshake failed：证书、时间、SNI

**现象**（类似）：

```text
TLS handshake failed: tls: failed to verify certificate: x509: certificate signed by unknown authority
```

**原因**：系统时间不对、SNI 与证书不匹配、自签证书未信任，或 REALITY 参数不对。
**修复**：

- 先校准时间（证书校验依赖时钟）。
- 检查 `tls.server_name` 是否是证书覆盖的域名。
- 自签场景才考虑 `insecure: true`；公网配置不要长期开。
- REALITY 检查 `server_name`、`public_key`、`short_id` 与服务端一致。
- 看日志里是“验证失败”还是“握手超时”，两者方向不同。

**文档**：[TLS](https://sing-box.sagernet.org/configuration/shared/tls/) ·
[VLESS](https://sing-box.sagernet.org/configuration/outbound/vless/)

## 9. Hysteria2 authentication failed：密码或混淆

**现象**（类似）：

```text
hysteria2: authentication failed
```

**原因**：`password` 错、服务端开了 `obfs` 而客户端没配、端口/`server_ports` 不对。
**修复**：

- 核对 `password`（注意 URL 里的特殊字符）。
- 服务端有 `obfs: salamander` 时，客户端也要有同类型、同密码的 `obfs`。
- 确认 `server_port` 或 `server_ports` 与服务端一致。
- Hysteria2 必须配 `tls`，且 `server_name` 要对。

**文档**：[Hysteria2](https://sing-box.sagernet.org/configuration/outbound/hysteria2/)

## 10. context deadline exceeded：DNS、网络或下载

**现象**（类似）：

```text
context deadline exceeded
```

**原因**：DNS 解析失败、上游不可达、远程 rule-set 下载超时，或 `detour` 指向的代理本身不通。
**修复**：

- 先确认直连能解析：`dig example.com` / `nslookup`。
- 检查 DNS server 的 `detour` 是否指向一个可用的 outbound。
- 远程 `rule_set` 配了 `http_client` 时，确认该 client 的 `detour` 可用。
- 临时把 `route.final` 改成 `direct`，判断是代理问题还是规则问题。

**文档**：[DNS](https://sing-box.sagernet.org/configuration/dns/) ·
[Dial fields](https://sing-box.sagernet.org/configuration/shared/dial/)

## 11. duplicate tag：tag 重复

**现象**（类似）：

```text
duplicate tag: proxy
```

**原因**：同一类对象里两个 tag 相同；或把 inbound/outbound 的 tag 混用。
**修复**：每个 `inbounds` / `outbounds` / `endpoints` / `services` / `dns.servers` /
`route.rule_set` 内部 tag 唯一。`validate.py` 会报重复位置。

**文档**：[Configuration](https://sing-box.sagernet.org/configuration/)

## 12. http_client not found：1.14 的 HTTP 客户端

**现象**（类似）：

```text
route: http_client not found: http
```

**原因**：`route.default_http_client` 或 `rule_set[].http_client` 指向了不存在的
`http_clients[].tag`；或者仍在依赖 1.14 已废弃的隐式默认客户端。
**修复**：

```jsonc
{
  "http_clients": [{ "tag": "http" }],
  "route": { "default_http_client": "http" }
}
```

**文档**：[HTTP Client](https://sing-box.sagernet.org/configuration/shared/http-client/) ·
[Rule Set](https://sing-box.sagernet.org/configuration/rule-set/)

## 13. 能启动但没分流：规则顺序和 final

**现象**：能上网，但国内/国外流量走错，或 DNS 泄漏。

**原因**：route 规则从上到下匹配，第一条命中就结束；`final` 只兜底。
**修复**：

- 把 `action: "sniff"` 和 `protocol: "dns"` + `action: "hijack-dns"` 放前面。
- 私网直连、国内 rule-set 直连放在代理规则之前。
- `final` 明确写 `proxy` 或 `direct`，不要留空。
- DNS 的 `final` 和 `servers[].detour` 一起检查，避免 DNS 查询绕进代理环。

**文档**：[Route Rule](https://sing-box.sagernet.org/configuration/route/rule/) ·
[DNS](https://sing-box.sagernet.org/configuration/dns/)
