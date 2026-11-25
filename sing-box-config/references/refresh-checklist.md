# 发布后刷新清单

最后核对：2026-11-23

这份清单用于 sing-box 新稳定版发布后，或每 1–2 个月，重新校准 skill 的事实基础。目标不是“把所有文档再抄一遍”，而是找出**会改变答案的版本差异**，并让 eval 能证明 skill 仍然比裸模型可靠。

## 触发时机

- 新的 `x.y.0` 稳定版发布（字段废弃/移除通常集中在这里）。
- alpha / beta 出现新的大功能（例如 1.15 的 Tailcat、MASQUE）。
- 线上文档与最近一次核对出现明显差异。
- 用户连续两次报告同一个“文档里有、skill 没有”的字段。

## 0. 先留快照

```bash
cd /home/jxpc003/projects/dsh/skills
cp -a sing-box-config sing-box-config-snapshot-$(date +%F)
cd sing-box-config
```

快照用于 eval 的旧版 baseline；不要在快照上继续修改。

## 1. 确认版本

```bash
# 稳定版
curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases/latest | jq -r .tag_name

# 预发布（有 alpha/beta 时）
curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases | jq -r '.[].tag_name' | head
```

GitHub API 不可达时，改用项目 release 页面或 `https://sing-box.sagernet.org/` 首页的版本号；不要凭记忆填版本。

记录：

- 最新稳定版：`vX.Y.Z`
- 最新预发布：`vX.Y.Z-alpha.N`（没有就写“无”）
- 本次核对日期（`YYYY-MM-DD`）

## 2. 更新 `references/doc-map.md`

逐项检查：

- [ ] 顶部“最后核对”日期。
- [ ] 稳定版 / 预发布版本号，以及“线上站代表最新线”的提醒是否仍准确。
- [ ] 版本选择表：tag 文档、`testing` 分支、1.10 及以下的 best-effort 策略是否仍可用。
- [ ] 顶层对象表是否与对应 tag 的 `docs/schema.json` 一致（14 个顶层键是否变化）。
- [ ] 是否出现新的顶层分类（例如 1.14 的 `http_clients`、`network_namespaces`）。
- [ ] 版本差异速查表是否补上本次的 deprecated / removed 项。
- [ ] 新增 inbound / outbound / endpoint / DNS server 是否进入对应清单。
- [ ] 代表性 URL 是否仍返回 200；至少抽查：
  - `/configuration/index/`
  - `/configuration/dns/`
  - `/configuration/route/`
  - `/configuration/route/rule_action/`
  - `/configuration/shared/http-client/`
  - `/migration/`
  - `/deprecated/`
  - `/schema.json`

快速抓取：

```bash
python3 scripts/fetch_docs.py -v <version> schema --out /tmp/schema.json
python3 scripts/fetch_docs.py -v <version> migration
python3 scripts/fetch_docs.py -v <version> deprecated
```

## 3. 更新 `references/migration-cheatsheet.md`

先读对应 tag 的 `/migration/` 和 `/deprecated/`，再改表：

- [ ] 新增“废弃版本 → 移除版本 → 替代写法”的行。
- [ ] 只写文档明确给出的移除版本；文档只说 deprecated 时，不要替它推断 removed。
- [ ] 区分“字段仍在但语义变了”和“字段已移除”。
- [ ] 特别检查容易误判的项：`route.rules[].outbound` 在 `action: "route"` 下仍然合法，不要当成移除字段。
- [ ] 给每条迁移补一个官方页面路径。

## 4. 更新 `references/troubleshooting.md`

- [ ] 把本次 release 后用户最可能遇到的 1–3 个新报错加进去。
- [ ] 每条保持“症状 → 原因 → 最小修复 → 文档页”。
- [ ] 不把猜测写成确定原因；无法确认时写“先确认版本/完整报错”。

## 5. 更新 recipes 与 skeleton

- [ ] 四个 recipe 的目标版本是否还合适；如果新版有更简单的写法，先改 recipe 再改 SKILL。
- [ ] `assets/config-skeleton.jsonc` 的 `$schema` 只在目标版本 ≥ 1.14.0 时保留。
- [ ] 所有配置跑一遍：

```bash
for f in references/recipes/*.md; do
  echo "== $f"
  python3 scripts/validate.py "$f" -v <version> --no-check --extract
done
python3 scripts/validate.py assets/config-skeleton.jsonc -v <version> --no-check
```

- 如果本机装了 `sing-box`，再跑 L3：

```bash
sing-box check -c <config>
```

没有 L3 时，报告只能写“结构符合 schema”，不能写“check 通过”。

## 6. 重跑行为 eval

- [ ] 用快照作为旧版 baseline，当前版本作为 with-skill。
- [ ] 至少跑 `evals/evals.json` 的 8 条；每条同时跑 with-skill 和 baseline。
- [ ] 评分只依据 `expectations` 和实际输出；schema 通过必须有命令输出，不能凭感觉。
- [ ] 验收线：
  - 编造字段：0。
  - with-skill 的 expectations 通过率明显高于 baseline。
  - 第 8 条（文档不可达）必须拒绝生成，不能“凭经验补全”。

运行方法见 `evals/README.md`。

## 7. 重跑触发 eval

- [ ] 用 `evals/trigger-evals.json` 的 12 条正例、10 条负例。
- [ ] 每条跑 3 次，记录触发率。
- [ ] 正例目标 ≥ 90%，负例误触发目标 ≤ 10%。
- [ ] 如果负例被误触发，优先在 `description` 里补负边界，不要把整个 skill 写成“只适用于 sing-box”。
- [ ] 如果正例漏触发，补用户真实会说的短语（例如“订阅转换”“check 报错”“TUN 透明代理”），而不是堆砌字段名。

## 8. 收尾

- [ ] 更新 `SKILL.md` 的“最后核对”相关表述（如有）。
- [ ] 更新改进计划里的实施记录。
- [ ] 删除临时文档目录和 `__pycache__`。
- [ ] 检查 `git diff`，确认没有把用户真实 UUID、密码、订阅链接写进示例。
