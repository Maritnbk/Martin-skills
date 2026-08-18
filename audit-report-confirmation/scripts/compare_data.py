#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审计报告数据核对脚本

支持以下核对类型：
1. 资产负债表逐项加总核对（期末/期初）
2. 利润表分层核对（本年累计/上年累计）
3. 现金流量表分层核对（本年累计/上年累计）
4. 跨表勾稽核对
5. 附注表格内部勾稽核对
6. 多年度跨期衔接核对

用法：
    # 单年度核对
    python compare_data.py --bs data_bs.json --is data_is.json --cf data_cf.json -o 核对结果.md
    # 或者
    python compare_data.py --bs data_bs.json --income-stmt data_is.json --cf data_cf.json -o 核对结果.md

    # 手动输入模式
    python compare_data.py --manual -o 核对结果.md

    # 多年度核对
    python compare_data.py --multi-year --years 2022,2023,2024 --data-dir ./years -o 多年度核对结果.md
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# ============================================================
# 数值处理
# ============================================================

def clean_number(val: Any) -> Optional[float]:
    """将各种格式的数值转为 float，无法转换时返回 None"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    if isinstance(val, str):
        s = val.strip()
        if not s or s in ("-", "--", "—", ""):
            return None
        # 去掉千分位逗号、人民币符号、空格
        s = s.replace(",", "").replace("，", "").replace("¥", "").replace(" ", "")
        # 处理括号表示负数： (100) -> -100
        if s.startswith("(") and s.endswith(")"):
            try:
                return -round(float(s[1:-1]), 2)
            except ValueError:
                return None
        try:
            return round(float(s), 2)
        except ValueError:
            return None
    return None


def fmt(val: Optional[float]) -> str:
    """格式化数值显示"""
    if val is None:
        return "-"
    return f"{val:,.2f}"


# ============================================================
# 核对结果模型
# ============================================================

class CheckResult:
    """单项核对结果
    
    status: "pass" | "fail" | "na" (无相关内容)
    """
    
    def __init__(self, category: str, check_item: str, 
                 expected: Optional[float] = None, actual: Optional[float] = None,
                 passed: bool = True, detail: str = "",
                 year: str = "", status: str = "pass"):
        self.category = category
        self.check_item = check_item
        self.expected = expected
        self.actual = actual
        self.passed = passed
        self.detail = detail
        self.year = year
        self.status = status  # "pass" | "fail" | "na"
    
    def to_markdown_row(self) -> str:
        if self.status == "na":
            status = "➖"
            exp = "-"
            act = "-"
            detail = self.detail or "被审计单位无此业务/无此表格"
        else:
            status = "✅" if self.passed else "❌"
            exp = fmt(self.expected)
            act = fmt(self.actual)
            detail = self.detail
        return f"| {self.check_item} | {exp} | {act} | {status} | {detail} |"


# ============================================================
# 资产负债表核对
# ============================================================

BS_FORMULAS = {
    "存货": ["原材料", "在产品", "库存商品", "周转材料"],
    "流动资产合计": [
        "货币资金", "短期投资", "应收票据", "应收账款", "预付账款",
        "应收股利", "应收利息", "其他应收款", "存货", "其他流动资产"
    ],
    "非流动资产合计": [
        "长期债权投资", "长期股权投资", "固定资产账面价值",
        "在建工程", "工程物资", "固定资产清理", "生产性生物资产",
        "无形资产", "开发支出", "长期待摊费用", "其他非流动资产"
    ],
    "资产总计": ["流动资产合计", "非流动资产合计"],
    "流动负债合计": [
        "短期借款", "应付票据", "应付账款", "预收账款",
        "应付职工薪酬", "应交税费", "应付利息", "应付利润",
        "其他应付款", "其他流动负债"
    ],
    "非流动负债合计": [
        "长期借款", "长期应付款", "递延收益", "其他非流动负债"
    ],
    "所有者权益合计": ["实收资本", "资本公积", "盈余公积", "未分配利润"],
}

BS_SPECIAL = {
    "固定资产账面价值": ("固定资产原值", "累计折旧"),  # 原值 - 折旧
}


def check_balance_sheet(data: Dict[str, Dict[str, Optional[float]]],
                        year: str = "") -> List[CheckResult]:
    """
    核对资产负债表。
    data: {"期末余额": {"货币资金": 1000, ...}, "年初余额": {...}}
    
    约束：每一项核对公式都必须执行并记录，不可跳过。
    - 数据存在时：逐项加总后比较，标记 ✅ 或 ❌
    - 数据不存在时：标记 ➖ 无相关内容
    """
    results = []
    
    for period in ["期末余额", "年初余额"]:
        if period not in data:
            # 整个期间缺失 —— 所有合计项标记为无相关内容
            for total_name in BS_FORMULAS:
                results.append(CheckResult(
                    category=f"资产负债表-{period}",
                    check_item=total_name,
                    status="na",
                    detail="被审计单位无此期间数据",
                    year=year,
                ))
            continue
        
        items = data[period]
        
        for total_name, components in BS_FORMULAS.items():
            if total_name in items and items[total_name] is not None:
                # 合计项存在 —— 执行加总验证
                component_sum = 0.0
                missing = []
                for comp in components:
                    v = items.get(comp)
                    if v is not None:
                        component_sum += v
                    else:
                        missing.append(comp)
                
                reported: float = items[total_name]  # type: ignore[assignment]
                passed = abs(reported - component_sum) <= 0.01
                detail = ""
                if not passed:
                    detail = f"{total_name}({fmt(reported)}) ≠ 明细之和({fmt(component_sum)})"
                    if missing:
                        detail += f"；缺失: {', '.join(missing)}"
                else:
                    if missing:
                        detail = f"一致（缺失项按0处理: {', '.join(missing)}）"
                
                results.append(CheckResult(
                    category=f"资产负债表-{period}",
                    check_item=total_name,
                    expected=reported,
                    actual=component_sum,
                    passed=passed,
                    detail=detail,
                    year=year,
                ))
            else:
                # 合计项不存在 —— 仍列示，标记无相关内容
                results.append(CheckResult(
                    category=f"资产负债表-{period}",
                    check_item=total_name,
                    status="na",
                    detail="被审计单位无此科目",
                    year=year,
                ))
        
        # 特殊验证：固定资产账面价值 = 原值 - 累计折旧
        has_orig = "固定资产原值" in items and items["固定资产原值"] is not None
        has_dep = "累计折旧" in items and items["累计折旧"] is not None
        has_nv = "固定资产账面价值" in items and items["固定资产账面价值"] is not None
        
        if has_orig and has_dep and has_nv:
            orig: float = items["固定资产原值"]  # type: ignore[assignment]
            dep: float = items["累计折旧"]  # type: ignore[assignment]
            reported_nv: float = items["固定资产账面价值"]  # type: ignore[assignment]
            calc_nv = orig - dep
            passed = abs(reported_nv - calc_nv) <= 0.01
            results.append(CheckResult(
                category=f"资产负债表-{period}",
                check_item="固定资产账面价值(原值-折旧)",
                expected=reported_nv,
                actual=calc_nv,
                passed=passed,
                detail="" if passed else f"原值{fmt(orig)}-折旧{fmt(dep)}={fmt(calc_nv)}≠报表{fmt(reported_nv)}",
                year=year,
            ))
        elif "固定资产账面价值" in items:
            # 有账面价值科目但缺少原值或折旧 → 无法验证，标记
            results.append(CheckResult(
                category=f"资产负债表-{period}",
                check_item="固定资产账面价值(原值-折旧)",
                status="na",
                detail="缺少固定资产原值或累计折旧数据，无法验证",
                year=year,
            ))
    
    return results


# ============================================================
# 利润表核对
# ============================================================

IS_FORMULAS = {
    "税金及附加": [
        "消费税", "城市维护建设税", "资源税", "土地增值税",
        "城镇土地使用税", "房产税", "车船税", "印花税",
        "教育费附加", "矿产资源税", "排污费"
    ],
    "营业利润": [
        "营业收入", "营业成本", "税金及附加", "销售费用",
        "管理费用", "财务费用", "投资收益"
    ],
    "利润总额": ["营业利润", "营业外收入", "营业外支出"],
    "净利润": ["利润总额", "所得税费用"],
}

IS_FORMULA_TYPES = {
    "税金及附加": "sum",           # 各项之和
    "营业利润": "加减",            # 收入-成本-税金-费用+投资收益
    "利润总额": "加减",            # 营业利润+营业外收入-营业外支出
    "净利润": "subtract",          # 利润总额-所得税费用
}


def check_income_statement(data: Dict[str, Dict[str, Optional[float]]],
                           year: str = "") -> List[CheckResult]:
    """核对利润表
    
    约束：每一项核对公式都必须执行并记录，不可跳过。
    """
    results = []
    
    for period in ["本年累计数", "上年累计数"]:
        if period not in data:
            for total_name in IS_FORMULAS:
                results.append(CheckResult(
                    category=f"利润表-{period}",
                    check_item=total_name,
                    status="na",
                    detail="被审计单位无此期间数据",
                    year=year,
                ))
            continue
        
        items = data[period]
        
        for total_name, components in IS_FORMULAS.items():
            if total_name in items and items[total_name] is not None:
                reported: float = items[total_name]  # type: ignore[assignment]
                fmt_type = IS_FORMULA_TYPES.get(total_name, "sum")
                
                if fmt_type == "sum":
                    calc_val = sum(float(items.get(c, 0) or 0) for c in components)
                elif fmt_type == "加减":
                    if len(components) == 7:
                        rev = items.get(components[0], 0) or 0
                        cost = items.get(components[1], 0) or 0
                        tax = items.get(components[2], 0) or 0
                        sell = items.get(components[3], 0) or 0
                        admin = items.get(components[4], 0) or 0
                        fin = items.get(components[5], 0) or 0
                        invest = items.get(components[6], 0) or 0
                        calc_val = rev - cost - tax - sell - admin - fin + invest
                    else:
                        calc_val = sum(float(items.get(c, 0) or 0) for c in components)
                elif fmt_type == "subtract":
                    if len(components) == 2:
                        a = items.get(components[0], 0) or 0
                        b = items.get(components[1], 0) or 0
                        calc_val = a - b
                    else:
                        calc_val = sum(float(items.get(c, 0) or 0) for c in components)
                else:
                    calc_val = sum(float(items.get(c, 0) or 0) for c in components)
                
                passed = abs(reported - calc_val) <= 0.01
                results.append(CheckResult(
                    category=f"利润表-{period}",
                    check_item=total_name,
                    expected=reported,
                    actual=calc_val,
                    passed=passed,
                    detail="" if passed else f"{total_name}({fmt(reported)})≠计算值({fmt(calc_val)})",
                    year=year,
                ))
            else:
                results.append(CheckResult(
                    category=f"利润表-{period}",
                    check_item=total_name,
                    status="na",
                    detail="被审计单位无此科目",
                    year=year,
                ))
    
    return results


# ============================================================
# 现金流量表核对
# ============================================================

CF_FORMULAS = {
    "经营活动产生的现金流量净额": [
        "销售产成品商品提供劳务收到的现金",
        "收到的税费返还",
        "收到其他与经营活动有关的现金",
        "购买原材料商品接受劳务支付的现金",
        "支付的职工薪酬",
        "支付的税费",
        "支付其他与经营活动有关的现金",
    ],
    "投资活动产生的现金流量净额": [
        "收回短期投资长期债券投资和长期股权投资收到的现金",
        "取得投资收益收到的现金",
        "处置固定资产无形资产和其他非流动资产收回的现金净额",
        "短期投资长期债券投资和长期股权投资支付的现金",
        "购建固定资产无形资产和其他非流动资产支付的现金",
    ],
    "筹资活动产生的现金流量净额": [
        "取得借款收到的现金",
        "吸收投资者投资收到的现金",
        "偿还借款本金支付的现金",
        "偿还借款利息支付的现金",
        "支付的其他与筹资活动有关的现金",
    ],
}

CF_FORMULA_TYPES = {
    "经营活动产生的现金流量净额": "operating",   # inflow - outflow
    "投资活动产生的现金流量净额": "investing",
    "筹资活动产生的现金流量净额": "financing",
}


def check_cash_flow(data: Dict[str, Dict[str, Optional[float]]],
                    year: str = "") -> List[CheckResult]:
    """核对现金流量表
    
    约束：每一项核对公式都必须执行并记录，不可跳过。
    """
    results = []
    
    for period in ["本年累计发生额", "上年累计发生额"]:
        if period not in data:
            for net_name in CF_FORMULAS:
                results.append(CheckResult(
                    category=f"现金流量表-{period}",
                    check_item=net_name,
                    status="na",
                    detail="被审计单位无此期间数据",
                    year=year,
                ))
            results.append(CheckResult(
                category=f"现金流量表-{period}",
                check_item="现金净增加额",
                status="na",
                detail="被审计单位无此期间数据",
                year=year,
            ))
            results.append(CheckResult(
                category=f"现金流量表-{period}",
                check_item="期末现金余额",
                status="na",
                detail="被审计单位无此期间数据",
                year=year,
            ))
            continue
        
        items = data[period]
        
        # 验证各活动净额
        for net_name, components in CF_FORMULAS.items():
            if net_name in items and items[net_name] is not None:
                reported: float = items[net_name]  # type: ignore[assignment]
                fmt_type = CF_FORMULA_TYPES[net_name]
                
                if fmt_type == "operating":
                    inflow = sum(items.get(c, 0) or 0 for c in components[:3])
                    outflow = sum(items.get(c, 0) or 0 for c in components[3:])
                    calc_val = inflow - outflow
                elif fmt_type == "investing":
                    inflow = sum(items.get(c, 0) or 0 for c in components[:3])
                    outflow = sum(items.get(c, 0) or 0 for c in components[3:])
                    calc_val = inflow - outflow
                elif fmt_type == "financing":
                    inflow = sum(items.get(c, 0) or 0 for c in components[:2])
                    outflow = sum(items.get(c, 0) or 0 for c in components[2:])
                    calc_val = inflow - outflow
                else:
                    calc_val = 0
                
                passed = abs(reported - calc_val) <= 0.01
                results.append(CheckResult(
                    category=f"现金流量表-{period}",
                    check_item=net_name,
                    expected=reported,
                    actual=calc_val,
                    passed=passed,
                    detail="" if passed else f"{net_name}({fmt(reported)})≠计算值({fmt(calc_val)})",
                    year=year,
                ))
            else:
                results.append(CheckResult(
                    category=f"现金流量表-{period}",
                    check_item=net_name,
                    status="na",
                    detail="被审计单位无此业务",
                    year=year,
                ))
        
        # 现金净增加额
        if "现金净增加额" in items and items["现金净增加额"] is not None:
            op = float(items.get("经营活动产生的现金流量净额", 0) or 0)
            iv = float(items.get("投资活动产生的现金流量净额", 0) or 0)
            fn = float(items.get("筹资活动产生的现金流量净额", 0) or 0)
            fx = float(items.get("汇率变动对现金的影响额", 0) or 0)
            calc_net = op + iv + fn + fx
            reported_net: float = items["现金净增加额"]  # type: ignore[assignment]
            passed = abs(reported_net - calc_net) <= 0.01
            results.append(CheckResult(
                category=f"现金流量表-{period}",
                check_item="现金净增加额",
                expected=reported_net,
                actual=calc_net,
                passed=passed,
                detail="" if passed else f"净增加额({fmt(reported_net)})≠经营+投资+筹资+汇率({fmt(calc_net)})",
                year=year,
            ))
        else:
            results.append(CheckResult(
                category=f"现金流量表-{period}",
                check_item="现金净增加额",
                status="na",
                detail="被审计单位无此科目",
                year=year,
            ))
        
        # 期末现金余额
        has_end = "期末现金余额" in items and items["期末现金余额"] is not None
        has_start = "期初现金余额" in items and items["期初现金余额"] is not None
        if has_end and has_start:
            end: float = items["期末现金余额"]  # type: ignore[assignment]
            start: float = items["期初现金余额"]  # type: ignore[assignment]
            net = float(items.get("现金净增加额", 0) or 0)
            calc_end = net + start
            passed = abs(end - calc_end) <= 0.01
            results.append(CheckResult(
                category=f"现金流量表-{period}",
                check_item="期末现金余额",
                expected=end,
                actual=calc_end,
                passed=passed,
                detail="" if passed else f"期末({fmt(end)})≠净增加额({fmt(net)})+期初({fmt(start)})={fmt(calc_end)}",
                year=year,
            ))
        else:
            results.append(CheckResult(
                category=f"现金流量表-{period}",
                check_item="期末现金余额",
                status="na",
                detail="被审计单位缺少期末或期初现金余额数据",
                year=year,
            ))
    
    return results


# ============================================================
# 跨表勾稽核对
# ============================================================

def check_cross_table(bs_data: Dict[str, Dict[str, Optional[float]]],
                      cf_data: Dict[str, Dict[str, Optional[float]]],
                      is_data: Dict[str, Dict[str, Optional[float]]],
                      year: str = "") -> List[CheckResult]:
    """核对跨表勾稽关系"""
    results = []
    
    # 1. 货币资金期末余额 = 现金流量表本年累计期末现金余额
    bs_end = (bs_data.get("期末余额") or {}).get("货币资金")
    cf_curr_end = (cf_data.get("本年累计发生额") or {}).get("期末现金余额")
    if bs_end is not None and cf_curr_end is not None:
        passed = abs(bs_end - cf_curr_end) <= 0.01
        results.append(CheckResult(
            category="跨表勾稽",
            check_item="货币资金期末=CF期末现金余额(本年)",
            expected=bs_end,
            actual=cf_curr_end,
            passed=passed,
            detail="" if passed else f"BS货币资金期末{fmt(bs_end)}≠CF期末现金余额{fmt(cf_curr_end)}",
            year=year,
        ))
    
    # 2. 货币资金年初余额 = 现金流量表上年累计期末现金余额
    bs_start = (bs_data.get("年初余额") or {}).get("货币资金")
    cf_prev_end = (cf_data.get("上年累计发生额") or {}).get("期末现金余额")
    if bs_start is not None and cf_prev_end is not None:
        passed = abs(bs_start - cf_prev_end) <= 0.01
        results.append(CheckResult(
            category="跨表勾稽",
            check_item="货币资金年初=CF期末现金余额(上年)",
            expected=bs_start,
            actual=cf_prev_end,
            passed=passed,
            detail="" if passed else f"BS货币资金年初{fmt(bs_start)}≠CF期末现金余额(上年){fmt(cf_prev_end)}",
            year=year,
        ))
    
    # 3. 未分配利润期末-期初 = 净利润本年累计数
    bs_end_unprofit = (bs_data.get("期末余额") or {}).get("未分配利润")
    bs_start_unprofit = (bs_data.get("年初余额") or {}).get("未分配利润")
    is_net = (is_data.get("本年累计数") or {}).get("净利润")
    if bs_end_unprofit is not None and bs_start_unprofit is not None and is_net is not None:
        diff = bs_end_unprofit - bs_start_unprofit
        passed = abs(diff - is_net) <= 0.01
        results.append(CheckResult(
            category="跨表勾稽",
            check_item="未分配利润变动=净利润",
            expected=is_net,
            actual=diff,
            passed=passed,
            detail="" if passed else f"未分配利润变动({fmt(diff)})≠净利润{fmt(is_net)}",
            year=year,
        ))
    
    return results


# ============================================================
# 附注表格核对
# ============================================================

def check_note_table(table_type: str,
                     table_data: Dict[str, Any],
                     year: str = "") -> List[CheckResult]:
    """
    核对附注表格内部勾稽。
    
    table_type: 表格类型
        - "aging": 账龄表
        - "top5": 前五名明细表
        - "fixed_asset": 固定资产表
        - "long_term_prepaid": 长期待摊费用
        - "payroll": 应付职工薪酬
        - "capital": 实收资本
        - "balance_only": 只有期末/期初余额的表格
        - "occurrence_only": 只有本期/上期发生额的表格
    
    table_data: {
        "rows": [{"name": "...", "期末余额": 100, "期初余额": 50, ...}],
        "summary": {"name": "合计", "期末余额": 500, "期初余额": 250, ...}
    }
    """
    results = []
    rows = table_data.get("rows", [])
    summary = table_data.get("summary", {})
    
    if not rows or not summary:
        return results
    
    # 提取所有数值列
    value_keys = [k for k in summary.keys() if k != "name"]
    
    for vk in value_keys:
        if vk not in summary or summary[vk] is None:
            continue
        
        row_sum = sum(row.get(vk, 0) or 0 for row in rows)
        summary_val = summary[vk]
        
        passed = abs(summary_val - row_sum) <= 0.01
        results.append(CheckResult(
            category=f"附注-{table_type}",
            check_item=f"明细之和={vk}",
            expected=summary_val,
            actual=row_sum,
            passed=passed,
            detail="" if passed else f"{vk}: 合计{fmt(summary_val)}≠明细之和{fmt(row_sum)}",
            year=year,
        ))
    
    # 特殊验证：固定资产表 - 账面原值-累计折旧-减值准备=账面价值
    if table_type == "fixed_asset":
        for row in rows + [summary]:
            if all(k in row and row[k] is not None for k in ["原值", "累计折旧", "减值准备", "账面价值"]):
                calc_nv = row["原值"] - row["累计折旧"] - (row.get("减值准备", 0) or 0)
                passed = abs(row["账面价值"] - calc_nv) <= 0.01
                results.append(CheckResult(
                    category="附注-固定资产表",
                    check_item=f"{row.get('name','')}账面价值(原值-折旧-减值)",
                    expected=row["账面价值"],
                    actual=calc_nv,
                    passed=passed,
                    detail="" if passed else f"{row.get('name','')}: 账面价值{fmt(row['账面价值'])}≠原值-折旧-减值={fmt(calc_nv)}",
                    year=year,
                ))
    
    # 特殊验证：实收资本 - 期初+本期增加-本期减少=期末
    if table_type == "capital":
        for row in rows + [summary]:
            s = row.get("期初余额")
            inc = row.get("本期增加")
            dec = row.get("本期减少")
            e = row.get("期末余额")
            if s is not None and e is not None:
                calc_e = s + (inc or 0) - (dec or 0)
                passed = abs(e - calc_e) <= 0.01
                results.append(CheckResult(
                    category="附注-实收资本",
                    check_item=f"{row.get('name','')}期初+增加-减少=期末",
                    expected=e,
                    actual=calc_e,
                    passed=passed,
                    detail="" if passed else f"{row.get('name','')}: 期初{fmt(s)}+增加{fmt(inc or 0)}-减少{fmt(dec or 0)}={fmt(calc_e)}≠期末{fmt(e)}",
                    year=year,
                ))
    
    # 特殊验证：变化表类型 - 期初+本期增加-本期减少=期末
    if table_type in ("long_term_prepaid", "payroll"):
        for row in rows + [summary]:
            s = row.get("期初余额")
            inc = row.get("本期增加")
            dec = row.get("本期减少")
            e = row.get("期末余额")
            if s is not None and e is not None:
                calc_e = s + (inc or 0) - (dec or 0)
                passed = abs(e - calc_e) <= 0.01
                results.append(CheckResult(
                    category=f"附注-{table_type}",
                    check_item=f"{row.get('name','')}期初+增加-减少=期末",
                    expected=e,
                    actual=calc_e,
                    passed=passed,
                    detail="" if passed else f"期初{fmt(s)}+增加{fmt(inc or 0)}-减少{fmt(dec or 0)}={fmt(calc_e)}≠期末{fmt(e)}",
                    year=year,
                ))
    
    return results


# ============================================================
# 多年度衔接核对
# ============================================================

def check_multi_year_linkage(yearly_data: Dict[str, Dict],
                             year: str = "") -> List[CheckResult]:
    """
    核对多年度数据衔接。
    
    yearly_data: {
        "2022": {"bs": {...}, "is": {...}, "cf": {...}},
        "2023": {"bs": {...}, "is": {...}, "cf": {...}},
        ...
    }
    """
    results = []
    years = sorted(yearly_data.keys())
    
    for i in range(len(years) - 1):
        curr_year = years[i]
        next_year = years[i + 1]
        
        curr_bs = yearly_data[curr_year].get("bs", {})
        next_bs = yearly_data[next_year].get("bs", {})
        
        # 资产负债表跨年：本年期末 = 下年期初
        if "期末余额" in curr_bs and "年初余额" in next_bs:
            curr_end = curr_bs["期末余额"]
            next_start = next_bs["年初余额"]
            common_items = set(curr_end.keys()) & set(next_start.keys())
            
            for item in sorted(common_items):
                cv = curr_end[item]
                nv = next_start[item]
                if cv is not None and nv is not None:
                    passed = abs(cv - nv) <= 0.01
                    results.append(CheckResult(
                        category="多年度衔接",
                        check_item=f"{item}({curr_year}末 → {next_year}初)",
                        expected=cv,
                        actual=nv,
                        passed=passed,
                        detail="" if passed else f"{item}: {curr_year}末{fmt(cv)}≠{next_year}初{fmt(nv)}",
                        year=f"{curr_year}-{next_year}",
                    ))
        
        # 利润表跨年：本年累计 = 下年上年累计
        curr_is = yearly_data[curr_year].get("is", {})
        next_is = yearly_data[next_year].get("is", {})
        if "本年累计数" in curr_is and "上年累计数" in next_is:
            curr_is_vals = curr_is["本年累计数"]
            next_is_prev = next_is["上年累计数"]
            common = set(curr_is_vals.keys()) & set(next_is_prev.keys())
            for item in sorted(common):
                cv = curr_is_vals[item]
                nv = next_is_prev[item]
                if cv is not None and nv is not None:
                    passed = abs(cv - nv) <= 0.01
                    results.append(CheckResult(
                        category="多年度衔接",
                        check_item=f"{item} ({curr_year}本年→{next_year}上年)",
                        expected=cv,
                        actual=nv,
                        passed=passed,
                        detail="" if passed else f"{item}: {curr_year}本年{fmt(cv)}≠{next_year}上年{fmt(nv)}",
                        year=f"{curr_year}-{next_year}",
                    ))
        
        # 现金流量表跨年
        curr_cf = yearly_data[curr_year].get("cf", {})
        next_cf = yearly_data[next_year].get("cf", {})
        if "本年累计发生额" in curr_cf and "上年累计发生额" in next_cf:
            curr_cf_vals = curr_cf["本年累计发生额"]
            next_cf_prev = next_cf["上年累计发生额"]
            common = set(curr_cf_vals.keys()) & set(next_cf_prev.keys())
            for item in sorted(common):
                cv = curr_cf_vals[item]
                nv = next_cf_prev[item]
                if cv is not None and nv is not None:
                    passed = abs(cv - nv) <= 0.01
                    results.append(CheckResult(
                        category="多年度衔接",
                        check_item=f"CF {item} ({curr_year}本年→{next_year}上年)",
                        expected=cv,
                        actual=nv,
                        passed=passed,
                        detail="" if passed else f"CF {item}: {curr_year}本年{fmt(cv)}≠{next_year}上年{fmt(nv)}",
                        year=f"{curr_year}-{next_year}",
                    ))
    
    return results


# ============================================================
# 报告生成
# ============================================================

def generate_report(results: List[CheckResult],
                    report_name: str = "审计报告核对结果",
                    text_issues: Optional[List[str]] = None,
                    highlights: Optional[List[str]] = None,
                    output_path: Optional[str] = None) -> str:
    """生成核对结果 Markdown 报告"""
    
    lines = []
    lines.append(f"# 核对结果：{report_name}")
    lines.append("")
    
    # 按类别分组
    categories = {}
    for r in results:
        cat = r.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    # 通过率统计
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    na_count = sum(1 for r in results if r.status == "na")
    
    # 输出每个类别
    for cat in sorted(categories.keys()):
        checks = categories[cat]
        cat_passed = sum(1 for r in checks if r.status == "pass")
        cat_failed = sum(1 for r in checks if r.status == "fail")
        cat_na = sum(1 for r in checks if r.status == "na")
        lines.append(f"## {cat}")
        lines.append("")
        lines.append(f"| 检查项 | 报表值 | 计算值 | 结果 | 备注 |")
        lines.append(f"|--------|--------|--------|:----:|------|")
        for r in checks:
            lines.append(r.to_markdown_row())
        lines.append("")
        parts = [f"**{cat}: {cat_passed} ✅ / {cat_failed} ❌"]
        if cat_na > 0:
            parts.append(f"{cat_na} ➖ 无相关内容")
        parts.append("**")
        lines.append(" ".join(parts))
        lines.append("")
    
    # 文本问题
    if text_issues:
        lines.append("## 文本问题")
        lines.append("")
        for i, issue in enumerate(text_issues, 1):
            lines.append(f"{i}. {issue}")
        lines.append("")
    
    # 汇总
    lines.append("## 汇总")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|:----:|")
    lines.append(f"| 核对项总数 | {total} |")
    lines.append(f"| ✅ 通过 | {passed} |")
    lines.append(f"| ❌ 不通过 | {failed} |")
    lines.append(f"| ➖ 无相关内容 | {na_count} |")
    effective = total - na_count
    if effective > 0:
        lines.append(f"| 通过率（不含无相关内容） | {passed/effective*100:.1f}% |")
    lines.append("")
    
    # 未通过项
    if failed > 0:
        lines.append("### ❌ 不通过项明细")
        lines.append("")
        lines.append("| 类别 | 检查项 | 报表值 | 计算值 | 备注 |")
        lines.append("|------|--------|--------|--------|------|")
        for r in results:
            if r.status == "fail":
                lines.append(f"| {r.category} | {r.check_item} | {fmt(r.expected)} | {fmt(r.actual)} | {r.detail} |")
        lines.append("")
    
    # 重点关注建议
    if highlights:
        lines.append("## 重点关注建议")
        lines.append("")
        for h in highlights:
            lines.append(f"- {h}")
        lines.append("")
    
    report_text = "\n".join(lines)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"核对结果已写入: {output_path}")
    
    return report_text


# ============================================================
# 手动交互模式
# ============================================================

def manual_input() -> List[CheckResult]:
    """通过交互式输入进行核对"""
    results = []
    print("\n=== 手动核对模式 ===\n")
    
    # 资产负债表
    print("--- 资产负债表 ---")
    bs_end = {}
    bs_start = {}
    
    print("\n输入期末余额（直接回车结束）：")
    while True:
        name = input("  科目名称: ")
        if not name:
            break
        val = input(f"  {name} 期末余额: ")
        if val:
            v = clean_number(val)
            if v is not None:
                bs_end[name] = v
                # 也问期初
                val2 = input(f"  {name} 年初余额: ")
                if val2:
                    v2 = clean_number(val2)
                    if v2 is not None:
                        bs_start[name] = v2
    
    if bs_end:
        results.extend(check_balance_sheet({"期末余额": bs_end, "年初余额": bs_start}))
    
    # 利润表
    print("\n--- 利润表 ---")
    is_curr = {}
    is_prev = {}
    
    print("\n输入本年累计数（直接回车结束）：")
    while True:
        name = input("  科目名称: ")
        if not name:
            break
        val = input(f"  {name} 本年累计数: ")
        if val:
            v = clean_number(val)
            if v is not None:
                is_curr[name] = v
                val2 = input(f"  {name} 上年累计数: ")
                if val2:
                    v2 = clean_number(val2)
                    if v2 is not None:
                        is_prev[name] = v2
    
    if is_curr:
        results.extend(check_income_statement({"本年累计数": is_curr, "上年累计数": is_prev}))
    
    # 现金流量表
    print("\n--- 现金流量表 ---")
    cf_curr = {}
    cf_prev = {}
    
    print("\n输入本年累计发生额（直接回车结束）：")
    while True:
        name = input("  项目名称: ")
        if not name:
            break
        val = input(f"  {name} 本年累计发生额: ")
        if val:
            v = clean_number(val)
            if v is not None:
                cf_curr[name] = v
                val2 = input(f"  {name} 上年累计发生额: ")
                if val2:
                    v2 = clean_number(val2)
                    if v2 is not None:
                        cf_prev[name] = v2
    
    if cf_curr:
        results.extend(check_cash_flow({"本年累计发生额": cf_curr, "上年累计发生额": cf_prev}))
    
    # 跨表勾稽
    if bs_end and bs_start and cf_curr and is_curr:
        results.extend(check_cross_table(
            {"期末余额": bs_end, "年初余额": bs_start},
            {"本年累计发生额": cf_curr, "上年累计发生额": cf_prev},
            {"本年累计数": is_curr, "上年累计数": is_prev},
        ))
    
    return results


# ============================================================
# JSON 数据输入模式
# ============================================================

def load_from_json(filepath: str) -> Dict:
    """从 JSON 文件加载数据"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def run_single_year(data: Dict, year: str = "") -> List[CheckResult]:
    """对单年度数据执行所有核对"""
    results = []
    
    if "bs" in data:
        results.extend(check_balance_sheet(data["bs"], year))
    if "is" in data:
        results.extend(check_income_statement(data["is"], year))
    if "cf" in data:
        results.extend(check_cash_flow(data["cf"], year))
    if "bs" in data and "cf" in data and "is" in data:
        results.extend(check_cross_table(data["bs"], data["cf"], data["is"], year))
    if "notes" in data:
        for table_type, table_data in data["notes"].items():
            results.extend(check_note_table(table_type, table_data, year))
    
    return results


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="审计报告数据核对工具")
    parser.add_argument("--bs", help="资产负债表 JSON 文件")
    parser.add_argument("--is", "--income-stmt", dest="income_stmt", help="利润表 JSON 文件")
    parser.add_argument("--cf", help="现金流量表 JSON 文件")
    parser.add_argument("--notes", help="附注表格 JSON 文件")
    parser.add_argument("--single-year", help="单年度数据 JSON 文件（包含 bs/is/cf/notes）")
    parser.add_argument("--multi-year", help="多年度数据 JSON 文件（按年份组织）")
    parser.add_argument("--manual", action="store_true", help="手动输入模式")
    parser.add_argument("--output", "-o", default="核对结果.md", help="输出文件路径")
    parser.add_argument("--name", "-n", default="审计报告", help="报告名称")
    parser.add_argument("--year", default="", help="当前年度")
    
    args = parser.parse_args()
    results = []
    
    if args.manual:
        results = manual_input()
    
    elif args.multi_year:
        data = load_from_json(args.multi_year)
        for year in sorted(data.keys()):
            results.extend(run_single_year(data[year], year))
        # 多年度衔接
        results.extend(check_multi_year_linkage(data))
    
    elif args.single_year:
        data = load_from_json(args.single_year)
        results = run_single_year(data, args.year)
    
    elif args.bs or args.income_stmt or args.cf:
        bs_data = load_from_json(args.bs) if args.bs else {}
        is_data = load_from_json(args.income_stmt) if args.income_stmt else {}
        cf_data = load_from_json(args.cf) if args.cf else {}
        notes_data = load_from_json(args.notes) if args.notes else {}
        
        if bs_data:
            results.extend(check_balance_sheet(bs_data, args.year))
        if is_data:
            results.extend(check_income_statement(is_data, args.year))
        if cf_data:
            results.extend(check_cash_flow(cf_data, args.year))
        if bs_data and cf_data and is_data:
            results.extend(check_cross_table(bs_data, cf_data, is_data, args.year))
        if notes_data:
            for table_type, table_data in notes_data.items():
                results.extend(check_note_table(table_type, table_data, args.year))
    
    else:
        parser.print_help()
        print("\n请提供数据文件或使用 --manual 手动输入模式。")
        print("\nJSON 数据格式参考：")
        print("  --single-year: {\"bs\":{\"期末余额\":{...},\"年初余额\":{...}},\"is\":{...},\"cf\":{...},\"notes\":{\"aging\":{...}}}")
        print("  --multi-year: {\"2023\":{\"bs\":{...}},\"2024\":{\"bs\":{...}}}")
        sys.exit(1)
    
    # 生成报告
    generate_report(
        results,
        report_name=args.name,
        output_path=args.output,
    )
    
    # 输出简要统计
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    print(f"\n核对完成: {passed}/{total} 通过", end="")
    if failed > 0:
        print(f", {failed} 项未通过", end="")
    print()


if __name__ == "__main__":
    main()
