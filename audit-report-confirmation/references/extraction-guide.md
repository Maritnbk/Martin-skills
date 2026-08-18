# MinerU 文件提取指南

## 为什么需要提取

审计报告(docx)、财务报表(xlsx)、附注(docx)是二进制格式，无法直接读取内容进行核对。需要用 MinerU 将其转换为 Markdown 文本，才能进行数值提取和比对。

> **重要：** MinerU 提取结果仅供参考。对于关键数据，务必回到源文件二次确认。

---

## 环境确认

```powershell
mineru-open-api --help
```

如果提示未找到命令，请先安装 MinerU。

---

## 提取操作

### 提取报告正文

```powershell
mineru-open-api flash-extract "路径\被审计单位_审计报告.docx" -o "导出目录\被审计单位_报告.md"
```

### 提取财务报表

```powershell
mineru-open-api flash-extract "路径\被审计单位_财务报表.xlsx" -o "导出目录\被审计单位_财务报表.md"
```

> 财务报表通常有多张表（资产负债表、利润表、现金流量表），检查提取结果是否包含全部表格。

### 提取附注

```powershell
mineru-open-api flash-extract "路径\被审计单位_附注.docx" -o "导出目录\被审计单位_附注.md"
```

### 并行提取提高效率

多个文件的提取操作相互独立，可以同时进行：

```powershell
# 并行提取三个文件
$job1 = Start-Job { mineru-open-api flash-extract "路径\报告.docx" -o "导出\报告.md" }
$job2 = Start-Job { mineru-open-api flash-extract "路径\财务报表.xlsx" -o "导出\财务报表.md" }
$job3 = Start-Job { mineru-open-api flash-extract "路径\附注.docx" -o "导出\附注.md" }
$job1,$job2,$job3 | Wait-Job | Receive-Job
```

---

## 提取结果验证

| 检查项 | 正常 | 异常 |
|--------|------|------|
| 表格完整性 | 行列完整，数字可读 | 表格错位、合并单元格丢失 |
| 数字可识别 | `1,775,477.94` 清晰可读 | 数字被拆分或与文本粘连 |
| 全部内容 | 所有章节/Sheet 都有对应内容 | 缺少某部分 |
| 段落/标题 | 层级正确，段落分明 | 段落合并、标题丢失 |

### 提取质量不佳时的处理方法

1. 重新提取一次（有时是临时问题）
2. 使用精度模式：`mineru-open-api precision-extract ...`
3. 关键数据从源文件手动复制

---

## 文件组织建议

```
导出目录\
├── 被审计单位_报告.md
├── 被审计单位_财务报表.md
└── 被审计单位_附注.md
```
