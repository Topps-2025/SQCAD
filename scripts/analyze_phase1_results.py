#!/usr/bin/env python3
"""
Phase 1 实验结果分析脚本
分析 L3 鲁棒性和 SimpleMem 结果
"""

import json
import numpy as np
from pathlib import Path
import pandas as pd

def analyze_l3_robustness(results_dir):
    """分析 L3 多参数鲁棒性结果"""

    results = []
    gamma_values = [0.90, 0.95, 0.99]
    harm_values = [15, 20, 25]

    print("=== L3 参数鲁棒性分析 ===\n")

    for gamma in gamma_values:
        for harm in harm_values:
            filepath = results_dir / f"l3_robust_gamma{gamma}_harm{harm}.json"

            if not filepath.exists():
                print(f"⚠️  缺失: gamma={gamma}, harm={harm}")
                continue

            with open(filepath) as f:
                data = json.load(f)

            # 提取关键指标
            sqcad_v2 = data.get('sqcad_v2', {})
            ablation = data.get('ablation', {})

            result = {
                'GAMMA': gamma,
                'HARM_PENALTY': harm,
                'mean_value': sqcad_v2.get('mean_value', np.nan),
                'false_commit': sqcad_v2.get('false_commit', np.nan),
                'oracle_agreement': sqcad_v2.get('oracle_agreement', np.nan),
            }

            # 提取 censoring 效应
            if 'censoring' in ablation:
                cens = ablation['censoring']
                result['censoring_effect'] = cens.get('effect', np.nan)
                result['censoring_CI_lower'] = cens.get('CI', [np.nan, np.nan])[0]
                result['censoring_CI_upper'] = cens.get('CI', [np.nan, np.nan])[1]
                result['censoring_significant'] = cens.get('CI', [0, 0])[0] > 0

            results.append(result)
            print(f"✓ gamma={gamma}, harm={harm}: value={result['mean_value']:.3f}, "
                  f"oracle_agr={result['oracle_agreement']:.3f}")

    # 创建 DataFrame
    df = pd.DataFrame(results)

    # 统计稳定性
    print(f"\n总计: {len(results)}/9 组配置完成")

    if len(results) > 0:
        significant_count = df['censoring_significant'].sum()
        print(f"Censoring 显著: {significant_count}/{len(results)} 组")

        # 汇总表格
        print("\n=== 参数鲁棒性汇总表 ===\n")
        print("| GAMMA | HARM | Mean Value | Oracle Agr | False-Commit | Censoring Sig |")
        print("|-------|------|------------|------------|--------------|---------------|")
        for _, row in df.iterrows():
            sig_mark = "✓" if row['censoring_significant'] else "✗"
            print(f"| {row['GAMMA']:.2f} | {row['HARM_PENALTY']:.0f} | "
                  f"{row['mean_value']:+.3f} | {row['oracle_agreement']:.3f} | "
                  f"{row['false_commit']:.3f} | {sig_mark} |")

        # 生成 LaTeX 表格
        latex_table = generate_latex_robustness_table(df)
        latex_path = results_dir / "l3_robustness_table.tex"
        with open(latex_path, 'w') as f:
            f.write(latex_table)
        print(f"\n✓ LaTeX 表格已保存: {latex_path}")

    return df

def generate_latex_robustness_table(df):
    """生成 LaTeX 表格"""

    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{L3 Parameter Robustness (LifecycleBench, 1,380 episodes)}",
        "\\label{tab:l3_robustness}",
        "\\begin{tabular}{cccccc}",
        "\\toprule",
        "$\\gamma$ & HARM & Mean Value & Oracle Agr & False-Commit & Censoring$^*$ \\\\",
        "\\midrule",
    ]

    for _, row in df.iterrows():
        sig_mark = "$\\checkmark$" if row['censoring_significant'] else ""
        lines.append(
            f"{row['GAMMA']:.2f} & {row['HARM_PENALTY']:.0f} & "
            f"{row['mean_value']:+.3f} & {row['oracle_agreement']:.3f} & "
            f"{row['false_commit']:.3f} & {sig_mark} \\\\"
        )

    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\begin{tablenotes}",
        "\\small",
        "\\item $^*$ Censoring ablation significant (CI lower > 0) at bucket-level unit count (n≈14).",
        "\\end{tablenotes}",
        "\\end{table}",
    ])

    return "\n".join(lines)

def analyze_simplemem(results_dir):
    """分析 SimpleMem n=100 结果"""

    filepath = results_dir / "simplemem_lme_s_n100.json"

    print("\n=== SimpleMem n=100 分析 ===\n")

    if not filepath.exists():
        print(f"⚠️  SimpleMem 结果不存在: {filepath}")
        return None

    with open(filepath) as f:
        data = json.load(f)

    # 提取指标
    metrics = data.get('longmemeval_s', {}).get('simplemem', {})

    hit = metrics.get('hit_rate', [np.nan])[0] if 'hit_rate' in metrics else np.nan
    recall = metrics.get('recall_mean', [np.nan])[0] if 'recall_mean' in metrics else np.nan
    storage = metrics.get('tokens_mean', [np.nan])[0] if 'tokens_mean' in metrics else np.nan

    print(f"Hit Rate:    {hit:.3f}")
    print(f"Recall:      {recall:.3f}")
    print(f"Storage:     {storage:.0f} tokens")

    # 与 SQCAD 比较
    sqcad_hit = 0.754
    sqcad_storage = 1631

    print(f"\n与 SQCAD 对比:")
    print(f"Hit:    SimpleMem {hit:.3f} vs SQCAD {sqcad_hit:.3f} = {hit/sqcad_hit:.2f}×")
    print(f"Storage: SimpleMem {storage:.0f} vs SQCAD {sqcad_storage:.0f} = {storage/sqcad_storage:.2f}×")

    # 判断场景
    if hit > 0.85:
        scenario = "A"
        interpretation = "SimpleMem 在存储更大的情况下实现了更高的覆盖率。两种方法互补：SimpleMem 的压缩机制可以与 SQCAD 的授权机制结合。"
    elif hit >= 0.70:
        scenario = "B"
        interpretation = "SimpleMem 和 SQCAD 在不同存储预算下实现了相似的覆盖率，支持 lifecycle-aware 授权在约束条件下有效保留决策相关证据的主张。"
    else:
        scenario = "C"
        interpretation = "在存储约束下，SQCAD 的 lifecycle-aware 授权比 SimpleMem 的压缩机制保留了更多决策相关证据。"

    print(f"\n场景判断: {scenario}")
    print(f"解读: {interpretation}")

    result = {
        'hit': hit,
        'recall': recall,
        'storage': storage,
        'scenario': scenario,
        'interpretation': interpretation
    }

    return result

def main():
    """主函数"""

    results_dir = Path("C:/Users/Lenovo/Desktop/Paper/SQCAD/results")

    print("SQCAD Phase 1 实验结果分析")
    print("=" * 60)
    print()

    # 分析 L3 鲁棒性
    l3_df = analyze_l3_robustness(results_dir)

    # 分析 SimpleMem
    simplemem_result = analyze_simplemem(results_dir)

    # 保存汇总
    summary = {
        'l3_robustness': l3_df.to_dict('records') if l3_df is not None else [],
        'simplemem': simplemem_result
    }

    summary_path = results_dir / "phase1_analysis_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n✓ 汇总已保存: {summary_path}")
    print("\n分析完成！")

if __name__ == "__main__":
    main()
