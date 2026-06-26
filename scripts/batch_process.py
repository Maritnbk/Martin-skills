#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量审计报告核对处理脚本

对多个协会依次运行核对流程，汇总所有结果到一份总报告中。

用法：
    python batch_process.py --data-dir "导出目录" --output "汇总核对结果.md"
    
    # 也可以手动指定协会列表
    python batch_process.py --data-dir "导出目录" --associations "协会A","协会B" -o "汇总.md"
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def discover_associations(data_dir: str) -> list:
    """从目录中自动发现协会名称"""
    data_path = Path(data_dir)
    names = set()
    
    # 找 _报告.md 和 _汇总表.md 文件
    for f in data_path.glob("*_报告.md"):
        stem = f.stem.replace("_报告", "")
        names.add(stem)
    for f in data_path.glob("*_汇总表.md"):
        stem = f.stem.replace("_汇总表", "")
        names.add(stem)
    
    return sorted(names)


def find_files(data_dir: str, assoc_name: str) -> tuple:
    """查找协会对应的报告和汇总表文件"""
    data_path = Path(data_dir)
    
    report_patterns = [
        f"{assoc_name}_报告.md",
        f"{assoc_name}审计报告.md",
        f"{assoc_name}报告.md",
    ]
    summary_patterns = [
        f"{assoc_name}_汇总表.md",
        f"{assoc_name}汇总表.md",
    ]
    
    report_file = None
    summary_file = None
    
    for pattern in report_patterns:
        candidate = data_path / pattern
        if candidate.exists():
            report_file = str(candidate)
            break
    
    for pattern in summary_patterns:
        candidate = data_path / pattern
        if candidate.exists():
            summary_file = str(candidate)
            break
    
    return report_file, summary_file


def run_single_check(assoc_name: str, report_file: str, summary_file: str, 
                     output_dir: str, compare_script: str) -> dict:
    """对单个协会运行核对"""
    output_file = Path(output_dir) / f"{assoc_name}_核对结果.md"
    
    cmd = [
        sys.executable, compare_script,
        "--report", report_file,
        "--summary", summary_file,
        "--output", str(output_file),
        "--name", assoc_name,
    ]
    
    result = {
        "name": assoc_name,
        "output": str(output_file),
        "success": False,
        "error": "",
    }
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            result["success"] = True
            # 简单分析结果文件判断是否全部通过
            if output_file.exists():
                content = output_file.read_text(encoding="utf-8")
                result["all_passed"] = "全部核对通过" in content
                result["has_issues"] = "发现" in content and "项问题" in content
        else:
            result["error"] = proc.stderr[:500]
    except subprocess.TimeoutExpired:
        result["error"] = "执行超时（120秒）"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def generate_master_report(
    results: list,
    output_path: str,
    data_dir: str,
    timestamp: str
):
    """生成汇总报告"""
    lines = []
    lines.append("# 审计报告核对汇总结果")
    lines.append("")
    lines.append(f"- **核对时间：** {timestamp}")
    lines.append(f"- **数据目录：** {data_dir}")
    lines.append(f"- **核对协会数：** {len(results)}")
    lines.append("")
    
    # 整体概览
    success_count = sum(1 for r in results if r.get("success"))
    all_passed_count = sum(1 for r in results if r.get("all_passed"))
    has_issues_count = sum(1 for r in results if r.get("has_issues"))
    
    lines.append("## 一、核对范围")
    lines.append("")
    for r in results:
        status = "✅" if r.get("all_passed") else ("⚠️" if r.get("has_issues") else "❌")
        lines.append(f"- {status} {r['name']}")
    lines.append("")
    
    lines.append("## 二、总体统计")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|:----:|")
    lines.append(f"| 核对总数 | {len(results)} |")
    lines.append(f"| 成功完成 | {success_count} |")
    lines.append(f"| 全部通过 | {all_passed_count} |")
    lines.append(f"| 存在问题 | {has_issues_count} |")
    lines.append(f"| 执行失败 | {len(results) - success_count} |")
    lines.append("")
    
    # 各协会详细结果
    lines.append("## 三、各协会核对结果")
    lines.append("")
    
    for r in results:
        if r.get("success"):
            rel_path = Path(r["output"]).name
            lines.append(f"### {r['name']}")
            lines.append("")
            if r.get("all_passed"):
                lines.append("✅ **全部核对通过**")
            else:
                lines.append("⚠️ **存在发现项**")
            lines.append("")
            lines.append(f"详细结果：`{rel_path}`")
            lines.append("")
        else:
            lines.append(f"### {r['name']} ❌")
            lines.append("")
            lines.append(f"执行失败：{r.get('error', '未知错误')}")
            lines.append("")
    
    # 重点关注建议
    lines.append("## 四、重点关注建议")
    lines.append("")
    if has_issues_count > 0:
        lines.append(f"以下 {has_issues_count} 个协会的核对结果存在发现项，建议优先复查：")
        lines.append("")
        for r in results:
            if r.get("has_issues"):
                lines.append(f"- {r['name']} — 见 `{Path(r['output']).name}`")
    else:
        lines.append("本次核对未发现问题。")
    lines.append("")
    
    # 写入
    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"汇总核对结果已写入: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="批量审计报告核对工具")
    parser.add_argument("--data-dir", "-d", required=True, 
                        help="MinerU 提取结果目录")
    parser.add_argument("--output", "-o", default="汇总核对结果.md",
                        help="输出汇总文件路径")
    parser.add_argument("--associations", "-a", 
                        help="协会列表，逗号分隔。不指定则自动发现")
    parser.add_argument("--compare-script", "-c", 
                        default=str(Path(__file__).parent / "compare_data.py"),
                        help="compare_data.py 脚本路径")
    
    args = parser.parse_args()
    data_dir = args.data_dir
    compare_script = args.compare_script
    
    # 发现或获取协会列表
    if args.associations:
        assoc_names = [n.strip() for n in args.associations.split(",")]
    else:
        assoc_names = discover_associations(data_dir)
    
    if not assoc_names:
        print(f"在 {data_dir} 中未找到任何协会数据文件。")
        print("提示：文件应命名为 `协会名_报告.md` 和 `协会名_汇总表.md` 格式。")
        sys.exit(1)
    
    print(f"发现 {len(assoc_names)} 个协会: {', '.join(assoc_names)}")
    
    # 创建输出目录
    output_dir = Path(args.output).parent
    if str(output_dir) != ".":
        output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for assoc_name in assoc_names:
        print(f"\n正在核对: {assoc_name}")
        report_file, summary_file = find_files(args.data_dir, assoc_name)
        
        if not report_file:
            print(f"  警告: 未找到 {assoc_name} 的报告文件，跳过")
            results.append({"name": assoc_name, "success": False, 
                          "error": "报告文件未找到"})
            continue
        
        if not summary_file:
            print(f"  警告: 未找到 {assoc_name} 的汇总表文件，跳过")
            results.append({"name": assoc_name, "success": False,
                          "error": "汇总表文件未找到"})
            continue
        
        result = run_single_check(
            assoc_name, report_file, summary_file,
            str(output_dir), compare_script
        )
        
        if result["success"]:
            print(f"  ✅ 完成: {result['output']}")
        else:
            print(f"  ❌ 失败: {result.get('error', '')}")
        
        results.append(result)
    
    # 生成汇总报告
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generate_master_report(results, args.output, args.data_dir, timestamp)
    
    # 汇总
    success = sum(1 for r in results if r.get("success"))
    print(f"\n{'='*40}")
    print(f"处理完成: {success}/{len(results)} 成功")
    print(f"汇总文件: {args.output}")


if __name__ == "__main__":
    main()
