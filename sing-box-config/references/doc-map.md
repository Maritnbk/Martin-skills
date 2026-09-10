# sing-box 官方文档 URL 地图

站点：<https://sing-box.sagernet.org> （Docusaurus 静态站）

**三条硬约束：**

1. **所有配置页 URL 必须带结尾斜杠**：`/configuration/log/` 可以，`/configuration/log` 可能取不到。根配置页就是 `/configuration/` 本身。
2. **没有 llms.txt / llms-full.txt**（`/llms.txt` 和 `/llms-full.txt` 均返回 404）。不存在整站合并版本，只能逐页抓。
3. **URL 里没有版本号**，站点只跟随最新发布线，没有 `dev` / `legacy` / `1.12` 这类分支路径。版本信息在页面正文里（见下方"版本标记"）。

不确定某个协议或字段属于哪一页时，先抓 `/configuration/` 读它的导航树，再定点抓取。

---

## 版本标记（比字段本身更重要）

页面正文里以内联标记说明版本，字段级别标注：

| 标记 | 含义 |
|---|---|
| `Since sing-box X.Y.Z` | 该字段/选项从这个版本开始存在 |
| `Deprecated in sing-box X.Y.Z` | 已废弃，仍可用但会被移除 |
| `Removed in sing-box X.Y.Z` | 已移除，写了会报错或失效 |
| `Changes in sing-box X.Y.Z` | 行为变更（字段还在，语义变了） |

集中查废弃/移除：先看 `/deprecated/`（按版本分组的废弃清单），再看 `/migration/`（旧写法 → 新写法的对照，含 JSON 示例），`/changelog/` 看发布说明。

已知的废弃批次集中在 **1.11.0 / 1.12.0 / 1.14.0**。文档当前对应到 `1.14.0-rc.1`，略超前于最后一个稳定版。

---

## 非配置参考页

| 用途 | URL |
|---|---|
| 变更日志（倒序 `#### x.y.z` 标题 + 变更条目） | `/changelog/` |
| 迁移指南（按引入版本分组：1.14.0 / 1.12.0 / 1.11.0 / 1.10.0 / 1.9.5 / 1.9.0 / 1.8.0） | `/migration/` |
| 废弃清单（按版本分组：1.14.0 / 1.12.0 / 1.11.0 / 1.10.0 / 1.8.0 / 1.6.0） | `/deprecated/` |

---

## 顶层配置对象

| 对象 | URL |
|---|---|
| 根配置（Structure / Fields / **Check** / **Format** / Merge） | `/configuration/` |
| log | `/configuration/log/` |
| dns | `/configuration/dns/` |
| ntp | `/configuration/ntp/` |
| certificate | `/configuration/certificate/` |
| endpoints | `/configuration/endpoint/` |
| inbounds | `/configuration/inbound/` |
| outbounds | `/configuration/outbound/` |
| route | `/configuration/route/` |
| experimental | `/configuration/experimental/` |
| services | `/configuration/service/` |
| JSON Schema | `/configuration/schema/` |
| network namespace | `/configuration/network-namespace/` |

`sing-box check` / `format` 的用法在 `/configuration/` 页面的 Check / Format 小节。

---

## DNS

| 内容 | URL |
|---|---|
| dns 总览 | `/configuration/dns/` |
| server 索引 | `/configuration/dns/server/` |
| dns 规则 | `/configuration/dns/rule/` ⚠️大 |
| dns 规则动作 | `/configuration/dns/rule_action/` |
| **legacy** fakeip 配置（Removed in 1.14.0） | `/configuration/dns/fakeip/` |

DNS server 每种类型一页，路径 `/configuration/dns/server/<type>/`：

`legacy`（旧格式）、`local`、`hosts`、`tcp`、`udp`、`tls`、`quic`、`https`、`http3`、`dhcp`、`mdns`、`fakeip`、`tailscale`、`openconnect`、`openvpn`、`resolved`

⚠️ **两个 fakeip 页面不要混**：
- `/configuration/dns/server/fakeip/` — 当前的 server 类型（Since 1.12.0）
- `/configuration/dns/fakeip/` — 旧的顶层 fakeip 配置（Removed in 1.14.0）

⚠️ 旧格式 DNS server 写法在 1.14.0 被移除，写 DNS 配置前务必读 `/configuration/dns/server/` 和 `/migration/`。

---

## Route

| 内容 | URL |
|---|---|
| route 总览 | `/configuration/route/` |
| 路由规则 | `/configuration/route/rule/` ⚠️大 |
| 规则动作 | `/configuration/route/rule_action/` ⚠️大 |
| 协议嗅探 | `/configuration/route/sniff/` |
| geoip（1.12.0 已移除相关字段，查文档确认） | `/configuration/route/geoip/` |
| geosite（同上） | `/configuration/route/geosite/` |

---

## Rule Set

| 内容 | URL |
|---|---|
| rule-set 总览（local / remote 类型都在这页） | `/configuration/rule-set/` |
| 源格式 | `/configuration/rule-set/source-format/` |
| headless rule | `/configuration/rule-set/headless-rule/` ⚠️大 |
| AdGuard DNS filter | `/configuration/rule-set/adguard/` |

---

## Inbound（`/configuration/inbound/<proto>/`）

`direct`、`mixed`、`socks`、`http`、`shadowsocks`、`vmess`、`vless`、`trojan`、`naive`、`hysteria`、`hysteria2`、`shadowtls`、`tuic`、`anytls`、`snell`、`tun`、`redirect`、`tproxy`、`cloudflared`

**每个 inbound 都要同时读 `/configuration/shared/listen/`**（监听相关的公共字段在那里，不在协议页上）。

⚠️ 部分旧 inbound 字段在 1.11.0 被废弃，写之前查 `/deprecated/`。

---

## Outbound（`/configuration/outbound/<proto>/`）

`direct`、`block`、`selector`、`urltest`、`socks`、`http`、`shadowsocks`、`vmess`、`vless`、`trojan`、`naive`、`hysteria`、`hysteria2`、`tuic`、`wireguard`、`anytls`、`shadowtls`、`snell`、`ssh`、`tor`、`dns`、`bridge`

**每个出站类型都要同时读 `/configuration/shared/dial/`**（拨号相关的公共字段在那里）。

⚠️ 特殊 outbound（如 `block`、`dns`）在 1.11.0 有废弃变更，被 rule action 取代，务必查 `/deprecated/` 和 `/migration/`。

---

## Endpoint（`/configuration/endpoint/<type>/`）

`wireguard` ⚠️大、`tailscale`、`openconnect`、`openvpn-client`、`openvpn-server`

---

## 公共字段（`/configuration/shared/<page>/`）

| 页 | 何时必读 |
|---|---|
| `listen/` ⚠️大 | 写任何 inbound |
| `dial/` ⚠️大 | 写任何 outbound |
| `tls/` ⚠️大 | 任何涉及 TLS / Reality / ECH / uTLS 的配置 |
| `multiplex/` | 涉及多路复用 |
| `v2ray-transport/` | ws / grpc / httpupgrade 等传输层 |
| `udp-over-tcp/` | UoT |
| `http-client/`、`http2/`、`quic/` | 相关协议细节 |
| `certificate-provider/`（下含 `acme/`、`tailscale/`、`cloudflare-origin-ca/`） | 自动签发证书 |
| `dns01_challenge/` | ACME DNS-01 |
| `pre-match/`、`udp-nat/`、`tcp-brutal/`、`wifi-state/`、`neighbor/` | 按需 |

---

## Experimental（`/configuration/experimental/<page>/`）

`cache-file/`、`clash-api/`、`v2ray-api/`

---

## Service（`/configuration/service/<name>/`）

`api`、`derp`、`resolved`、`ssm-api`、`ccm`、`ocm`、`hysteria-realm`、`usbip-server`、`usbip-client`

---

## 抓取提示

**⚠️大页面**（整页拉进上下文会爆）：`route/rule/`、`route/rule_action/`、`dns/rule/`、`rule-set/headless-rule/`、`shared/listen/`、`shared/dial/`、`shared/tls/`、`endpoint/wireguard/`、`outbound/wireguard/`。用 webfetch 的 prompt 参数只提取需要的字段，或按锚点定位。

**小页面**（可整页抓）：`log/`、`inbound/mixed/`、`outbound/selector/`、`outbound/block/`、`dns/server/fakeip/`、`experimental/cache-file/`。

**锚点约定**（用于深链某个字段）：

- 多词小节标题 → 连字符：`#listen-fields`、`#udp-over-tcp`
- 字段名 → 原样，含下划线：`#tcp_keep_alive`、`#domain_strategy`、`#server_port`
- **同名标题会加数字后缀**：`#timeout` / `#timeout_1`、`#key` / `#key_1`、`#path` / `#path_1` / `#path_2`。深链前先看页面目录确认实际锚点。

**页数多时并行抓**：把不同页面分给多个子 agent，让每个只回传"字段名 + 类型 + 默认值 + 版本标记 + 限制条件"的压缩结果，不要回传原文。
