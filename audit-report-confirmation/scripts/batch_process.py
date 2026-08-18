#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量审计报告核对处理脚本

支持：
1. 对多个年度或多个被审计单位依次运行核对
2. 汇总所有结果到一份总报告中
3. 支持单年度和多年度两种模式

用法：
    # 单年度多单位
    python batch_process.py --data-dir "数据目录" --output "汇总核对结果.md"
    
    # 多年度单个单位
    python batch_process.py --multi-year --data-dir "各年度数据目录" --output "多年度汇总.md"
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional


def discover_data_files(data_dir: str, suffix: str = ".json") -> List[str]:
    """从目录中发现数据文件"""
    data_path = Path(data_dir)
    if not data_path.exists():
        return []
    
    files = []
    for f in data_path.iterdir():
        if f.is_file() and f.suffix == suffix:
            files.append(str(f))
    return sorted(files)


def run_single_check(data_file: str, compare_script: str,
                     output_dir: str, year: str = "") -> dict:
    """对单个数据文件运行核对"""
    
    output_file = Path(output_dir) / f"{Path(data_file).stem}_核对结果.md"
    
    cmd = [
        sys.executable, compare_script,
        "--single-year", data_file,
        "--output", str(output_file),
        "--year", year,
        "--name", Path(data_file).stem,
    ]
    
    result = {
        "name": Path(data_file).stem,
        "output": str(output_file),
        "success": False,
        "all_passed": False,
        "has_issues": False,
        "error": "",
        "total": 0,
        "passed": 0,
        "failed": 0,
        "na": 0,
    }
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            result["success"] = True
            # 分析输出统计行
            for line in proc.stdout.split("\n"):
                if "核对完成" in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            ratio = parts[1].split("/")
                            result["passed"] = int(ratio[0])
                            result["total"] = int(ratio[1])
                            result["failed"] = result["total"] - result["passed"]
                            result["all_passed"] = result["passed"] == result["total"]
                            result["has_issues"] = result["failed"] > 0
                        except (IndexError, ValueError):
                            pass
        else:
            result["error"] = proc.stderr[:500]
    except subprocess.TimeoutExpired:
        result["error"] = "执行超时（120秒）"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def generate_master_report(results: List[dict], output_path: str,
                           data_dir: str, timestamp: str,
                           is_multi_year: bool = False):
    """生成汇总报告"""
    
    lines = []
    lines.append("# 审计报告核对汇总结果")
    lines.append("")
    lines.append(f"- **核对时间：** {timestamp}")
    lines.append(f"- **数据目录：** {data_dir}")
    lines.append(f"- **核对单位/年度数：** {len(results)}")
    lines.append("")
    
    # 一、核对范围
    lines.append("## 一、核对范围")
    lines.append("")
    for r in results:
        if r.get("success"):
            status = "✅" if r.get("all_passed") else "⚠️"
            lines.append(f"- {status} {r['name']}" + 
                        (f" ({r['passed']}/{r['total']} 通过)" if r.get("total", 0) > 0 else ""))
        else:
            lines.append(f"- ❌ {r['name']} — 执行失败: {r.get('error', '未知错误')}")
    lines.append("")
    
    # 二、总体统计
    lines.append("## 二、总体统计")
    lines.append("")
    success_count = sum(1 for r in results if r.get("success"))
    all_passed_count = sum(1 for r in results if r.get("all_passed"))
    has_issues_count = sum(1 for r in results if r.get("has_issues"))
    
    total_checks = sum(r.get("total", 0) for r in results)
    passed_checks = sum(r.get("passed", 0) for r in results)
    failed_checks = sum(r.get("failed", 0) for r in results)
    
    lines.append("| 指标 | 数值 |")
    lines.append("|------|:----:|")
    lines.append(f"| 核对总数 | {len(results)} |")
    lines.append(f"| 成功完成 | {success_count} |")
    lines.append(f"| 全部通过 | {all_passed_count} |")
    lines.append(f"| 存在问题 | {has_issues_count} |")
    lines.append(f"| 核验项总数（含无相关内容） | {total_checks} |")
    lines.append(f"| ✅ 通过 | {passed_checks} |")
    lines.append(f"| ❌ 不通过 | {failed_checks} |")
    if total_checks > 0:
        effective = total_checks - sum(r.get("na", 0) for r in results)
        if effective > 0:
            lines.append(f"| 通过率（不含无相关内容） | {passed_checks/effective*100:.1f}% |")
    lines.append("")
    
    # 三、各结果
    lines.append("## 三、各年度/单位核对结果")
    lines.append("")
    
    for r in results:
        if r.get("success"):
            lines.append(f"### {r['name']}")
            lines.append("")
            if r.get("all_passed"):
                lines.append(f"✅ **全部核对通过** ({r['passed']}/{r['total']})")
            else:
                lines.append(f"⚠️ **存在发现项** ({r['passed']}/{r['total']} 通过)")
            lines.append("")
            lines.append(f"详细结果：`{Path(r['output']).name}`")
            lines.append("")
        else:
            lines.append(f"### {r['name']} ❌")
            lines.append("")
            lines.append(f"执行失败：{r.get('error', '未知错误')}")
            lines.append("")
    
    # 四、重点关注建议
    lines.append("## 四、重点关注建议")
    lines.append("")
    
    if has_issues_count > 0:
        lines.append(f"以下 {has_issues_count} 个结果存在发现项，建议优先复查：")
        lines.append("")
        for r in results:
            if r.get("has_issues"):
                lines.append(f"- {r['name']} ({r['passed']}/{r['total']} 通过) — 见 `{Path(r['output']).name}`")
        lines.append("")
    
    failed_results = [r for r in results if not r.get("success")]
    if failed_results:
        lines.append(f"以下 {len(failed_results)} 个单位/年度执行失败，需手动检查：")
        lines.append("")
        for r in failed_results:
            lines.append(f"- {r['name']} — {r.get('error', '')}")
        lines.append("")
    
    if has_issues_count == 0 and not failed_results:
        lines.append("本次核对未发现问题。")
        lines.append("")
    
    if is_multi_year:
        lines.append("### 跨年度衔接关注点")
        lines.append("")
        lines.append("对于多年度核对，请务必检查：")
        lines.append("1. 各年度资产负债表期末=下年度期初的衔接一致性")
        lines.append("2. 各年度利润表本年累计=下年度上年累计的衔接一致性")
        lines.append("3. 上年度发现的问题是否已在本年度修正")
        lines.append("")
    
    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"汇总核对结果已写入: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="批量审计报告核对工具")
    parser.add_argument("--data-dir", "-d", required=True,
                        help="数据文件目录（包含 JSON 数据文件）")
    parser.add_argument("--output", "-o", default="汇总核对结果.md",
                        help="输出汇总文件路径")
    parser.add_argument("--compare-script", "-c",
                        default=str(Path(__file__).parent / "compare_data.py"),
                        help="compare_data.py 脚本路径")
    parser.add_argument("--multi-year", action="store_true",
                        help="多年度模式（自动检测各年度目录）")
    parser.add_argument("--years", help="指定年度列表，逗号分隔")
    
    args = parser.parse_args()
    data_dir = args.data_dir
    compare_script = args.compare_script
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建输出目录
    output_dir = Path(args.output).parent
    if str(output_dir) != ".":
        output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    if args.multi_year:
        # 多年度模式：每个子目录是一个年度
        data_path = Path(data_dir)
        years = args.years.split(",") if args.years else sorted(
            [d.name for d in data_path.iterdir() if d.is_dir()]
        )
        
        for year in years:
            year_dir = data_path / year
            if not year_dir.exists():
                print(f"  警告: {year} 目录不存在，跳过")
                continue
            
            print(f"\n正在核对 {year} 年度...")
            data_file = year_dir / f"{year}_data.json"
            if not data_file.exists():
                # 搜索目录中的 JSON 文件
                json_files = list(year_dir.glob("*.json"))
                if json_files:
                    data_file = json_files[0]
                else:
                    print(f"  警告: {year} 目录中未找到 JSON 数据文件，跳过")
                    continue
            
            result = run_single_check(str(data_file), compare_script,
                                       str(output_dir), year)
            
            if result["success"]:
                print(f"  ✅ {year}: {result['passed']}/{result['total']} 通过")
            else:
                print(f"  ❌ {year}: {result.get('error', '')}")
            
            results.append(result)
    
    else:
        # 单年度多单位模式：data-dir 包含多个 JSON 文件
        json_files = discover_data_files(data_dir, ".json")
        
        if not json_files:
            print(f"在 {data_dir} 中未找到 JSON 数据文件。")
            sys.exit(1)
        
        print(f"发现 {len(json_files)} 个数据文件")
        
        for data_file in json_files:
            name = Path(data_file).stem
            print(f"\n正在核对: {name}")
            
            result = run_single_check(data_file, compare_script,
                                       str(output_dir))
            
            if result["success"]:
                print(f"  ✅ {name}: {result['passed']}/{result['total']} 通过")
            else:
                print(f"  ❌ {name}: {result.get('error', '')}")
            
            results.append(result)
    
    # 生成汇总报告
    if results:
        generate_master_report(results, args.output, args.data_dir,
                               timestamp, args.multi_year)
        
        success = sum(1 for r in results if r.get("success"))
        print(f"\n{'='*40}")
        print(f"处理完成: {success}/{len(results)} 成功")
        print(f"汇总文件: {args.output}")
    else:
        print("没有处理任何数据。")


if __name__ == "__main__":
    main()
