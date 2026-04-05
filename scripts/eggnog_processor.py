#!/usr/bin/env python3

"""
EggNOG-Mapper Annotation Result Processor
处理 emapper.annotations 注释结果，进行质量过滤并输出可信度评估

输入: emapper.annotations 文件
输出: 过滤后的注释结果，包含可信度评估
"""

import argparse
import sys
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path

# 导入 loguru 和 rich
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich import box

# 配置 loguru
logger.remove()  # 移除默认处理器
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
logger.add("eggnog_processor_{time}.log", rotation="10 MB", retention="1 week")

# 创建 rich console
console = Console()


class ConfidenceLevel(Enum):
    """注释结果可信度等级"""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    

@dataclass
class FilterThresholds:
    """过滤阈值配置"""
    evalue: float = 1e-5          # E-value 阈值 (≤)
    bitscore: float = 60          # Bit-score 阈值 (≥)
    pident: float = 40            # Percentage identity 阈值 (≥)
    qcov: float = 20              # Query coverage 阈值 (≥)
    scov: float = 20              # Subject coverage 阈值 (≥)
    
    # 严格模式阈值
    strict_pident: float = 70     # 严格模式下的 Percentage identity
    
    def __str__(self):
        return (
            f"E-value ≤ {self.evalue}\n"
            f"Bit-score ≥ {self.bitscore}\n"
            f"Percentage identity ≥ {self.pident}% (标准) / ≥ {self.strict_pident}% (严格)\n"
            f"Query coverage ≥ {self.qcov}%\n"
            f"Subject coverage ≥ {self.scov}%"
        )


@dataclass
class AnnotationRecord:
    """注释记录数据结构 - 与 KofamScan_processor 格式统一"""
    # 基础比对信息
    query: str = ""
    seed_ortholog: str = ""
    evalue: float = 999.0
    score: float = 0.0
    
    # eggNOG 信息
    eggnog_ogs: str = ""
    max_annot_lvl: str = ""
    cog_category: str = ""
    description: str = ""
    
    # 功能注释
    preferred_name: str = ""
    gos: str = ""
    ec: str = ""
    kegg_ko: str = ""
    kegg_pathway: str = ""
    kegg_module: str = ""
    kegg_reaction: str = ""
    kegg_rclass: str = ""
    brite: str = ""
    kegg_tc: str = ""
    cazy: str = ""
    bigg_reaction: str = ""
    pfams: str = ""
    
    # 可信度评估 - 统一格式
    confidence_level: str = "Low"      # High/Medium/Low
    confidence_score: int = 0          # 0-100
    confidence_reason: str = ""
    
    @classmethod
    def from_line(cls, line: str, header_map: Dict[str, int]) -> 'AnnotationRecord':
        """从TSV行解析记录"""
        cols = line.strip().split('\t')
        
        def get(idx: int) -> str:
            if idx < len(cols):
                val = cols[idx]
                return val if val != '-' else ''
            return ''
        
        def get_float(idx: int, default: float = 0.0) -> float:
            try:
                return float(get(idx)) if get(idx) else default
            except ValueError:
                return default
        
        return cls(
            query=get(header_map.get('query', 0)),
            seed_ortholog=get(header_map.get('seed_ortholog', 1)),
            evalue=get_float(header_map.get('evalue', 2), 999.0),
            score=get_float(header_map.get('score', 3), 0.0),
            eggnog_ogs=get(header_map.get('eggnog_ogs', 4)),
            max_annot_lvl=get(header_map.get('max_annot_lvl', 5)),
            cog_category=get(header_map.get('cog_category', 6)),
            description=get(header_map.get('description', 7)),
            preferred_name=get(header_map.get('preferred_name', 8)),
            gos=get(header_map.get('gos', 9)),
            ec=get(header_map.get('ec', 10)),
            kegg_ko=get(header_map.get('kegg_ko', 11)),
            kegg_pathway=get(header_map.get('kegg_pathway', 12)),
            kegg_module=get(header_map.get('kegg_module', 13)),
            kegg_reaction=get(header_map.get('kegg_reaction', 14)),
            kegg_rclass=get(header_map.get('kegg_rclass', 15)),
            brite=get(header_map.get('brite', 16)),
            kegg_tc=get(header_map.get('kegg_tc', 17)),
            cazy=get(header_map.get('cazy', 18)),
            bigg_reaction=get(header_map.get('bigg_reaction', 19)),
            pfams=get(header_map.get('pfams', 20))
        )
    
    def to_line(self, include_confidence: bool = True) -> str:
        """转换为TSV行 - 统一输出格式"""
        cols = [
            self.query or '-',
            self.seed_ortholog or '-',
            str(self.evalue) if self.evalue < 999 else '-',
            str(self.score) if self.score > 0 else '-',
            self.eggnog_ogs or '-',
            self.max_annot_lvl or '-',
            self.cog_category or '-',
            self.description or '-',
            self.preferred_name or '-',
            self.gos or '-',
            self.ec or '-',
            self.kegg_ko or '-',
            self.kegg_pathway or '-',
            self.kegg_module or '-',
            self.kegg_reaction or '-',
            self.kegg_rclass or '-',
            self.brite or '-',
            self.kegg_tc or '-',
            self.cazy or '-',
            self.bigg_reaction or '-',
            self.pfams or '-',
        ]
        
        if include_confidence:
            cols.extend([
                self.confidence_level,
                str(self.confidence_score),
                self.confidence_reason
            ])
        
        return '\t'.join(cols)
    
    def to_dict(self) -> Dict:
        """转换为字典 - 便于与其他工具集成"""
        return {
            'query': self.query,
            'seed_ortholog': self.seed_ortholog,
            'evalue': self.evalue,
            'score': self.score,
            'eggnog_ogs': self.eggnog_ogs,
            'max_annot_lvl': self.max_annot_lvl,
            'cog_category': self.cog_category,
            'description': self.description,
            'preferred_name': self.preferred_name,
            'gos': self.gos,
            'ec': self.ec,
            'kegg_ko': self.kegg_ko,
            'kegg_pathway': self.kegg_pathway,
            'kegg_module': self.kegg_module,
            'kegg_reaction': self.kegg_reaction,
            'kegg_rclass': self.kegg_rclass,
            'brite': self.brite,
            'kegg_tc': self.kegg_tc,
            'cazy': self.cazy,
            'bigg_reaction': self.bigg_reaction,
            'pfams': self.pfams,
            'confidence_level': self.confidence_level,
            'confidence_score': self.confidence_score,
            'confidence_reason': self.confidence_reason
        }
    
    def has_kegg(self) -> bool:
        """检查是否有 KEGG 注释"""
        return bool(
            self.kegg_ko or 
            self.kegg_pathway or 
            self.kegg_module or
            self.kegg_reaction
        )
    
    def has_go(self) -> bool:
        """检查是否有 GO 注释"""
        return bool(self.gos)
    
    def kegg_summary(self) -> str:
        """KEGG 注释摘要"""
        kos = self.kegg_ko.split(',') if self.kegg_ko else []
        pathways = self.kegg_pathway.split(',') if self.kegg_pathway else []
        modules = self.kegg_module.split(',') if self.kegg_module else []
        
        parts = []
        if kos:
            parts.append(f"KO:{len(kos)}")
        if pathways:
            parts.append(f"Pathway:{len(pathways)}")
        if modules:
            parts.append(f"Module:{len(modules)}")
        
        return '; '.join(parts) if parts else '-'
    
    def go_summary(self) -> str:
        """GO 注释摘要"""
        if not self.gos:
            return '-'
        
        gos = self.gos.split(',')
        return f"GO:{len(gos)}"


def parse_header(line: str) -> Dict[str, int]:
    """解析文件头，获取列名到索引的映射"""
    cols = line.strip().split('\t')
    
    # 标准 eggnog-mapper 输出列名
    standard_headers = [
        'query', 'seed_ortholog', 'evalue', 'score', 'eggnog_ogs',
        'max_annot_lvl', 'cog_category', 'description', 'preferred_name',
        'gos', 'ec', 'kegg_ko', 'kegg_pathway', 'kegg_module',
        'kegg_reaction', 'kegg_rclass', 'brite', 'kegg_tc', 'cazy',
        'bigg_reaction', 'pfams'
    ]
    
    header_map = {}
    for i, col in enumerate(cols):
        col_lower = col.lower().replace(' ', '_')
        # 尝试匹配标准列名
        for std in standard_headers:
            if std in col_lower or col_lower in std:
                header_map[std] = i
                break
        else:
            header_map[col_lower] = i
    
    # 确保必需的列有默认值
    for i, std in enumerate(standard_headers):
        if std not in header_map:
            header_map[std] = i
    
    return header_map


def calculate_confidence_score(
    record: AnnotationRecord, 
    thresholds: FilterThresholds,
    strict_mode: bool = False
) -> Tuple[str, int, str]:
    """
    计算可信度评分 (与 KofamScan_processor 风格统一)
    
    返回: (confidence_level, confidence_score, reason)
    """
    score = 0
    reasons = []
    
    # E-value 评分 (0-40分)
    if record.evalue <= 1e-20:
        score += 40
        reasons.append("E-value excellent")
    elif record.evalue <= 1e-10:
        score += 35
        reasons.append("E-value very good")
    elif record.evalue <= 1e-5:
        score += 30
        reasons.append("E-value good")
    elif record.evalue <= 0.001:
        score += 20
        reasons.append("E-value moderate")
    elif record.evalue <= 0.01:
        score += 10
        reasons.append("E-value marginal")
    else:
        reasons.append(f"E-value poor ({record.evalue:.2e})")
    
    # Bit-score 评分 (0-30分)
    if record.score >= 200:
        score += 30
        reasons.append("Score excellent")
    elif record.score >= 100:
        score += 25
        reasons.append("Score very good")
    elif record.score >= thresholds.bitscore:
        score += 20
        reasons.append("Score good")
    elif record.score >= 40:
        score += 10
        reasons.append("Score moderate")
    else:
        reasons.append(f"Score low ({record.score:.1f})")
    
    # 注释完整性评分 (0-30分)
    annotation_count = sum([
        bool(record.gos),
        bool(record.kegg_ko),
        bool(record.ec),
        bool(record.pfams),
        bool(record.cazy)
    ])
    
    if annotation_count >= 4:
        score += 30
        reasons.append("Annotations rich")
    elif annotation_count >= 3:
        score += 25
        reasons.append("Annotations comprehensive")
    elif annotation_count >= 2:
        score += 20
        reasons.append("Annotations good")
    elif annotation_count >= 1:
        score += 10
        reasons.append("Annotations limited")
    else:
        reasons.append("No functional annotations")
    
    # 确定可信度等级
    if score >= 80:
        level = "High"
    elif score >= 50:
        level = "Medium"
    else:
        level = "Low"
    
    # 生成简洁的原因说明
    if level == "High":
        reason_summary = "High quality annotation"
    elif level == "Medium":
        reason_summary = "Moderate quality annotation"
    else:
        # 低可信度时，说明具体问题
        problems = [r for r in reasons if "poor" in r or "low" in r or "No" in r or "limited" in r or "marginal" in r]
        reason_summary = "; ".join(problems) if problems else "Low quality annotation"
    
    return level, score, reason_summary


def filter_record(
    record: AnnotationRecord, 
    thresholds: FilterThresholds,
    require_kegg: bool = False,
    require_go: bool = False,
    min_confidence: str = "Low"
) -> bool:
    """
    根据阈值过滤记录
    
    返回 True 表示保留该记录
    """
    # 最低可信度检查
    conf_rank = {'High': 3, 'Medium': 2, 'Low': 1}
    if conf_rank.get(record.confidence_level, 0) < conf_rank.get(min_confidence, 1):
        return False
    
    # E-value 过滤 (越小越好)
    if record.evalue > thresholds.evalue:
        return False
    
    # Bit-score 过滤 (越大越好)
    if record.score < thresholds.bitscore:
        return False
    
    # KEGG 注释要求
    if require_kegg and not record.has_kegg():
        return False
    
    # GO 注释要求
    if require_go and not record.has_go():
        return False
    
    return True


def process_annotations(
    input_file: str,
    output_file: str,
    thresholds: FilterThresholds,
    require_kegg: bool = False,
    require_go: bool = False,
    strict_mode: bool = False,
    keep_all: bool = False,
    min_confidence: str = "Low"
) -> Dict:
    """
    处理注释文件
    
    参数:
        input_file: 输入的 emapper.annotations 文件
        output_file: 输出文件路径
        thresholds: 过滤阈值
        require_kegg: 是否要求有 KEGG 注释
        require_go: 是否要求有 GO 注释
        strict_mode: 是否使用严格模式
        keep_all: 是否保留所有记录（不过滤，只添加可信度评估）
        min_confidence: 最低可信度阈值
    
    返回:
        统计信息字典
    """
    stats = {
        'total': 0,
        'passed': 0,
        'filtered': 0,
        'high_confidence': 0,
        'medium_confidence': 0,
        'low_confidence': 0,
        'with_kegg': 0,
        'with_go': 0,
        'with_both': 0
    }
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # 处理文件头
    header_line = None
    header_map = {}
    data_start = 0
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # 跳过注释行
        if line_stripped.startswith('#') or line_stripped.startswith('##'):
            continue
        
        # 第一个非注释行是文件头
        if not header_line:
            header_line = line_stripped
            header_map = parse_header(header_line)
            data_start = i + 1
            break
    
    # 处理数据行 - 使用 rich 进度条
    records = []
    data_lines = lines[data_start:]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Processing annotations...", total=len(data_lines))
        
        for line in data_lines:
            line_stripped = line.strip()
            progress.advance(task)
            
            # 跳过空行和注释行
            if not line_stripped or line_stripped.startswith('#'):
                continue
            
            # 跳过统计信息行
            if line_stripped.startswith('---') or 'queries scanned' in line_stripped:
                continue
            
            stats['total'] += 1
            
            try:
                record = AnnotationRecord.from_line(line_stripped, header_map)
            except Exception as e:
                logger.warning(f"解析行失败，跳过: {line_stripped[:50]}... ({e})")
                continue
            
            # 计算可信度
            record.confidence_level, record.confidence_score, record.confidence_reason = calculate_confidence_score(
                record, thresholds, strict_mode
            )
            
            # 统计
            if record.has_kegg():
                stats['with_kegg'] += 1
            if record.has_go():
                stats['with_go'] += 1
            if record.has_kegg() and record.has_go():
                stats['with_both'] += 1
            
            if record.confidence_level == "High":
                stats['high_confidence'] += 1
            elif record.confidence_level == "Medium":
                stats['medium_confidence'] += 1
            else:
                stats['low_confidence'] += 1
            
            # 过滤
            if keep_all or filter_record(record, thresholds, require_kegg, require_go, min_confidence):
                records.append(record)
                stats['passed'] += 1
            else:
                stats['filtered'] += 1
    
    # 写入输出文件
    output_lines = []
    
    # 文件头注释
    output_lines.append("# EggNOG-Mapper Annotation Results with Confidence Assessment")
    output_lines.append("#")
    output_lines.append("# Filter Thresholds:")
    output_lines.append(f"#   E-value ≤ {thresholds.evalue}")
    output_lines.append(f"#   Bit-score ≥ {thresholds.bitscore}")
    output_lines.append(f"#   Mode: {'Strict' if strict_mode else 'Standard'}")
    output_lines.append(f"#   Min confidence: {min_confidence}")
    if require_kegg:
        output_lines.append("#   Require KEGG: Yes")
    if require_go:
        output_lines.append("#   Require GO: Yes")
    output_lines.append("#")
    output_lines.append("# Confidence Assessment:")
    output_lines.append("#   High (80-100): Excellent E-value, high score, rich annotations")
    output_lines.append("#   Medium (50-79): Good quality, passes thresholds")
    output_lines.append("#   Low (0-49): Marginal quality or lacks annotation support")
    output_lines.append("#")
    
    # 列头 - 统一格式
    base_headers = [
        'query', 'seed_ortholog', 'evalue', 'score', 'eggnog_ogs',
        'max_annot_lvl', 'cog_category', 'description', 'preferred_name',
        'gos', 'ec', 'kegg_ko', 'kegg_pathway', 'kegg_module',
        'kegg_reaction', 'kegg_rclass', 'brite', 'kegg_tc', 'cazy',
        'bigg_reaction', 'pfams', 'confidence_level', 'confidence_score', 
        'confidence_reason'
    ]
    output_lines.append('\t'.join(base_headers))
    
    # 数据行
    for record in records:
        output_lines.append(record.to_line(include_confidence=True))
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(output_lines) + '\n')
    
    return stats, records


def print_summary_report(stats: Dict, output_file: str):
    """打印摘要报告 - 使用 rich 美化"""
    # 创建主表格
    table = Table(title="📊 EggNOG Annotation Processing Report", box=box.ROUNDED)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")
    table.add_column("Percentage", justify="right", style="yellow")
    
    total = max(stats['total'], 1)
    
    table.add_row("Total records", f"{stats['total']:,}", "100.0%")
    table.add_row("Passed filter", f"{stats['passed']:,}", f"{stats['passed']/total*100:.1f}%")
    table.add_row("Filtered out", f"{stats['filtered']:,}", f"{stats['filtered']/total*100:.1f}%")
    
    console.print(table)
    
    # 可信度分布表格
    conf_table = Table(title="🎯 Confidence Distribution", box=box.ROUNDED)
    conf_table.add_column("Level", style="cyan")
    conf_table.add_column("Count", justify="right", style="green")
    conf_table.add_column("Percentage", justify="right", style="yellow")
    
    conf_table.add_row("⭐ High", f"{stats['high_confidence']:,}", f"{stats['high_confidence']/total*100:.1f}%", style="green")
    conf_table.add_row("🔶 Medium", f"{stats['medium_confidence']:,}", f"{stats['medium_confidence']/total*100:.1f}%", style="yellow")
    conf_table.add_row("🔻 Low", f"{stats['low_confidence']:,}", f"{stats['low_confidence']/total*100:.1f}%", style="red")
    
    console.print(conf_table)
    
    # 注释覆盖表格
    annot_table = Table(title="📝 Annotation Coverage", box=box.ROUNDED)
    annot_table.add_column("Type", style="cyan")
    annot_table.add_column("Count", justify="right", style="green")
    annot_table.add_column("Percentage", justify="right", style="yellow")
    
    annot_table.add_row("🧬 With KEGG", f"{stats['with_kegg']:,}", f"{stats['with_kegg']/total*100:.1f}%")
    annot_table.add_row("🔬 With GO", f"{stats['with_go']:,}", f"{stats['with_go']/total*100:.1f}%")
    annot_table.add_row("🧬+🔬 With Both", f"{stats['with_both']:,}", f"{stats['with_both']/total*100:.1f}%")
    
    console.print(annot_table)
    
    # 输出文件信息
    console.print(Panel(
        f"[green]Output file:[/green] {output_file}\n"
        f"[blue]Total records saved:[/blue] {stats['passed']:,}",
        title="💾 Output",
        border_style="green"
    ))


def write_report_file(stats: Dict, output_prefix: str, thresholds: FilterThresholds, 
                      args, passed_records: List[AnnotationRecord]):
    """写入详细报告文件"""
    report_file = f"{output_prefix}_report.txt"
    
    with open(report_file, 'w') as f:
        f.write("EggNOG Annotation Processing Report\n")
        f.write("="*70 + "\n\n")
        
        f.write("Parameters:\n")
        f.write(f"  E-value threshold: {thresholds.evalue}\n")
        f.write(f"  Bit-score threshold: {thresholds.bitscore}\n")
        f.write(f"  Mode: {'Strict' if args.strict else 'Standard'}\n")
        f.write(f"  Min confidence: {args.min_confidence}\n")
        if args.require_kegg:
            f.write("  Require KEGG: Yes\n")
        if args.require_go:
            f.write("  Require GO: Yes\n")
        f.write("\n")
        
        f.write("Statistics:\n")
        f.write(f"  Total records: {stats['total']}\n")
        f.write(f"  Passed filter: {stats['passed']}\n")
        f.write(f"  Filtered out: {stats['filtered']}\n\n")
        
        f.write("Confidence Distribution:\n")
        f.write(f"  High: {stats['high_confidence']}\n")
        f.write(f"  Medium: {stats['medium_confidence']}\n")
        f.write(f"  Low: {stats['low_confidence']}\n\n")
        
        f.write("Annotation Coverage:\n")
        f.write(f"  With KEGG: {stats['with_kegg']}\n")
        f.write(f"  With GO: {stats['with_go']}\n")
        f.write(f"  With both KEGG and GO: {stats['with_both']}\n\n")
        
        f.write("Confidence Assessment Criteria:\n")
        f.write("  Score components (max 100):\n")
        f.write("    - E-value: 0-40 points\n")
        f.write("    - Bit-score: 0-30 points\n")
        f.write("    - Annotation richness: 0-30 points\n")
        f.write("  Level thresholds:\n")
        f.write("    - High: 80-100 points\n")
        f.write("    - Medium: 50-79 points\n")
        f.write("    - Low: 0-49 points\n")
    
    return report_file


def main():
    parser = argparse.ArgumentParser(
        description='Process EggNOG-Mapper annotation results with quality filtering and confidence assessment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 标准过滤 (默认)
  python eggnog_processor.py -i input.emapper.annotations -o output
  
  # 严格模式
  python eggnog_processor.py -i input.emapper.annotations -o output --strict
  
  # 只保留 High 可信度的结果
  python eggnog_processor.py -i input.emapper.annotations -o output --min-confidence High
  
  # 只保留有 KEGG 注释的结果
  python eggnog_processor.py -i input.emapper.annotations -o output --require-kegg
  
  # 保留所有记录，只添加可信度评估
  python eggnog_processor.py -i input.emapper.annotations -o output --keep-all
  
  # 自定义阈值
  python eggnog_processor.py -i input.emapper.annotations -o output \\
      --evalue 1e-10 --bitscore 80
        """
    )
    
    parser.add_argument('-i', '--input', required=True,
                        help='输入的 emapper.annotations 文件路径')
    parser.add_argument('-o', '--output', required=True,
                        help='输出文件前缀')
    
    # 过滤参数
    filter_group = parser.add_argument_group('过滤阈值参数')
    filter_group.add_argument('--evalue', type=float, default=1e-5,
                              help='E-value 阈值 (默认: 1e-5)')
    filter_group.add_argument('--bitscore', type=float, default=60,
                              help='Bit-score 阈值 (默认: 60)')
    filter_group.add_argument('--pident', type=float, default=40,
                              help='Percentage identity 阈值 (默认: 40)')
    filter_group.add_argument('--qcov', type=float, default=20,
                              help='Query coverage 阈值 (默认: 20)')
    filter_group.add_argument('--scov', type=float, default=20,
                              help='Subject coverage 阈值 (默认: 20)')
    
    # 模式参数
    mode_group = parser.add_argument_group('运行模式')
    mode_group.add_argument('--strict', action='store_true',
                            help='严格模式 (使用更严格的质量标准评估可信度)')
    mode_group.add_argument('--require-kegg', action='store_true',
                            help='只保留有 KEGG 注释的记录')
    mode_group.add_argument('--require-go', action='store_true',
                            help='只保留有 GO 注释的记录')
    mode_group.add_argument('--keep-all', action='store_true',
                            help='保留所有记录，不过滤，只添加可信度评估')
    mode_group.add_argument('--min-confidence', default='Low', 
                           choices=['High', 'Medium', 'Low'],
                           help='最低可信度阈值 (默认: Low，保留所有)')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)
    
    # 创建阈值配置
    thresholds = FilterThresholds(
        evalue=args.evalue,
        bitscore=args.bitscore,
        pident=args.pident,
        qcov=args.qcov,
        scov=args.scov
    )
    
    # 使用 rich 打印启动信息
    console.print(Panel(
        f"[bold cyan]EggNOG Annotation Processing[/bold cyan]\n\n"
        f"[green]Input:[/green] {args.input}\n"
        f"[green]Output prefix:[/green] {args.output}\n"
        f"[green]Thresholds:[/green] E-value ≤ {thresholds.evalue}, Bit-score ≥ {thresholds.bitscore}\n"
        f"[green]Mode:[/green] {'Strict' if args.strict else 'Standard'}\n"
        f"[green]Min confidence:[/green] {args.min_confidence}",
        title="🚀 Processing Configuration",
        border_style="cyan"
    ))
    
    logger.info("开始处理注释文件...")
    
    # 处理文件
    output_file = f"{args.output}_formatted.tsv"
    stats, records = process_annotations(
        input_file=args.input,
        output_file=output_file,
        thresholds=thresholds,
        require_kegg=args.require_kegg,
        require_go=args.require_go,
        strict_mode=args.strict,
        keep_all=args.keep_all,
        min_confidence=args.min_confidence
    )
    
    logger.success(f"处理完成: {stats['total']} 条记录, {stats['passed']} 条通过过滤")
    
    # 打印报告
    print_summary_report(stats, output_file)
    
    # 写入详细报告
    report_file = write_report_file(stats, args.output, thresholds, args, records)
    console.print(f"[blue]📄 详细报告:[/blue] {report_file}")
    
    # 生成高质量子集
    if stats['high_confidence'] > 0:
        high_conf_file = f"{args.output}_high_confidence.tsv"
        high_conf_records = [r for r in records if r.confidence_level == "High"]
        
        with open(high_conf_file, 'w') as f:
            # 列头
            base_headers = [
                'query', 'seed_ortholog', 'evalue', 'score', 'eggnog_ogs',
                'max_annot_lvl', 'cog_category', 'description', 'preferred_name',
                'gos', 'ec', 'kegg_ko', 'kegg_pathway', 'kegg_module',
                'kegg_reaction', 'kegg_rclass', 'brite', 'kegg_tc', 'cazy',
                'bigg_reaction', 'pfams', 'confidence_level', 'confidence_score', 
                'confidence_reason'
            ]
            f.write('\t'.join(base_headers) + '\n')
            
            for record in high_conf_records:
                f.write(record.to_line(include_confidence=True) + '\n')
        
        console.print(f"[green]⭐ 高置信度子集:[/green] {high_conf_file} ({len(high_conf_records)} 条)")
        logger.info(f"高置信度子集已生成: {high_conf_file}")


if __name__ == '__main__':
    main()
