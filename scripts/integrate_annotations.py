#!/usr/bin/env python3
"""
Integrate eggnog and KofamScan annotation results with scoring system.
对 eggnog 和 KofamScan 注释结果进行整合，并给出综合评分。
"""

import argparse
import sys
import os
import re
from pathlib import Path
from collections import Counter

try:
    import pandas as pd
except ImportError:
    print("Error: pandas is required. Install with: conda install pandas")
    sys.exit(1)

try:
    from loguru import logger
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    logger.remove()
    console = Console()
    HAS_RICH = True
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
    logger = logging.getLogger(__name__)
    HAS_RICH = False


def read_tsv(path):
    """读取 TSV，处理可能的注释行"""
    if not path or not Path(path).exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, sep='\t', low_memory=False, comment='#')
    except pd.errors.ParserError:
        df = pd.read_csv(path, sep='\t', low_memory=False, comment='#', on_bad_lines='skip')
    if len(df) == 0:
        return df
    # 清理列名
    df.columns = [str(c).lstrip('#').strip().lower() for c in df.columns]
    return df


def parse_confidence_score(val):
    """解析 confidence_score 为数值"""
    if pd.isna(val):
        return 0.0
    s = str(val)
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if m:
        return float(m.group(1))
    return 0.0


def normalize_ko(val):
    """标准化 KO 编号，如 K00001"""
    if pd.isna(val):
        return ''
    s = str(val).strip()
    # 提取 K+数字
    kos = re.findall(r'K\d+', s)
    if kos:
        return kos[0]
    return s if s != '-' and s.lower() != 'nan' else ''


def compute_integrated_score(row):
    """
    计算综合评分 (0-100)
    规则：
    - 一致性：双一致 +30，单源 +10，冲突 0
    - 可信度：eggnog score 0-40，kofam score 0-30
    - 注释丰富度：有 KO +10，有 EC +5，有 GO +5，有 Pathway/Module +5
    """
    score = 0.0

    # 1. 一致性评分 (max 30)
    agreement = row.get('ko_agreement', 'none')
    if agreement == 'agree':
        score += 30
    elif agreement == 'single_source':
        score += 10
    # conflict -> 0

    # 2. 工具可信度评分
    eggnog_conf = parse_confidence_score(row.get('eggnog_confidence_score', 0))
    kofam_conf = parse_confidence_score(row.get('kofam_confidence_score', 0))
    # eggnog confidence_score 一般是 0-100，映射到 0-40
    score += min(eggnog_conf / 100.0 * 40, 40)
    # kofam confidence_score 也映射到 0-30
    score += min(kofam_conf / 100.0 * 30, 30)

    # 3. 注释丰富度 (max 25)
    integrated_ko = str(row.get('integrated_ko', ''))
    if integrated_ko:
        score += 10
    if str(row.get('best_ec', '')):
        score += 5
    if row.get('has_go', False):
        score += 5
    if row.get('has_pathway', False):
        score += 5

    return round(min(score, 100), 1)


def integrate_sample(eggnog_df, kofam_df):
    """整合单个样本的 eggnog 和 kofam 结果"""
    records = []

    all_queries = set()
    if not eggnog_df.empty:
        all_queries.update(eggnog_df['query'].astype(str).tolist())
    if not kofam_df.empty:
        all_queries.update(kofam_df['query'].astype(str).tolist())

    # 预处理：建立 query -> row 的映射
    eggnog_map = {}
    if not eggnog_df.empty:
        for _, r in eggnog_df.iterrows():
            eggnog_map[str(r['query'])] = r

    kofam_map = {}
    if not kofam_df.empty:
        for _, r in kofam_df.iterrows():
            kofam_map[str(r['query'])] = r

    for q in sorted(all_queries):
        ed = eggnog_map.get(q)
        kd = kofam_map.get(q)

        row = {'query': q}

        # eggnog 字段
        if ed is not None:
            row['eggnog_seed_ortholog'] = str(ed.get('seed_ortholog', ''))
            row['eggnog_evalue'] = str(ed.get('evalue', ''))
            row['eggnog_score'] = str(ed.get('score', ''))
            row['eggnog_kegg_ko'] = normalize_ko(ed.get('kegg_ko', ''))
            row['eggnog_confidence_level'] = str(ed.get('confidence_level', ''))
            row['eggnog_confidence_score'] = str(ed.get('confidence_score', ''))
            row['eggnog_description'] = str(ed.get('description', ''))
            row['eggnog_ec'] = str(ed.get('ec', ''))
            row['eggnog_go'] = str(ed.get('gos', ''))
            row['eggnog_pathway'] = str(ed.get('kegg_pathway', ''))
        else:
            row['eggnog_seed_ortholog'] = ''
            row['eggnog_evalue'] = ''
            row['eggnog_score'] = ''
            row['eggnog_kegg_ko'] = ''
            row['eggnog_confidence_level'] = ''
            row['eggnog_confidence_score'] = ''
            row['eggnog_description'] = ''
            row['eggnog_ec'] = ''
            row['eggnog_go'] = ''
            row['eggnog_pathway'] = ''

        # kofam 字段
        if kd is not None:
            row['kofam_ko'] = normalize_ko(kd.get('ko', kd.get('seed_ortholog', '')))
            row['kofam_evalue'] = str(kd.get('evalue', ''))
            row['kofam_score'] = str(kd.get('score', ''))
            row['kofam_confidence_level'] = str(kd.get('confidence_level', ''))
            row['kofam_confidence_score'] = str(kd.get('confidence_score', ''))
            row['kofam_description'] = str(kd.get('description', kd.get('definition', '')))
            row['kofam_ec'] = str(kd.get('ec', kd.get('ec', '')))
            row['kofam_pass_threshold'] = str(kd.get('pass_threshold', ''))
        else:
            row['kofam_ko'] = ''
            row['kofam_evalue'] = ''
            row['kofam_score'] = ''
            row['kofam_confidence_level'] = ''
            row['kofam_confidence_score'] = ''
            row['kofam_description'] = ''
            row['kofam_ec'] = ''
            row['kofam_pass_threshold'] = ''

        # 判定 KO 一致性
        e_ko = row['eggnog_kegg_ko']
        k_ko = row['kofam_ko']
        if e_ko and k_ko:
            if e_ko == k_ko:
                row['ko_agreement'] = 'agree'
                row['integrated_ko'] = e_ko
            else:
                row['ko_agreement'] = 'conflict'
                # 冲突时优先选通过 Kofam 阈值且 score 更高的
                try:
                    k_score = float(row['kofam_score']) if row['kofam_score'] else 0
                    e_score = float(row['eggnog_score']) if row['eggnog_score'] else 0
                except ValueError:
                    k_score = e_score = 0
                if row['kofam_pass_threshold'].lower() in ('true', '1', 'yes') and k_score >= e_score:
                    row['integrated_ko'] = k_ko
                else:
                    row['integrated_ko'] = e_ko
        elif e_ko:
            row['ko_agreement'] = 'single_source'
            row['integrated_ko'] = e_ko
        elif k_ko:
            row['ko_agreement'] = 'single_source'
            row['integrated_ko'] = k_ko
        else:
            row['ko_agreement'] = 'none'
            row['integrated_ko'] = ''

        # 最佳描述和 EC
        descs = [d for d in (row['eggnog_description'], row['kofam_description']) if d and d.lower() != 'nan' and d != '-']
        row['best_description'] = descs[0] if descs else ''
        ecs = [e for e in (row['eggnog_ec'], row['kofam_ec']) if e and e.lower() != 'nan' and e != '-']
        row['best_ec'] = ecs[0] if ecs else ''

        # GO / Pathway 标志
        row['has_go'] = bool(row['eggnog_go']) and row['eggnog_go'] != '-' and row['eggnog_go'].lower() != 'nan'
        row['has_pathway'] = bool(row['eggnog_pathway']) and row['eggnog_pathway'] != '-' and row['eggnog_pathway'].lower() != 'nan'

        # 综合评分
        row['integrated_score'] = compute_integrated_score(row)
        s = row['integrated_score']
        if s >= 75:
            row['integrated_level'] = 'High'
        elif s >= 45:
            row['integrated_level'] = 'Medium'
        else:
            row['integrated_level'] = 'Low'

        records.append(row)

    out_df = pd.DataFrame(records)
    # 调整列顺序
    col_order = [
        'query',
        'integrated_ko', 'ko_agreement', 'integrated_score', 'integrated_level',
        'best_description', 'best_ec', 'has_go', 'has_pathway',
        'eggnog_seed_ortholog', 'eggnog_evalue', 'eggnog_score', 'eggnog_kegg_ko',
        'eggnog_confidence_level', 'eggnog_confidence_score',
        'kofam_ko', 'kofam_evalue', 'kofam_score',
        'kofam_confidence_level', 'kofam_confidence_score', 'kofam_pass_threshold'
    ]
    # 只保留存在的列
    col_order = [c for c in col_order if c in out_df.columns]
    out_df = out_df[col_order]
    return out_df


def generate_report(df, sample_name, output_report):
    """生成整合报告"""
    total = len(df)
    high = len(df[df['integrated_level'] == 'High'])
    medium = len(df[df['integrated_level'] == 'Medium'])
    low = len(df[df['integrated_level'] == 'Low'])
    agree = len(df[df['ko_agreement'] == 'agree'])
    conflict = len(df[df['ko_agreement'] == 'conflict'])
    single = len(df[df['ko_agreement'] == 'single_source'])
    none_ = len(df[df['ko_agreement'] == 'none'])
    with_ko = len(df[df['integrated_ko'].ne('')])
    with_go = df['has_go'].sum()
    with_pathway = df['has_pathway'].sum()
    avg_score = df['integrated_score'].mean() if total else 0

    lines = [
        "=" * 70,
        f"Integrated Annotation Report for {sample_name}",
        "=" * 70,
        f"Total genes: {total}",
        f"With integrated KO: {with_ko} ({with_ko/total*100:.1f}%)",
        f"With GO terms: {with_go} ({with_go/total*100:.1f}%)",
        f"With KEGG Pathway: {with_pathway} ({with_pathway/total*100:.1f}%)",
        "",
        "Integrated Confidence Distribution:",
        f"  High:   {high} ({high/total*100:.1f}%)",
        f"  Medium: {medium} ({medium/total*100:.1f}%)",
        f"  Low:    {low} ({low/total*100:.1f}%)",
        f"  Average integrated score: {avg_score:.1f}",
        "",
        "Cross-tool Agreement:",
        f"  Agree:         {agree} ({agree/total*100:.1f}%)",
        f"  Conflict:      {conflict} ({conflict/total*100:.1f}%)",
        f"  Single source: {single} ({single/total*100:.1f}%)",
        f"  No annotation: {none_} ({none_/total*100:.1f}%)",
        "",
        "Scoring Criteria (max 100):",
        "  - Cross-tool agreement: 0-30 points",
        "  - Confidence (eggnog 0-40 + kofam 0-30): 0-70 points",
        "  - Annotation richness (KO/EC/GO/Pathway): 0-25 points",
        "  - High:   >= 75",
        "  - Medium: 45-74",
        "  - Low:    < 45",
        "=" * 70,
    ]

    with open(output_report, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    logger.info(f"整合报告已生成: {output_report}")


def main():
    parser = argparse.ArgumentParser(
        description='Integrate eggnog and KofamScan annotations with scoring system'
    )
    parser.add_argument('-e', '--eggnog', required=True, help='eggnog 结果 TSV')
    parser.add_argument('-k', '--kofam', required=True, help='KofamScan 结果 TSV')
    parser.add_argument('-s', '--sample', required=True, help='样本名称')
    parser.add_argument('-o', '--output', required=True, help='输出前缀')
    args = parser.parse_args()

    logger.info(f"读取 eggnog: {args.eggnog}")
    eggnog_df = read_tsv(args.eggnog)
    logger.info(f"读取 kofam: {args.kofam}")
    kofam_df = read_tsv(args.kofam)

    logger.info(f"eggnog rows: {len(eggnog_df)}, kofam rows: {len(kofam_df)}")

    logger.info("整合注释结果...")
    integrated_df = integrate_sample(eggnog_df, kofam_df)

    output_tsv = f"{args.output}_integrated.tsv"
    output_report = f"{args.output}_integrated_report.txt"

    integrated_df.to_csv(output_tsv, sep='\t', index=False)
    logger.success(f"整合结果已保存: {output_tsv} ({len(integrated_df)} 条)")

    generate_report(integrated_df, args.sample, output_report)


if __name__ == '__main__':
    main()
