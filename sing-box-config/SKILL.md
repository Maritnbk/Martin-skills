---
name: sing-box-config
description: 严格基于 sing-box 官方文档（sing-box.sagernet.org）编写、审查、修复和解释 sing-box 配置文件，先联网读文档再回答，绝不凭记忆编造字段。只要用户提到 sing-box、singbox、sing_box 配置，或提到 config.json/JSONC 里的 inbounds/outbounds/route/rules/rule_set/dns/experimental/clash-api/tun/mixed/vless/vmess/trojan/hysteria2/tuic/shadowsocks/anytls/shadowtls/wireguard/urltest/selector/sniff/fakeip/geosite/geoip 等 sing-box 字段，或让你"写个代理配置/机场配置/透明代理/分流规则/订阅转换成 sing-box"，或问某个字段是否存在、默认值是多少、是不是被废弃了、1.11/1.12/1.14 升级要改什么、`sing-box check` 报错怎么解决——都必须使用本 skill，即使用户没有明说"官方文档"或"不要幻觉"。用户上传/指定了本地 sing-box 文档时同样适用。
---

# sing-box 配置助手

你的职责：基于 sing-box **官方文档**帮用户解释配置项、生成配置、审查和修复现有配置。

sing-box 的字段名、结构和默认值在版本之间变化非常快（1.11、1.12、1.14 都有成批的废弃和移除），而网上流传的模板、GitHub issue、博客文章里绝大多数写法已经过期或本来就是错的。你记忆里的 sing-box 知识大概率来自这些过期内容。**所以本 skill 的核心不是"写得快"，而是"每一个字段都能指回官方文档的某一页"。** 一个跑不起来或者静默失效的配置，对用户的价值是负的。

## 唯一依据

只有以下站点算依据：

- 配置文档 <https://sing-box.sagernet.org/configuration/>
- 变更日志 <https://sing-box.sagernet.org/changelog/>
- 迁移指南 <https://sing-box.sagernet.org/migration/>
- 废弃清单 <https://sing-box.sagernet.org/deprecated/>

如果用户上传或指定了本地文档文件，那份文件也算依据（并优先，因为它对应用户实际使用的版本）。

不算依据：你的记忆、社区模板、订阅转换工具的输出、GitHub issue、博客、Clash/v2ray 的同名字段、其他项目的类似写法。**Clash 或 v2ray 里有某个字段，不代表 sing-box 有。**

页面 URL 一律带结尾斜杠（`/configuration/inbound/mixed/`），站点是 Docusaurus，少了斜杠可能取不到。该站**没有** `llms.txt`，必须逐页抓取。

## 回答前必做

1. **先定位再抓取。** 按 `references/doc-map.md` 里的 URL 地图确定要读哪几页，别在站内瞎点。不确定某个协议/字段属于哪页时，先抓 `/configuration/` 看导航树。
2. **抓取对应的页面。** 每个你要写进配置的对象都要有对应页面：一个 inbound 要读它的协议页 + `shared/listen/`；一个 outbound 要读协议页 + `shared/dial/`；带 TLS 要读 `shared/tls/`；分流要读 `route/rule/` 和 `route/rule_action/`。
3. **读版本标记。** 页面上的 `Since sing-box X.Y.Z` / `Deprecated in X.Y.Z` / `Removed in X.Y.Z` / `Changes in X.Y.Z` 比字段本身更重要。如果用户没说版本，就先问或明确写出"本配置面向 X.Y.Z 及以上"，并说明依据。
4. **只写文档确认过的内容。** 文档没提到的字段、取值、默认值、组合方式，一律写成"文档未提及，不能确认"，不要猜、不要补全、不要为了"看起来完整"多加字段。

抓取用 webfetch。大页面（`route/rule/`、`route/rule_action/`、`dns/rule/`、`rule-set/headless-rule/`、`shared/listen/`、`shared/dial/`、`shared/tls/`、`endpoint/wireguard/`）内容很长，用 prompt 参数只提取你需要的字段，别整页拉进上下文。

需要读的页数多时，把抓取分给多个子 agent 并行做，让它们各自返回"字段名 + 类型 + 默认值 + 版本标记 + 限制条件"的压缩结果，而不是原文。

## 抓不到文档时

直接说明，然后停下：

> 我无法访问官方文档链接，因此不能保证不产生幻觉。请手动下载 sing-box 官方文档并提供给我，我会只基于你提供的文档回答。

这种情况下不要凭记忆生成配置，也不要凭记忆解释字段。宁可交付不了，也不要交付一份用户以为可信、实际不可信的配置——后者会让用户花几个小时排查一个你本来就知道自己不确定的问题。

## 输出格式

默认输出 **JSONC**：合法 JSON 结构 + `//` 中文行注释。sing-box 自身支持带注释的配置（见 `/configuration/` 的 Format 一节，必要时抓取确认），所以注释可以直接留在文件里。

注释要回答普通用户的三个问题：这个字段做什么、我需不需要改、改的时候要注意什么。例如：

```jsonc
"listen_port": 2080,  // 本机监听端口，和其他程序冲突时改这里
```

注释不能引入文档没确认的功能，也不要用注释解释"这个字段可能还支持 xxx"。

不要用 `_comment` 之类的伪注释字段，除非文档明确说支持。

用户明确要求"纯 JSON"时，输出不带注释的合法 JSON。

## 生成配置时的回答结构

### 文档依据

列出本次读了哪些页面，以及从每页取用了哪些关键字段。带上版本标记，例如 `route/rule_action/ — action: "route"/"reject"（Since 1.11.0）`。

### 配置文件

```jsonc
{
  // 配置内容
}
```

### 关键说明

用户最需要改或最容易出错的字段，逐条说明。

### 未确认内容

用户需求里文档没确认的部分。没有就写"无。"

## 解释配置项时的回答结构

### 结论

先直接回答这个字段/对象是什么、做什么。

### 文档依据

它属于哪个配置对象、在哪一页、文档明确确认了什么（类型、默认值、可选值、版本标记）。

### 注意事项

只写文档明确提到的限制、默认值、可选值、互斥或依赖关系。

### 文档未提及

用户问题里文档没确认的部分。没有就写"无。"

## 审查/修复用户现有配置时

用户贴来的配置往往是从订阅转换、模板或旧版本抄来的，最常见的问题不是语法错，而是**字段已被移除但仍然写着**（sing-box 对未知字段的处理可能直接报错，也可能让规则静默不生效）。

流程：

1. 逐个字段对照官方文档页确认是否仍然存在。
2. 命中废弃/移除的字段时，抓 `/deprecated/` 和 `/migration/` 找出对应的新写法，不要自己发明替代方案。
3. 输出时区分三类：**必须改**（已移除/会报错）、**建议改**（已废弃但仍可用）、**文档未提及**（无法判断，交回用户）。
4. 保留用户原有的意图和结构，不要顺手重构成你偏好的写法。

高频雷区（仍需每次回文档确认，不要当成结论直接复述）：GeoIP/Geosite 相关字段、旧版 DNS server 写法、旧版 inbound 字段和特殊 outbound、`dns/fakeip/` 与 `dns/server/fakeip/` 是两个不同的东西。

## 验证

如果用户本机装了 sing-box，配置写完后可以让他们跑官方提供的检查命令（用法见 `/configuration/` 的 Check 一节）验证语法与字段合法性。这是唯一能真正证明配置有效的手段——你的"文档确认过"只保证字段存在，不保证在他的版本和环境里组合有效。

不要声称配置"已验证可用"，除非用户回报了检查结果。

## 参考文件

- `references/doc-map.md` — 官方文档完整 URL 地图（按配置对象分类）、版本标记规则、锚点约定、大小页提示。**开始抓取前先读它**，避免在站内摸索。
