#!/usr/bin/env python3
"""
Merge Results Script
合并多个样本的注释结果，生成汇总文件
"""

import argparse
import sys
import os
import pandas as pd
from pathlib import Path

# 导入 loguru 和 rich
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box

# 配置 loguru
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
logger.add("merge_results_{time}.log", rotation="10 MB", retention="1 week")

# 创建 rich console
console = Console()


def merge_eggnog_results(input_dir, samples, output_all, output_high, output_stats):
    """合并 eggnog 处理结果"""
    
    all_records = []
    high_conf_records = []
    sample_stats = []
    
    logger.info(f"开始合并 {len(samples)} 个样本的 eggnog 结果...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Merging eggnog results...", total=len(samples))
        
        for sample in samples:
            progress.advance(task)
            
            # 读取完整结果
            all_file = os.path.join(input_dir, f"{sample}_eggnog.tsv")
            high_file = os.path.join(input_dir, f"{sample}_eggnog_highconf.tsv")
            
            if not os.path.exists(all_file):
                logger.warning(f"文件不存在，跳过: {all_file}")
                continue
            
            try:
                # 读取完整结果 (processor 输出的 TSV 可能有注释行)
                df_all = pd.read_csv(all_file, sep='\t', low_memory=False, comment='#')
                df_all['sample'] = sample  # 添加样本列
                all_records.append(df_all)
                
                # 统计
                total_count = len(df_all)
                kegg_count = df_all['kegg_ko'].ne('-').sum() if 'kegg_ko' in df_all.columns else 0
                go_count = df_all['gos'].ne('-').sum() if 'gos' in df_all.columns else 0
                
                # 读取高可信度结果
                high_count = 0
                if os.path.exists(high_file):
                    df_high = pd.read_csv(high_file, sep='\t', low_memory=False)
                    df_high['sample'] = sample
                    high_conf_records.append(df_high)
                    high_count = len(df_high)
                
                sample_stats.append({
                    'sample': sample,
                    'total': total_count,
                    'high_confidence': high_count,
                    'with_kegg': int(kegg_count),
                    'with_go': int(go_count)
                })
                
                logger.info(f"{sample}: 总计={total_count}, 高可信={high_count}, KEGG={int(kegg_count)}, GO={int(go_count)}")
            except Exception as e:
                logger.error(f"处理 {sample} 时出错: {e}")
    
    # 合并所有记录
    if all_records:
        df_merged_all = pd.concat(all_records, ignore_index=True)
        # 调整列顺序，将 sample 列放在第一列
        cols = ['sample'] + [c for c in df_merged_all.columns if c != 'sample']
        df_merged_all = df_merged_all[cols]
        df_merged_all.to_csv(output_all, sep='\t', index=False)
        logger.success(f"所有样本合并结果: {output_all} ({len(df_merged_all)} 条记录)")
    else:
        logger.error("没有找到可合并的数据")
        return
    
    # 合并高可信度记录
    if high_conf_records:
        df_merged_high = pd.concat(high_conf_records, ignore_index=True)
        cols = ['sample'] + [c for c in df_merged_high.columns if c != 'sample']
        df_merged_high = df_merged_high[cols]
        df_merged_high.to_csv(output_high, sep='\t', index=False)
        logger.success(f"高可信度合并结果: {output_high} ({len(df_merged_high)} 条记录)")
    
    # 生成统计报告
    df_stats = pd.DataFrame(sample_stats)
    
    with open(output_stats, 'w') as f:
        f.write("样本详细统计:\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'Sample':<20} {'Total':<10} {'High Conf':<12} {'With KEGG':<12} {'With GO':<10}\n")
        f.write("-" * 70 + "\n")
        
        for stat in sample_stats:
            f.write(f"{stat['sample']:<20} {stat['total']:<10} {stat['high_confidence']:<12} "
                   f"{stat['with_kegg']:<12} {stat['with_go']:<10}\n")
        
        f.write("-" * 70 + "\n")
        f.write(f"{'TOTAL':<20} {df_stats['total'].sum():<10} {df_stats['high_confidence'].sum():<12} "
               f"{df_stats['with_kegg'].sum():<12} {df_stats['with_go'].sum():<10}\n")
        f.write("-" * 70 + "\n")
    
    logger.success(f"统计报告: {output_stats}")
    
    # 使用 rich 打印汇总表格
    console.print("\n")
    table = Table(title="📊 EggNOG Merge Summary", box=box.ROUNDED)
    table.add_column("Sample", style="cyan")
    table.add_column("Total", justify="right", style="green")
    table.add_column("High Conf", justify="right", style="yellow")
    table.add_column("With KEGG", justify="right", style="blue")
    table.add_column("With GO", justify="right", style="magenta")
    
    for stat in sample_stats:
        table.add_row(
            stat['sample'],
            f"{stat['total']:,}",
            f"{stat['high_confidence']:,}",
            f"{stat['with_kegg']:,}",
            f"{stat['with_go']:,}"
        )
    
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{df_stats['total'].sum():,}[/bold]",
        f"[bold]{df_stats['high_confidence'].sum():,}[/bold]",
        f"[bold]{df_stats['with_kegg'].sum():,}[/bold]",
        f"[bold]{df_stats['with_go'].sum():,}[/bold]",
        style="bold green"
    )
    
    console.print(table)


def merge_kofam_results(input_dir, samples, output_all, output_high, output_stats):
    """合并 KofamScan 处理结果"""
    
    all_records = []
    high_conf_records = []
    sample_stats = []
    
    logger.info(f"开始合并 {len(samples)} 个样本的 KofamScan 结果...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Merging KofamScan results...", total=len(samples))
        
        for sample in samples:
            progress.advance(task)
            
            # 读取完整结果
            all_file = os.path.join(input_dir, f"{sample}_kofam.tsv")
            high_file = os.path.join(input_dir, f"{sample}_kofam_highconf.tsv")
            
            if not os.path.exists(all_file):
                logger.warning(f"文件不存在，跳过: {all_file}")
                continue
            
            try:
                # 读取完整结果 (processor 输出的 TSV 可能有注释行)
                df_all = pd.read_csv(all_file, sep='\t', low_memory=False, comment='#')
                df_all['sample'] = sample
                all_records.append(df_all)
                
                total_count = len(df_all)
                
                # 读取高可信度结果
                high_count = 0
                if os.path.exists(high_file):
                    df_high = pd.read_csv(high_file, sep='\t', low_memory=False)
                    df_high['sample'] = sample
                    high_conf_records.append(df_high)
                    high_count = len(df_high)
                
                sample_stats.append({
                    'sample': sample,
                    'total': total_count,
                    'high_confidence': high_count
                })
                
                logger.info(f"{sample}: 总计={total_count}, 高可信={high_count}")
            except Exception as e:
                logger.error(f"处理 {sample} 时出错: {e}")
    
    # 合并所有记录
    if all_records:
        df_merged_all = pd.concat(all_records, ignore_index=True)
        cols = ['sample'] + [c for c in df_merged_all.columns if c != 'sample']
        df_merged_all = df_merged_all[cols]
        df_merged_all.to_csv(output_all, sep='\t', index=False)
        logger.success(f"所有样本合并结果: {output_all} ({len(df_merged_all)} 条记录)")
    else:
        logger.error("没有找到可合并的数据")
        return
    
    # 合并高可信度记录
    if high_conf_records:
        df_merged_high = pd.concat(high_conf_records, ignore_index=True)
        cols = ['sample'] + [c for c in df_merged_high.columns if c != 'sample']
        df_merged_high = df_merged_high[cols]
        df_merged_high.to_csv(output_high, sep='\t', index=False)
        logger.success(f"高可信度合并结果: {output_high} ({len(df_merged_high)} 条记录)")
    
    # 生成统计报告
    df_stats = pd.DataFrame(sample_stats)
    
    with open(output_stats, 'w') as f:
        f.write("样本详细统计:\n")
        f.write("-" * 50 + "\n")
        f.write(f"{'Sample':<20} {'Total':<10} {'High Conf':<12}\n")
        f.write("-" * 50 + "\n")
        
        for stat in sample_stats:
            f.write(f"{stat['sample']:<20} {stat['total']:<10} {stat['high_confidence']:<12}\n")
        
        f.write("-" * 50 + "\n")
        f.write(f"{'TOTAL':<20} {df_stats['total'].sum():<10} {df_stats['high_confidence'].sum():<12}\n")
        f.write("-" * 50 + "\n")
    
    logger.success(f"统计报告: {output_stats}")
    
    # 使用 rich 打印汇总表格
    console.print("\n")
    table = Table(title="📊 KofamScan Merge Summary", box=box.ROUNDED)
    table.add_column("Sample", style="cyan")
    table.add_column("Total", justify="right", style="green")
    table.add_column("High Conf", justify="right", style="yellow")
    
    for stat in sample_stats:
        table.add_row(
            stat['sample'],
            f"{stat['total']:,}",
            f"{stat['high_confidence']:,}"
        )
    
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{df_stats['total'].sum():,}[/bold]",
        f"[bold]{df_stats['high_confidence'].sum():,}[/bold]",
        style="bold green"
    )
    
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description='合并多个样本的注释结果')
    parser.add_argument('--input-dir', required=True, help='输入目录')
    parser.add_argument('--samples', required=True, nargs='+', help='样本列表')
    parser.add_argument('--tool', required=True, choices=['eggnog', 'kofam'], 
                       help='工具类型')
    parser.add_argument('--output-all', required=True, help='所有结果合并输出文件')
    parser.add_argument('--output-high', required=True, help='高可信度结果合并输出文件')
    parser.add_argument('--output-stats', required=True, help='统计信息输出文件')
    
    args = parser.parse_args()
    
    # 启动信息
    console.print(Panel(
        f"[bold cyan]Merge Results[/bold cyan]\n\n"
        f"[green]Tool:[/green] {args.tool}\n"
        f"[green]Samples:[/green] {len(args.samples)}\n"
        f"[green]Input dir:[/green] {args.input_dir}",
        title="🚀 Merge Configuration",
        border_style="cyan"
    ))
    
    if args.tool == 'eggnog':
        merge_eggnog_results(
            args.input_dir,
            args.samples,
            args.output_all,
            args.output_high,
            args.output_stats
        )
    else:
        merge_kofam_results(
            args.input_dir,
            args.samples,
            args.output_all,
            args.output_high,
            args.output_stats
        )
    
    # 输出文件面板
    console.print(Panel(
        f"[green]✓[/green] {args.output_all}\n"
        f"[green]✓[/green] {args.output_high}\n"
        f"[green]✓[/green] {args.output_stats}",
        title="📁 Output Files",
        border_style="green"
    ))
    
    logger.success("合并完成！")


if __name__ == '__main__':
    main()
