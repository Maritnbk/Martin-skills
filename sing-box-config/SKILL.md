---
name: sing-box-config
description: 严格基于 sing-box 官方文档（sing-box.sagernet.org）编写、审查、修复和解释 sing-box 配置文件，先确认版本、再读对应版本文档，绝不凭记忆编造字段。只要用户提到 sing-box、singbox、sing_box 配置，或提到 config.json/JSONC 里的 inbounds/outbounds/route/rules/rule_set/dns/experimental/clash-api/tun/mixed/vless/vmess/trojan/hysteria2/tuic/shadowsocks/anytls/shadowtls/wireguard/urltest/selector/sniff/fakeip/geosite/geoip 等 sing-box 字段，或让你"写个代理配置/机场配置/透明代理/分流规则/订阅转换成 sing-box"，或问某个字段是否存在、默认值是多少、是不是被废弃了、1.11/1.12/1.13/1.14/1.15 升级要改什么、`sing-box check` 报错怎么解决——都必须使用本 skill，即使用户没有明说"官方文档"或"不要幻觉"。用户上传/指定了本地 sing-box 文档时同样适用。也适用于 sing-box config、proxy configuration、transparent proxy、rule-set、subscription conversion 等英文说法。不适用于纯 Clash/mihomo 或 Xray 配置、Clash Verge 等客户端 GUI 的安装/订阅导入、通用 JSON 格式化、与 sing-box 无关的网速/断网排障；这些场景不要套用本 skill。
---

# sing-box 配置助手

职责：基于 sing-box **官方文档**解释字段、生成配置、审查修复、排查 `check` 错误。

sing-box 的字段在版本之间变化很快（1.11 / 1.12 / 1.14 都有成批废弃和移除）。网上模板、issue、博客大多已经过期，模型记忆也大概率来自这些内容。**本 skill 的核心不是写得快，而是每个字段都能指回官方文档的某一页，并且对得上用户的实际版本。** 跑不起来或静默失效的配置，对用户是负资产。

## 任务分流

| 任务 | 先读 | 交付 |
|---|---|---|
| 写新配置 | 本文 + `references/doc-map.md` + 对应 `references/recipes/` | 完整配置 + 文档依据 + 验证结果 |
| 审查 / 修复现有配置 | `doc-map.md` + `migration-cheatsheet.md` | 必须改 / 建议改 / 未提及 + 最小修改 |
| 解释单个字段或默认值 | 该字段所在页 | 3–5 行轻量回答，不套四段式 |
| `sing-box check` 报错 | `references/troubleshooting.md` | 定位 + 最小修复，不整份重写 |
| 版本升级 | `/changelog/`、`/migration/`、`/deprecated/` + 速查表 | 逐项影响清单 + 迁移后配置 |
| 订阅 / Clash / v2ray 转换 | 目标字段文档 | 语义映射后的配置 + 未确认项 |
| 文档不可达 | 降级流程 | 停下来要本地文档，不猜 |

## 硬规则

1. **先定版本，再查文档。** 不默认"最新版"；版本不确定就明确写出假设。
2. **只认官方来源。** 优先级：用户本地文档 > 对应 tag 的 `docs/` 与 `docs/schema.json` > 官方线上站 > 可执行程序行为 > 官方 schema。
3. **线上站只代表最新线。** 截至 2026-11-23 已含 `Since 1.15.0` 的 Tailcat / MASQUE；不能拿它当 1.14 或更旧版本的依据。
4. **不算依据：** 模型记忆、社区模板、订阅转换输出、GitHub issue、博客、Clash/v2ray 的同名字段。Clash 有某个键，不代表 sing-box 有。
5. **文档没确认就不写。** 字段、取值、默认值、组合方式，文档没提就写"文档未提及，不能确认"；不要为了"看起来完整"补字段。
6. **抓不到文档就停。** 不凭记忆生成或解释；宁可交付不了，也不交付一份用户以为可信、实际不可信的配置。
7. **凭据只占位。** UUID、密码、订阅链接用占位符；不回显用户真实凭据。默认输出到新文件或代码块；改用户文件前先确认并备份。
8. **不越级声称验证。** 只有用户回报实际运行成功，才能说"已验证可用"；文档确认、schema、`check` 各算一级，见下文。

## 第一步：确定版本

1. 用户已说明版本：直接用（`1.14.4` → tag `v1.14.4`）。
2. 用户没说、本机可运行：让用户执行 `sing-box version`。
3. 两者都做不到：声明"本配置面向 X.Y.Z"，并说明这是假设。

| 用户版本 | 文档来源 |
|---|---|
| 1.11.0 及以上稳定版 | 官方仓库对应 tag 的 `docs/` |
| 预发布 / alpha | 官方仓库 `testing` 分支 |
| 1.10.0 及以下 | 对应 tag，best-effort，先建议升级 |
| 只想看最新线 / tag 缺页 | 线上站点（注明它可能超前） |

按 tag 抓文档用 raw markdown：`https://raw.githubusercontent.com/SagerNet/sing-box/v<version>/docs/...`。本环境 raw 可能不通，可用 jsDelivr：
`https://cdn.jsdelivr.net/gh/SagerNet/sing-box@v<version>/docs/...`。
中文页是同目录 `<page>.zh.md`；字段名、默认值、版本标记以英文页为准。

## 依据：只认官方来源

1. 用户上传或指定的本地文档（最高，对应实际版本）。
2. 官方仓库对应 tag 的文档源码（v1.11.0+ 可用）。
3. 官方线上站：配置 <https://sing-box.sagernet.org/configuration/>、变更日志 `/changelog/`、迁移 `/migration/`、废弃清单 `/deprecated/`。
4. `sing-box version` / `check` 的实际行为，只用于验证，不用来推断字段。
5. 官方 JSON Schema：线上 `https://sing-box.sagernet.org/schema.json`；tag 级 `docs/schema.json` 仅 v1.14.0+。

线上 URL 带结尾斜杠（`/configuration/inbound/mixed/`）；站点没有 `llms.txt`，必须逐页抓。引用给用户时用站点 URL，并注明依据版本。

## 工作流

### 写新配置

1. 按上一节定版本。
2. 读 `references/doc-map.md` 定位页面；能套 `references/recipes/` 就先读配方，避免从零拼。
3. 每个写进配置的对象都要有页面依据：inbound 读协议页 + `shared/listen/`；outbound 读协议页 + `shared/dial/`；TLS 读 `shared/tls/`；分流读 `route/rule/` + `route/rule_action/`；DNS 读 `dns/` + `dns/rule/`；远程 rule-set 读 `rule-set/` + `shared/http-client/`。
4. 读页面上的 `Since` / `Deprecated` / `Removed` / `Changes` 标记，尤其注意目标版本是否已移除。
5. 输出 JSONC；只有目标版本 ≥ 1.14.0 才加 `$schema`。
6. 按「验证阶梯」跑 L1–L3，并如实报告达到哪一级。

### 审查 / 修复

用户配置常来自订阅转换、模板或旧版本；最常见的问题不是语法错，而是字段已移除但仍写着。

1. 逐字段对照目标版本文档确认是否仍存在。
2. 命中废弃/移除时，查 `/deprecated/`、`/migration/` 和 `migration-cheatsheet.md`，不要自己发明替代字段。
3. 输出分三类：**必须改**（已移除/会报错）、**建议改**（已废弃但仍可用）、**文档未提及**（无法判断，交回用户）。
4. 保留用户意图和结构；给最小 diff，不顺手重构成你偏好的写法。
5. 用 `validate.py` 和（如有）`sing-box check` 复核；不要只靠肉眼。

高频雷区：GeoIP/Geosite、旧 DNS server 写法、旧 inbound `sniff`/`domain_strategy`、特殊 outbound、`dns/fakeip/` 与 `dns/server/fakeip/` 的区别、`route.rules[].outbound`（`action: "route"` 下仍合法，不是移除字段）。

### 解释字段（轻量）

默认 3–5 行，不套「结论 + 依据 + 注意事项 + 未提及」四段式：

1. 一句话回答它是什么/做什么。
2. 类型、默认值、可选值、`Since` / `Deprecated` / `Removed`。
3. 一条文档链接；有坑就补一句限制。

只有用户要求完整审查、或问题涉及多个对象时，才展开完整结构。

### `check` 排错

1. 先确认版本，再读 `references/troubleshooting.md` 找同类症状。
2. 让用户提供完整报错原文和最小配置；凭据先脱敏。
3. 只改报错相关字段；不要因为一个 unknown field 重写整份配置。
4. 修完再跑 `sing-box check`；仍失败就缩小到最小复现。

### 版本升级

1. 读目标版本的 `/changelog/`、`/migration/`、`/deprecated/`，再对照 `migration-cheatsheet.md`。
2. 逐项列出用户配置里受影响的字段：已移除、已废弃、行为变更。
3. 给出迁移后的最小配置；不要只列"建议升级"。
4. 用目标版本 schema / `check` 验证；跨大版本时提醒备份。

### 订阅 / Clash / v2ray 转换

1. 只做**语义映射**，不逐键搬运；源格式的键名不是依据。
2. 每个目标字段都回 sing-box 文档确认；找不到就写"未确认"。
3. 先确定目标版本；不同版本的 DNS、rule-set、TUN 字段差异很大。
4. 输出后跑 schema/check；提醒订阅链接本身可能包含真实凭据，注意脱敏。

## 输出契约

### 交付配置

- **文档依据**：依据版本（如 `v1.14.4`）、读了哪些页、每页取用的关键字段和版本标记。
- **配置文件**：完整 JSONC 代码块。
- **关键说明**：用户最需要改、最容易出错的字段。
- **未确认内容**：文档没确认的部分；没有就写"无。"

### 审查结果

- **结论**：能否继续用、主要风险。
- **必须改**：已移除/会报错，逐条给替代写法。
- **建议改**：已废弃/行为变更。
- **文档未提及**：无法判断的部分。
- **修改后配置 / diff**：尽量最小。
- **验证**：跑到了 L1/L2/L3 哪一级。

## JSONC 与 `$schema`

默认输出 JSONC：合法 JSON + `//` 中文注释。

文档 Introduction 只写 "sing-box uses JSON"，没有承诺注释；实际可用是因为 sing-box 的 JSON 解析器支持注释，且 `sing-box format` 会保留注释（`sing` 库 `common/json/comment.go`，format 的 `Comments()` / `SetComments()`）。因此：

- 注释可以留在文件里；
- 编辑器、CI、订阅转换不一定接受 JSONC，交付时说明；
- `sing-box check` 报语法错误时，退回纯 JSON 排查；
- 不要用 `_comment` 伪字段。

`$schema` 字段 **Since 1.14.0**；只有目标版本 ≥ 1.14.0 才默认加。1.14+ 的 tag schema：
`https://raw.githubusercontent.com/SagerNet/sing-box/v<version>/docs/schema.json`；也可让用户用本机版本生成：`sing-box schema -o schema.json`。

## 验证阶梯

| 级别 | 手段 | 只能说 |
|---|---|---|
| L1 | 字段在对应版本文档页确认存在 | "文档确认该字段存在" |
| L2 | 对应版本 `docs/schema.json` 校验通过 | "结构/类型符合该版本 schema" |
| L3 | `sing-box check` 通过 | "语法与组合检查通过" |
| L4 | 用户回报实际运行成功 | "已验证可用" |

```bash
python3 scripts/validate.py config.jsonc -v 1.14.4
sing-box check -c config.jsonc
# 目录式配置：sing-box check -C config_directory
```

`-C/--config-directory` 才是配置目录；`-D/--directory` 是工作目录。官方 format/merge 示例里的 `-D config_directory` 是切工作目录，不是指定配置目录。

`check` 验证的是用户本机版本，不是文档版本；两者不一致时以用户版本为准。schema 通过也不等于运行可用。

## 工具与降级

- 抓文档：优先 `scripts/fetch_docs.py -v <version> <page>`；也可用当前环境的 `web_fetch` / `WebFetch` / `net_fetch`。
- 校验：`scripts/validate.py` 依次做 JSONC 解析、版本字段扫描、schema、`sing-box check`；`--extract` 可直接校验 recipe Markdown 里的第一个可解析 JSONC 块。
- 页数多时交给子 agent（`subagent` / `worker`）并行抓，只回传"字段名 + 类型 + 默认值 + 版本标记 + 限制条件"。
- 大页面（`route/rule/`、`route/rule_action/`、`dns/rule/`、`shared/listen/`、`shared/dial/`、`shared/tls/`、`endpoint/wireguard/`）只提取需要的字段，别整页拉进上下文。

抓不到文档时按顺序降级：

1. 线上站不可达但 GitHub 可达：改用 tag 的 raw 文档（或 jsDelivr 镜像）。
2. 两者都不可达：请用户本地提供文档。可建议：
   `git clone --depth 1 --branch v1.14.4 https://github.com/SagerNet/sing-box`
3. 都做不到：直接停下并说明：

> 我无法访问官方文档链接，因此不能保证不产生幻觉。请手动下载 sing-box 官方文档并提供给我，我会只基于你提供的文档回答。

## 参考文件

- `references/doc-map.md` — 版本化 URL 地图、顶层对象、大小页、锚点、抓取提示。**抓取前先读。**
- `references/migration-cheatsheet.md` — 1.8–1.14 字段迁移索引，最终以 `/deprecated/` 和 `/migration/` 为准。
- `references/troubleshooting.md` — `check` / 启动报错 → 原因 → 文档 → 修复。
- `references/recipes/tun-transparent.md` — Linux TUN 透明代理（1.14+）。
- `references/recipes/mixed-clash-api.md` — mixed + Clash API 客户端（1.14+）。
- `references/recipes/dns-fakeip.md` — FakeIP DNS + TUN（1.14+）。
- `references/recipes/remote-rule-set.md` — 远程 rule-set 分流（1.14+）。
- `assets/config-skeleton.jsonc` — 最小可启动骨架（1.14+）。
- `scripts/fetch_docs.py` / `scripts/validate.py` — 版本化抓取与分层校验。
- `references/refresh-checklist.md` — 发布后核对版本、URL、迁移表和评测的维护清单（仅改 skill 时读）。
- `evals/evals.json` / `evals/trigger-evals.json` — 8 条行为评测与 22 条触发评测；运行方法见 `evals/README.md`（仅维护时使用）。
