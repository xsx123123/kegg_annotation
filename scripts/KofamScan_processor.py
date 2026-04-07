#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KofamScan Processor
将 KofamScan detail 输出转换为 eggNOG-mapper 风格，并评估可信度
"""

import pandas as pd
import re
import argparse
from pathlib import Path

# 导入 loguru 和 rich
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
import sys

# 配置 loguru
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
logger.add("kofamscan_processor_{time}.log", rotation="10 MB", retention="1 week")

# 创建 rich console
console = Console()


def parse_kofam_detail(file_path):
    """解析 KofamScan detail 格式"""
    records = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Parsing KofamScan detail...", total=len(lines))
        
        for line in lines:
            line = line.rstrip('\n')
            progress.advance(task)
            
            # 跳过注释行和空行
            if not line or line.startswith('#'):
                continue
            
            # 检查星号标记（通过阈值）
            is_significant = line.startswith('*')
            content = line[1:] if is_significant else line
            
            # 解析列（固定宽度或空格分隔）
            # 格式：gene_name KO thrshld score E-value definition
            parts = re.split(r'\s+', content.strip(), maxsplit=5)
            
            if len(parts) < 5:
                continue
            
            gene = parts[0]
            ko = parts[1]
            threshold_str = parts[2]
            score = float(parts[3])
            evalue_str = parts[4]
            definition = parts[5] if len(parts) > 5 else ''
            
            # 处理阈值
            threshold = float(threshold_str) if threshold_str != '-' else None
            
            # 处理 E-value（转换为数值）
            evalue = parse_evalue(evalue_str)
            
            # 提取 EC 号
            ec_match = re.search(r'\[EC:([^\]]+)\]', definition)
            ec = ec_match.group(1) if ec_match else '-'
            
            # 清理 definition（移除 EC 部分）
            clean_def = re.sub(r'\s*\[EC:[^\]]+\]', '', definition).strip()
            
            records.append({
                'query': gene,
                'KO': ko,
                'threshold': threshold,
                'score': score,
                'evalue': evalue,
                'evalue_str': evalue_str,
                'definition': clean_def,
                'EC': ec,
                'is_significant': is_significant,
                'pass_threshold': is_significant  # 有星号 = 通过阈值
            })
    
    return pd.DataFrame(records)


def parse_evalue(ev_str):
    """将科学计数法字符串转换为浮点数"""
    try:
        return float(ev_str)
    except ValueError:
        # 处理 3.4e-34 格式
        if 'e' in ev_str.lower():
            return float(ev_str.replace('e', 'E'))
        return 999.0


def calculate_confidence(row, all_hits_for_gene):
    """
    三级可信度评估体系
    返回: (confidence_level, confidence_score, reason)
    """
    score = row['score']
    threshold = row['threshold']
    evalue = row['evalue']
    is_sig = row['is_significant']
    ko = row['KO']
    
    # 统计该基因的所有 hits
    gene_hits = all_hits_for_gene.get(row['query'], [])
    total_hits = len(gene_hits)
    
    # 1. 高置信 (High Confidence)
    # 标准：通过阈值（有星号）且 score >= threshold
    if is_sig and threshold and score >= threshold:
        # 如果只有一个显著 hit，置信度更高
        sig_hits = [h for h in gene_hits if h['is_significant']]
        if len(sig_hits) == 1:
            return 'High', 95, 'Pass threshold, unique significant hit'
        else:
            return 'High', 90, 'Pass threshold, multiple significant hits'
    
    # 2. 中置信 (Medium Confidence)
    # 标准：未通过阈值但 score 很高（>100）或 evalue 极显著（<1e-20）
    if score > 100 or evalue < 1e-20:
        # 检查是否是最佳 hit（与其他 hits 的 score 差异）
        if total_hits > 1:
            max_score = max(h['score'] for h in gene_hits)
            score_gap = max_score - score
            if score_gap < 5:  # 与最佳 hit 差距很小
                return 'Medium', 75, 'High score but close to other hits (ambiguous)'
        
        return 'Medium', 80, 'High score but marginally below threshold'
    
    # 3. 低置信 (Low Confidence)
    # 标准：score < 60 或 evalue > 1e-5 或与其他 hits score 接近
    if score < 60 or evalue > 1e-5:
        return 'Low', 40, 'Low score or high e-value'
    
    # 检查是否有多个 hits 的 score 非常接近（<10% 差异）
    if total_hits > 1:
        scores = sorted([h['score'] for h in gene_hits], reverse=True)
        if len(scores) >= 2:
            top1, top2 = scores[0], scores[1]
            if (top1 - top2) / top1 < 0.1:  # 差异 <10%
                return 'Low', 50, 'Multiple hits with similar scores (ambiguous family)'
    
    # 默认中低置信
    return 'Medium', 60, 'Moderate evidence, no clear threshold pass'


def select_best_ko_with_confidence(df):
    """为每个基因选择最佳 KO，并计算可信度"""
    
    # 按基因分组
    grouped = df.groupby('query')
    
    results = []
    all_hits_dict = {name: group.to_dict('records') for name, group in grouped}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Calculating confidence scores...", total=len(grouped))
        
        for gene_id, group in grouped:
            progress.advance(task)
            
            # 排序：先按 is_significant 降序，再按 score 降序
            sorted_hits = group.sort_values(['is_significant', 'score'], ascending=[False, False])
            
            # 选择最佳 hit（第一行）
            best = sorted_hits.iloc[0].copy()
            
            # 计算可信度
            conf_level, conf_score, reason = calculate_confidence(best, all_hits_dict)
            
            best['confidence_level'] = conf_level
            best['confidence_score'] = conf_score
            best['confidence_reason'] = reason
            best['total_hits'] = len(group)
            best['significant_hits'] = group['is_significant'].sum()
            
            results.append(best)
    
    return pd.DataFrame(results)


def create_eggnog_style_output(df):
    """创建类似 eggNOG annotations 的格式"""
    
    # 重命名和选择列，匹配 eggNOG 风格
    output = pd.DataFrame({
        'query': df['query'],
        'seed_ortholog': df['KO'],  # 对应 eggNOG 的 seed_ortholog 列，这里放 KO
        'evalue': df['evalue'],
        'score': df['score'],
        'KO': df['KO'],
        'Description': df['definition'],
        'EC': df['EC'],
        'confidence_level': df['confidence_level'],
        'confidence_score': df['confidence_score'],
        'confidence_reason': df['confidence_reason'],
        'kofam_threshold': df['threshold'],
        'pass_threshold': df['is_significant'],
        'total_hits': df['total_hits'],
        'significant_hits': df['significant_hits']
    })
    
    return output


def generate_conflict_summary(df, eggnog_file=None):
    """生成冲突和统计摘要"""
    
    summary = {
        'total_genes': len(df),
        'high_conf': len(df[df['confidence_level'] == 'High']),
        'medium_conf': len(df[df['confidence_level'] == 'Medium']),
        'low_conf': len(df[df['confidence_level'] == 'Low']),
        'pass_threshold': df['is_significant'].sum(),
        'multi_hits': len(df[df['total_hits'] > 1])
    }
    
    # 如果提供 eggnog 文件，进行对比
    if eggnog_file and Path(eggnog_file).exists():
        logger.info(f"与 eggNOG 结果进行对比: {eggnog_file}")
        try:
            # eggnog 文件有 4 行注释，第 5 行是列名（以 # 开头）
            eggnog = pd.read_csv(eggnog_file, sep='\t', skiprows=4, comment='#')
            # 如果没有正确读取列名，尝试重新读取
            if eggnog.empty or 'query' not in eggnog.columns.str.lstrip('#').tolist():
                eggnog = pd.read_csv(eggnog_file, sep='\t', skiprows=3)
                # 去除列名的 # 前缀
                eggnog.columns = [col.lstrip('#') for col in eggnog.columns]
            comparison = compare_with_eggnog(df, eggnog)
            summary['comparison'] = comparison
        except Exception as e:
            logger.warning(f"读取 eggnog 文件失败: {e}")
    
    return summary


def compare_with_eggnog(kofam_df, eggnog_df):
    """与 eggNOG 结果对比"""
    # 标准化列名（去除可能的 # 前缀，统一大小写）
    eggnog_df = eggnog_df.rename(columns=lambda x: x.lstrip('#').lower())
    
    # 检查必需的列是否存在
    if 'query' not in eggnog_df.columns:
        logger.warning("eggnog 文件中缺少 'query' 列，跳过对比")
        return {
            'stats': {'error': 'Missing query column in eggnog'},
            'conflict_df': pd.DataFrame(),
            'merged_df': pd.DataFrame()
        }
    
    # 查找 KEGG_ko 列（可能是 'kegg_ko' 或其他变体）
    kegg_col = None
    for col in eggnog_df.columns:
        if 'kegg' in col and 'ko' in col:
            kegg_col = col
            break
    
    if not kegg_col:
        logger.warning("eggnog 文件中未找到 KEGG KO 列，跳过对比")
        return {
            'stats': {'error': 'Missing KEGG_ko column in eggnog'},
            'conflict_df': pd.DataFrame(),
            'merged_df': pd.DataFrame()
        }
    
    eggnog_subset = eggnog_df[['query', kegg_col]].copy()
    eggnog_subset['KEGG_ko_clean'] = eggnog_subset[kegg_col].str.replace('ko:', '', na='')
    
    # 合并
    merged = pd.merge(
        kofam_df[['query', 'KO', 'confidence_level']],
        eggnog_subset,
        on='query',
        how='outer'
    )
    
    # 分类
    def classify(row):
        kofam = str(row['KO']) if pd.notna(row['KO']) else '-'
        eggnog = str(row['KEGG_ko_clean']) if pd.notna(row['KEGG_ko_clean']) else '-'
        
        if kofam == '-' and eggnog == '-':
            return 'unassigned_both'
        elif kofam == eggnog:
            return 'consistent'
        elif kofam != '-' and eggnog == '-':
            return 'kofam_only'
        elif kofam == '-' and eggnog != '-':
            return 'eggnog_only'
        else:
            return 'conflict'
    
    merged['comparison'] = merged.apply(classify, axis=1)
    
    stats = merged['comparison'].value_counts().to_dict()
    
    # 提取冲突用于 AI 仲裁
    conflicts = merged[merged['comparison'] == 'conflict']
    
    return {
        'stats': stats,
        'conflict_df': conflicts,
        'merged_df': merged
    }


def print_summary(summary, output_file, high_conf_file, report_file, multi_file=None):
    """使用 rich 打印摘要报告"""
    
    # 主统计表
    table = Table(title="📊 KofamScan Processing Summary", box=box.ROUNDED)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")
    
    table.add_row("Total genes", f"{summary['total_genes']:,}")
    table.add_row("Pass threshold", f"{summary['pass_threshold']:,}")
    table.add_row("Multi-hit genes", f"{summary['multi_hits']:,}")
    
    console.print(table)
    
    # 可信度分布
    conf_table = Table(title="🎯 Confidence Distribution", box=box.ROUNDED)
    conf_table.add_column("Level", style="cyan")
    conf_table.add_column("Count", justify="right", style="green")
    conf_table.add_column("Percentage", justify="right", style="yellow")
    
    total = summary['total_genes']
    conf_table.add_row(
        "⭐ High", 
        f"{summary['high_conf']:,}", 
        f"{summary['high_conf']/total*100:.1f}%",
        style="green"
    )
    conf_table.add_row(
        "🔶 Medium", 
        f"{summary['medium_conf']:,}", 
        f"{summary['medium_conf']/total*100:.1f}%",
        style="yellow"
    )
    conf_table.add_row(
        "🔻 Low", 
        f"{summary['low_conf']:,}", 
        f"{summary['low_conf']/total*100:.1f}%",
        style="red"
    )
    
    console.print(conf_table)
    
    # 输出文件列表
    files_panel = Panel(
        f"[green]✓[/green] {output_file} (完整结果)\n"
        f"[green]✓[/green] {high_conf_file} (高置信度)\n" +
        (f"[green]✓[/green] {multi_file} (多匹配基因)\n" if multi_file else "") +
        f"[green]✓[/green] {report_file} (处理报告)",
        title="📁 Output Files",
        border_style="green"
    )
    console.print(files_panel)
    
    # 对比统计（如果有）
    if 'comparison' in summary:
        comp = summary['comparison']
        if 'stats' in comp:
            comp_table = Table(title="🔄 Comparison with EggNOG", box=box.ROUNDED)
            comp_table.add_column("Category", style="cyan")
            comp_table.add_column("Count", justify="right", style="green")
            
            for k, v in comp['stats'].items():
                emoji = "✅" if k == "consistent" else "🔶" if k == "kofam_only" else "⚠️" if k == "conflict" else "📋"
                comp_table.add_row(f"{emoji} {k}", str(v))
            
            console.print(comp_table)
            
            if len(comp.get('conflict_df', [])) > 0:
                console.print(f"[yellow]⚠️ 发现 {len(comp['conflict_df'])} 条冲突，已保存到冲突文件[/yellow]")


def main():
    parser = argparse.ArgumentParser(
        description='将 KofamScan 结果转换为 eggNOG 风格并评估可信度'
    )
    parser.add_argument('-i', '--input', required=True, help='KofamScan detail 输出文件')
    parser.add_argument('-o', '--output', required=True, help='输出文件前缀')
    parser.add_argument('-e', '--eggnog', help='可选：eggNOG annotations 文件进行对比')
    parser.add_argument('--min-confidence', default='Low', 
                       choices=['High', 'Medium', 'Low'],
                       help='最低可信度阈值 (默认: Low，保留所有)')
    
    args = parser.parse_args()
    
    # 启动信息
    console.print(Panel(
        f"[bold cyan]KofamScan Result Processing[/bold cyan]\n\n"
        f"[green]Input:[/green] {args.input}\n"
        f"[green]Output:[/green] {args.output}",
        title="🚀 Starting Processing",
        border_style="cyan"
    ))
    
    logger.info("开始解析 KofamScan 输出...")
    
    # 1. 解析输入
    df = parse_kofam_detail(args.input)
    logger.success(f"解析完成: {len(df)} 条比对记录, {df['query'].nunique()} 个基因")
    logger.info(f"通过阈值 (带*): {df['is_significant'].sum()}")
    
    # 2. 选择最佳 KO 并评估可信度
    logger.info("选择最佳 KO 并评估可信度...")
    best_df = select_best_ko_with_confidence(df)
    logger.success("可信度评估完成")
    
    # 3. 生成 eggNOG 风格输出
    logger.info("生成标准化输出...")
    eggnog_style = create_eggnog_style_output(best_df)
    
    # 过滤最低可信度
    conf_rank = {'High': 3, 'Medium': 2, 'Low': 1}
    min_rank = conf_rank[args.min_confidence]
    filtered = best_df[best_df['confidence_level'].apply(lambda x: conf_rank[x] >= min_rank)]
    
    # 保存主结果
    output_file = f"{args.output}.tsv"
    eggnog_style.to_csv(output_file, sep='\t', index=False)
    logger.success(f"主结果已保存: {output_file} ({len(eggnog_style)} 条)")
    
    # 保存高质量子集
    hq_file = f"{args.output}_highconf.tsv"
    high_conf_df = eggnog_style[eggnog_style['confidence_level'] == 'High']
    high_conf_df.to_csv(hq_file, sep='\t', index=False)
    logger.success(f"高置信子集已保存: {hq_file} ({len(high_conf_df)} 条)")
    
    # 4. 多匹配基因报告（潜在的旁系同源/基因家族）
    multi_file = None
    multi_hit_df = best_df[best_df['total_hits'] > 1].copy()
    if len(multi_hit_df) > 0:
        multi_file = f"{args.output}_multi_KO_genes.tsv"
        multi_hit_df.to_csv(multi_file, sep='\t', index=False)
        logger.info(f"多匹配基因报告: {multi_file} ({len(multi_hit_df)} 个基因)")
    
    # 5. 与 eggNOG 对比（如果提供）
    summary = generate_conflict_summary(best_df, args.eggnog)
    
    # 6. 生成报告
    report_file = f"{args.output}_report.txt"
    with open(report_file, 'w') as f:
        f.write(f"KofamScan 处理报告\n")
        f.write(f"{'='*70}\n\n")
        f.write(f"输入文件: {args.input}\n")
        f.write(f"总基因数: {best_df['query'].nunique()}\n")
        f.write(f"通过阈值: {best_df['is_significant'].sum()}\n")
        f.write(f"多匹配基因: {(best_df['total_hits'] > 1).sum()}\n\n")
        
        f.write(f"可信度分布:\n")
        for level in ['High', 'Medium', 'Low']:
            count = (best_df['confidence_level'] == level).sum()
            f.write(f"  {level}: {count}\n")
        
        f.write(f"\n可信度评估标准:\n")
        f.write(f"  High: 通过 KofamScan 自适应阈值 (score >= threshold)\n")
        f.write(f"  Medium: 未通过阈值但 score>100 或 evalue<1e-20，或接近阈值\n")
        f.write(f"  Low: score<60 或 evalue>1e-5，或多个 hits score 接近\n")
    
    # 打印摘要
    print_summary(summary, output_file, hq_file, report_file, multi_file)
    logger.success("处理完成！")


if __name__ == '__main__':
    main()
