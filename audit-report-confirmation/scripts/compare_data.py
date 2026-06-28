#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审计报告数据比对脚本

用于两类核对：
1. 核对一：报告与汇总表的勾稽关系（从提取的 Markdown 中识别数值并对比）
2. 核对二：报告内部数据勾稽关系验证

使用方法：
    python compare_data.py --report 协会A_报告.md --summary 协会A_汇总表.md -o 核对结果.md

也可以手动输入数据（当自动提取不准确时）：
    python compare_data.py --manual -o 核对结果.md
"""

import re
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================
# 数据模型
# ============================================================

class FinancialData:
    """存储一个来源（报告或汇总表）的财务数据"""
    
    INCOME_CATEGORIES = ["政府补助收入", "会费收入", "提供服务收入", "其他收入"]
    EXPENSE_CATEGORIES = ["业务活动成本", "管理费用", "其他费用"]
    
    def __init__(self, name: str = ""):
        self.name = name
        self.income_total: Optional[float] = None
        self.expense_total: Optional[float] = None
        self.balance: Optional[float] = None  # 收支结余
        self.income_details: Dict[str, float] = {}
        self.expense_details: Dict[str, float] = {}
        self.special_fund_income: Optional[float] = None
        self.special_fund_expense: Optional[float] = None
        self.special_fund_balance: Optional[float] = None
        self.yearly_data: Dict[str, Dict[str, float]] = {}  # year -> {category: value}
    
    def set_income_detail(self, category: str, value: float):
        self.income_details[category] = value
    
    def set_expense_detail(self, category: str, value: float):
        self.expense_details[category] = value
    
    def add_yearly(self, year: str, category: str, value: float):
        if year not in self.yearly_data:
            self.yearly_data[year] = {}
        self.yearly_data[year][category] = value

# ============================================================
# Markdown 数值提取
# ============================================================

def extract_numbers_from_md(text: str) -> List[Tuple[str, float]]:
    """从 Markdown 文本中提取所有 (标签, 数值) 对"""
    results = []
    
    # 模式1: "标签 xxx数字" — 如 "收入合计1,775,477.94元"
    patterns = [
        r'([\u4e00-\u9fa5]+(?:合计|总计|收入|支出|结余|费用|成本))\s*[：:]\s*([\d,]+\.?\d*)',
        r'([\u4e00-\u9fa5]+(?:合计|总计|收入|支出|结余|费用|成本))\s*([\d,]+\.?\d*)',
        r'(?:收入|支出|结余)[\u4e00-\u9fa5]*\s*[：:]?\s*([\d,]+\.?\d*)',
        r'\|\s*([\u4e00-\u9fa5]+(?:\u6536\u5165|\u652f\u51fa|\u5408\u8ba1|\u603b\u8ba1|\u7ed3\u4f59|费用|成本|补助|会费|服务|管理))\s*\|\s*([\d,]+\.?\d*)',  # 表格格式
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            # 根据模式组数量处理
            groups = match.groups()
            if len(groups) >= 2:
                label = groups[0].strip()
                num_str = groups[-1].strip().replace(",", "")
                try:
                    value = float(num_str)
                    results.append((label, value))
                except ValueError:
                    continue
    
    return results

def extract_tables_from_md(text: str) -> List[List[List[str]]]:
    """从 Markdown 中提取表格结构"""
    tables = []
    current_table = []
    in_table = False
    
    for line in text.split("\n"):
        stripped = line.strip()
        
        # 检测表格行
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # 跳过分隔行 (---|---|---)
            if re.match(r'^[\s\-:]+\|[\s\-:]+', "|".join(cells)):
                continue
            current_table.append(cells)
            in_table = True
        else:
            if in_table and len(current_table) > 0:
                tables.append(current_table)
                current_table = []
                in_table = False
    
    if in_table and len(current_table) > 0:
        tables.append(current_table)
    
    return tables

# ============================================================
# 核对逻辑
# ============================================================

class CheckResult:
    """单项核对结果"""
    def __init__(self, item: str, report_val: str, summary_val: str, 
                 passed: bool, note: str = ""):
        self.item = item
        self.report_val = report_val
        self.summary_val = summary_val
        self.passed = passed
        self.note = note
    
    def to_markdown_row(self) -> str:
        status = "✅" if self.passed else "❌"
        return f"| {self.item} | {self.report_val} | {self.summary_val} | {status} | {self.note} |"

class InternalCheckResult:
    """内部勾稽关系核对结果"""
    def __init__(self, check_item: str, expected: str, actual: str, 
                 passed: bool, note: str = ""):
        self.check_item = check_item
        self.expected = expected
        self.actual = actual
        self.passed = passed
        self.note = note
    
    def to_markdown_row(self) -> str:
        status = "✅" if self.passed else "❌"
        return f"| {self.check_item} | {self.expected} | {self.actual} | {status} | {self.note} |"

def fmt(val: Optional[float]) -> str:
    """格式化数值显示"""
    if val is None:
        return "-"
    return f"{val:,.2f}"

def compare_values(report_val: Optional[float], summary_val: Optional[float], 
                   tolerance: float = 0.01) -> Tuple[bool, float, str]:
    """
    比较两个数值是否在容差范围内一致。
    返回 (是否一致, 差值, 说明)
    """
    if report_val is None and summary_val is None:
        return True, 0.0, "双方均无数据"
    if report_val is None:
        return False, summary_val or 0.0, "报告侧无此数据"
    if summary_val is None:
        return False, report_val, "汇总表侧无此数据"
    
    diff = abs(report_val - summary_val)
    if diff <= tolerance:
        return True, round(report_val - summary_val, 2), "一致"
    else:
        return False, round(report_val - summary_val, 2), f"差异 {diff:.2f}"

def check_internal_consistency(data: FinancialData) -> List[InternalCheckResult]:
    """核对报告内部数据勾稽关系"""
    results = []
    
    # 核对收入
    if data.income_total is not None and data.income_details:
        sum_income = sum(data.income_details.values())
        passed = abs(data.income_total - sum_income) <= 0.01
        results.append(InternalCheckResult(
            "收入合计 = 各分类之和",
            fmt(data.income_total),
            fmt(sum_income),
            passed,
            "" if passed else f"合计{fmt(data.income_total)} ≠ 分类之和{fmt(sum_income)}"
        ))
    
    # 核对支出
    if data.expense_total is not None and data.expense_details:
        sum_expense = sum(data.expense_details.values())
        passed = abs(data.expense_total - sum_expense) <= 0.01
        results.append(InternalCheckResult(
            "支出合计 = 各分类之和",
            fmt(data.expense_total),
            fmt(sum_expense),
            passed,
            "" if passed else f"合计{fmt(data.expense_total)} ≠ 分类之和{fmt(sum_expense)}"
        ))
    
    # 核对收支结余
    if data.income_total is not None and data.expense_total is not None and data.balance is not None:
        calc_balance = data.income_total - data.expense_total
        passed = abs(data.balance - calc_balance) <= 0.01
        results.append(InternalCheckResult(
            "收支结余 = 收入合计 - 支出合计",
            fmt(data.balance),
            fmt(calc_balance),
            passed,
            "" if passed else f"报告结余{fmt(data.balance)} ≠ 计算结余{fmt(calc_balance)}"
        ))
    
    # 核对专项资金
    if data.special_fund_income is not None and data.special_fund_expense is not None and data.special_fund_balance is not None:
        calc_sf = data.special_fund_income - data.special_fund_expense
        passed = abs(data.special_fund_balance - calc_sf) <= 0.01
        results.append(InternalCheckResult(
            "专项资金结余 = 收入 - 支出",
            fmt(data.special_fund_balance),
            fmt(calc_sf),
            passed,
            "" if passed else f"报告专项结余{fmt(data.special_fund_balance)} ≠ 计算{fmt(calc_sf)}"
        ))
    
    if not results:
        results.append(InternalCheckResult("（无足够数据执行内部勾稽核对）", "-", "-", True, "数据不完整"))
    
    return results

# ============================================================
# 手动输入模式
# ============================================================

def manual_input() -> Tuple[FinancialData, FinancialData]:
    """通过交互式输入让用户录入数据"""
    print("\n=== 手动数据录入模式 ===")
    print("输入数值时直接回车可跳过/留空。\n")
    
    report = FinancialData("报告")
    summary = FinancialData("汇总表")
    
    for source_name, data in [("报告", report), ("汇总表", summary)]:
        print(f"\n--- {source_name} 数据 ---")
        
        raw = input(f"{source_name} - 收入合计: ")
        if raw:
            data.income_total = float(raw.replace(",", ""))
        
        raw = input(f"{source_name} - 支出合计: ")
        if raw:
            data.expense_total = float(raw.replace(",", ""))
        
        raw = input(f"{source_name} - 收支结余: ")
        if raw:
            data.balance = float(raw.replace(",", ""))
        
        # 收入明细
        print(f"  {source_name} - 收入明细（直接回车跳过）:")
        for cat in FinancialData.INCOME_CATEGORIES:
            raw = input(f"    {cat}: ")
            if raw:
                data.income_details[cat] = float(raw.replace(",", ""))
        
        # 支出明细
        print(f"  {source_name} - 支出明细（直接回车跳过）:")
        for cat in FinancialData.EXPENSE_CATEGORIES:
            raw = input(f"    {cat}: ")
            if raw:
                data.expense_details[cat] = float(raw.replace(",", ""))
        
        # 专项资金
        print(f"  {source_name} - 专项资金（直接回车跳过）:")
        raw = input(f"    专项资金收入: ")
        if raw:
            data.special_fund_income = float(raw.replace(",", ""))
        raw = input(f"    专项资金支出: ")
        if raw:
            data.special_fund_expense = float(raw.replace(",", ""))
        raw = input(f"    专项资金结余: ")
        if raw:
            data.special_fund_balance = float(raw.replace(",", ""))
    
    return report, summary

# ============================================================
# 自动提取模式
# ============================================================

def auto_extract(filepath: str) -> FinancialData:
    """从 MinerU 提取的 Markdown 文件中自动识别财务数据"""
    data = FinancialData(Path(filepath).stem)
    
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    
    # 提取数值对
    pairs = extract_numbers_from_md(text)
    
    # 按关键词匹配（简单的启发式规则）
    income_keywords = ["收入合计", "收入总计", "总收入"]
    expense_keywords = ["支出合计", "支出总计", "总支出", "费用合计", "成本合计"]
    balance_keywords = ["收支结余", "结余", "本年结余"]
    
    for label, value in pairs:
        if any(kw in label for kw in income_keywords):
            data.income_total = value
        elif any(kw in label for kw in expense_keywords):
            data.expense_total = value
        elif any(kw in label for kw in balance_keywords):
            data.balance = value
        
        # 收入分类
        for cat in FinancialData.INCOME_CATEGORIES:
            if cat in label:
                data.income_details[cat] = value
        
        # 支出分类
        for cat in FinancialData.EXPENSE_CATEGORIES:
            if cat in label:
                data.expense_details[cat] = value
    
    return data

# ============================================================
# 报告生成
# ============================================================

def generate_report(
    report_name: str,
    report: FinancialData,
    summary: FinancialData,
    cross_checks: List[CheckResult],
    internal_checks: List[InternalCheckResult],
    text_issues: List[str] = None,
    output_path: str = None
) -> str:
    """生成核对结果 Markdown 报告"""
    
    lines = []
    lines.append(f"# 核对结果：{report_name}")
    lines.append("")
    
    # --- 核对一 ---
    lines.append("## 一、报告与汇总表勾稽关系核对")
    lines.append("")
    lines.append("| 项目 | 报告数据 | 汇总表数据 | 结果 | 备注 |")
    lines.append("|------|---------|-----------|:----:|------|")
    for c in cross_checks:
        lines.append(c.to_markdown_row())
    lines.append("")
    
    # --- 核对二 ---
    lines.append("## 二、报告内部数据勾稽关系")
    lines.append("")
    lines.append("| 检查项 | 报告数据 | 计算结果 | 结果 | 备注 |")
    lines.append("|--------|---------|---------|:----:|------|")
    for c in internal_checks:
        lines.append(c.to_markdown_row())
    lines.append("")
    
    # --- 核对三 ---
    if text_issues:
        lines.append("## 三、错别字/语句问题")
        lines.append("")
        lines.append("| 序号 | 问题描述 |")
        lines.append("|:---:|---------|")
        for i, issue in enumerate(text_issues, 1):
            lines.append(f"| {i} | {issue} |")
        lines.append("")
    
    # --- 汇总 ---
    all_passed = all(c.passed for c in cross_checks) and all(c.passed for c in internal_checks)
    failed_items = [c for c in cross_checks if not c.passed] + [c for c in internal_checks if not c.passed]
    
    lines.append("## 四、汇总")
    lines.append("")
    if all_passed and not text_issues:
        lines.append("**结论：全部核对通过 ✅**")
    else:
        issues_count = len(failed_items) + (len(text_issues) if text_issues else 0)
        lines.append(f"**发现 {issues_count} 项问题：**")
        if failed_items:
            lines.append(f"- 数据差异 {len(failed_items)} 项")
        if text_issues:
            lines.append(f"- 文本问题 {len(text_issues)} 项")
    lines.append("")
    
    report_text = "\n".join(lines)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"核对结果已写入: {output_path}")
    
    return report_text

# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="审计报告数据比对工具 -- 支持自动提取和手动录入两种模式"
    )
    parser.add_argument("--report", "-r", help="报告提取结果的 Markdown 文件路径")
    parser.add_argument("--summary", "-s", help="汇总表提取结果的 Markdown 文件路径")
    parser.add_argument("--output", "-o", default="核对结果.md", help="输出文件路径")
    parser.add_argument("--name", "-n", default="", help="协会名称")
    parser.add_argument("--manual", "-m", action="store_true", 
                        help="手动输入模式（当自动提取不准确时使用）")
    
    args = parser.parse_args()
    
    # 手动模式
    if args.manual:
        report, summary = manual_input()
    elif args.report and args.summary:
        report = auto_extract(args.report)
        summary = auto_extract(args.summary)
        print(f"从文件提取数据完成:")
        print(f"  报告: {args.report}")
        print(f"  汇总表: {args.summary}")
    else:
        parser.print_help()
        print("\n错误：请提供 --report 和 --summary 文件路径，或使用 --manual 手动输入。")
        sys.exit(1)
    
    # 执行核对一：勾稽关系
    cross_checks = []
    
    items = [
        ("收入合计", report.income_total, summary.income_total),
        ("支出合计", report.expense_total, summary.expense_total),
        ("收支结余", report.balance, summary.balance),
    ]
    
    # 收入明细
    for cat in FinancialData.INCOME_CATEGORIES:
        rv = report.income_details.get(cat)
        sv = summary.income_details.get(cat)
        items.append((f"  {cat}", rv, sv))
    
    # 支出明细
    for cat in FinancialData.EXPENSE_CATEGORIES:
        rv = report.expense_details.get(cat)
        sv = summary.expense_details.get(cat)
        items.append((f"  {cat}", rv, sv))
    
    # 专项资金
    if report.special_fund_income is not None or summary.special_fund_income is not None:
        items.append(("专项资金收入", report.special_fund_income, summary.special_fund_income))
        items.append(("专项资金支出", report.special_fund_expense, summary.special_fund_expense))
        items.append(("专项资金结余", report.special_fund_balance, summary.special_fund_balance))
    
    for item_name, rv, sv in items:
        passed, diff, note = compare_values(rv, sv)
        cross_checks.append(CheckResult(item_name, fmt(rv), fmt(sv), passed, note))
    
    # 执行核对二：内部勾稽
    internal_checks = check_internal_consistency(report)
    
    # 生成报告
    name = args.name or (Path(args.report).stem if args.report else "未知")
    generate_report(name, report, summary, cross_checks, internal_checks, 
                   output_path=args.output)

if __name__ == "__main__":
    main()
