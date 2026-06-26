# MinerU 文件提取指南

> **为什么需要提取？** 审计报告(docx)和汇总表(xlsx)是二进制格式，无法直接读取内容进行核对。需要用 MinerU 将其转换为 Markdown 文本，才能进行数值提取和比对。
>
> **重要提醒：** MinerU 提取结果仅供参考。对于关键数据，务必回到源文件（docx/xlsx）二次确认。

---

## 环境确认

MinerU 需要先安装和配置。确认可用：

```powershell
mineru-open-api --help
```

如果提示"未找到命令"，请先参考 MinerU 官方文档安装。

---

## 提取报告（docx → Markdown）

```powershell
mineru-open-api flash-extract "协会文件夹\xxx审计报告.docx" -o "导出目录\协会名_报告.md"
```

**参数说明：**
- 第一个参数：源 docx 文件路径（含空格用引号包裹）
- `-o`：输出 Markdown 文件路径
- 建议输出到统一临时目录，如 `$env:TEMP\report_check\`

---

## 提取汇总表（xlsx → Markdown）

```powershell
mineru-open-api flash-extract "协会文件夹\xxx汇总表.xlsx" -o "导出目录\协会名_汇总表.md"
```

**注意：** 汇总表通常有多个 Sheet（收支汇总表、收入明细表、支出明细表等）。MinerU 会按顺序提取所有 Sheet。提取完成后检查输出文件是否包含全部 Sheet 内容。

---

## 并行提取提高效率

多个协会的提取操作相互独立，可以同时进行：

```powershell
# 在 PowerShell 中用后台作业并行
$jobs = @()
$jobs += Start-Job { mineru-open-api flash-extract "协会A\报告.docx" -o "导出\协会A_报告.md" }
$jobs += Start-Job { mineru-open-api flash-extract "协会B\报告.docx" -o "导出\协会B_报告.md" }
$jobs += Start-Job { mineru-open-api flash-extract "协会C\报告.docx" -o "导出\协会C_报告.md" }

# 等待所有完成
$jobs | Wait-Job | Receive-Job
```

---

## 提取结果验证

提取完成后，快速检查 Markdown 质量：

| 检查项 | 正常 | 异常 |
|--------|------|------|
| 表格是否完整 | 表格行列完整，数字可读 | 表格错位、合并单元格丢失、数字混在一起 |
| 数字是否可识别 | `1,775,477.94` 清晰可读 | 数字被拆分或与文本粘连 |
| Sheet 是否齐全 | 全部 Sheet 都有对应内容 | 缺少某个 Sheet |
| 段落是否完整 | 段落分明，标题层级正确 | 段落合并、标题丢失 |

**如果提取质量不佳：**
1. 尝试重新提取一次（有时是临时问题）
2. 用 MinerU 的精度模式（如果支持）：`mineru-open-api precision-extract ...`
3. 回退到手动从源文件复制关键数据

---

## 文件组织建议

```
$env:TEMP\report_check\
├── 协会A_报告.md
├── 协会A_汇总表.md
├── 协会B_报告.md
├── 协会B_汇总表.md
└── ...
```

提取后的文件与源文件分离管理，避免混淆。
