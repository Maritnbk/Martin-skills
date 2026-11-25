# sing-box-config evals

这里放两类评测：

- `evals.json`：8 条行为评测，检查 skill 是否按版本查文档、是否编造字段、是否给出可验证的最小修复。
- `trigger-evals.json`：12 条正例 + 10 条负例，用于检查 `description` 的触发边界。

## 当前状态

评测定义已落地。**本轮没有伪造 with-skill / baseline 的通过率**；跑完整 benchmark 需要独立的 agent 会话和评分，按下面的协议执行。

## 行为评测怎么跑

评测遵循 skill-creator 的 with-skill / baseline 对照：

1. 先留旧版快照（改进前）：

```bash
cd /home/jxpc003/projects/dsh/skills
cp -a sing-box-config sing-box-config-snapshot-$(date +%F)
```

2. 在工作区建 iteration 目录：

```bash
mkdir -p sing-box-config-workspace/iteration-1
```

3. 每条 eval 跑两个独立会话：
   - `with_skill`：告诉 agent 先读 `sing-box-config/SKILL.md`，再执行 prompt。
   - `old_skill`：让它读快照里的 `SKILL.md`，执行同一个 prompt。
   - 输出保存到 `iteration-1/eval-<id>-<name>/with_skill/outputs/` 和 `old_skill/outputs/`。

4. 每条 eval 建 `eval_metadata.json`，把 `evals.json` 里的 `expectations` 原样带进去。

5. 评分时逐条写 `grading.json`，字段必须是：

```json
{
  "expectations": [
    {"text": "原断言文本", "passed": true, "evidence": "输出中的具体证据/命令结果"}
  ],
  "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0}
}
```

没有证据的断言按失败处理；schema/check 结论必须附命令和输出。

6. 汇总后看两件事：
   - 编造字段数是否为 0。
   - with-skill 的通过率是否明显高于 old_skill。
   - 第 8 条必须拒绝生成，不能“凭经验补全”。

## 触发评测怎么跑

如果环境里有 `claude` CLI，可以用 skill-creator 的 `run_loop.py`：

```bash
python -m scripts.run_loop \
  --eval-set evals/trigger-evals.json \
  --skill-path /home/jxpc003/projects/dsh/skills/sing-box-config \
  --model <model-id> \
  --max-iterations 5 \
  --verbose
```

没有该 CLI 时，手工做最小检查：每条 query 跑 3 次，记录是否触发；正例目标 ≥ 90%，负例误触发 ≤ 10%。

## 断言设计约定

- 断言必须能指向输出里的具体句子、字段或命令结果，不能写“回答得很好”。
- 版本类断言必须出现明确版本号；不能接受“最新版”这种模糊说法。
- 字段类断言同时检查“应该出现的字段”和“不应该出现的旧字段/Clash 键名”。
- 引用类断言只算官方页面（`sing-box.sagernet.org` 或对应 tag 的 `docs/`），博客、issue、订阅转换结果不算。
- 文档不可达时，正确行为是停下来要文档；生成配置即使看起来合理也算失败。

## 已知校正

计划里第 1 条 eval 曾写“1.12.8 配置带 `$schema`”。这是错的：`$schema` 字段 1.14.0 才引入，1.12.8 不应包含。当前 `evals.json` 已按“不写 `$schema`”设计，并用 `validate.py -v 1.12.8` 做版本扫描。

计划里第 2 条 eval 曾把 route rule 的 `outbound` 当成需要迁移的旧写法。实际在 1.14 里它仍然合法，省略 `action` 时默认就是 `route`；真正要改的是 `outbound: "block"` 指向的已移除 outbound。当前断言已改为检查这个区别，避免把正确写法误判成错误。
