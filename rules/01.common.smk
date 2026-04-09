# =============================================================================
# Common Rules and Functions
# =============================================================================
# 通用规则和辅助函数
# =============================================================================

import os
import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# Logger Setup - 智能导入，优先使用自定义插件
# -----------------------------------------------------------------------------

try:
    # 1. 优先尝试导入 Snakemake 自定义插件
    from snakemake_logger_plugin_rich_loguru import get_analysis_logger
    logger = get_analysis_logger()
    logger_type = "rich-loguru"
    
except ImportError:
    try:
        # 2. 回退到标准 loguru
        from loguru import logger
        logger_type = "loguru"
        
    except ImportError:
        # 3. 最后回退到标准 logging
        import logging
        
        class ColoredFormatter(logging.Formatter):
            """自定义彩色日志格式化器"""
            
            COLORS = {
                'DEBUG': '\033[36m',
                'INFO': '\033[32m',
                'WARNING': '\033[33m',
                'ERROR': '\033[31m',
                'CRITICAL': '\033[35m',
                'RESET': '\033[0m'
            }
            
            def format(self, record):
                record.asctime = self.formatTime(record, '%H:%M:%S')
                levelname = record.levelname
                if levelname in self.COLORS:
                    record.colored_levelname = f"{self.COLORS[levelname]}{levelname: <8}{self.COLORS['RESET']}"
                else:
                    record.colored_levelname = f"{levelname: <8}"
                return super().format(record)
        
        # 配置日志处理器
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(colored_levelname)s | %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        logger = logging.getLogger('kegg_annotation')
        logger.setLevel(logging.DEBUG)
        
        if not logger.handlers:
            logger.addHandler(console_handler)
        
        logger_type = "builtin"

# 记录使用的 logger 类型
logger.info(f"Logger initialized: using {logger_type}")

# -----------------------------------------------------------------------------
# 资源管理函数
# -----------------------------------------------------------------------------

def rule_resource(config, resource_type='default', skip_queue_on_local=False, logger=None):
    """
    根据运行环境返回资源配置
    
    从 conf/config.yaml 读取 resource_presets 配置，如果没有则使用默认值
    
    Args:
        config: Snakemake配置字典
        resource_type: 资源类型 (default, high_resource, low_resource)
        skip_queue_on_local: 本地运行时是否跳过队列
        logger: 日志记录器
    
    Returns:
        dict: 资源配置字典
    """
    # 默认资源配置
    default_presets = {
        'default': {
            'mem_gb': 8,
            'runtime': 60,
        },
        'high_resource': {
            'mem_gb': 32,
            'runtime': 240,
        },
        'low_resource': {
            'mem_gb': 4,
            'runtime': 30,
        }
    }
    
    # 从配置中读取 resource_presets
    resource_presets = config.get('resource_presets', default_presets)
    
    # 获取指定类型的资源
    resource = resource_presets.get(resource_type, resource_presets.get('default', default_presets['default'])).copy()
    
    # 检查是否在集群环境运行
    execution_config = config.get('execution', {})
    is_cluster = execution_config.get('environment', 'local') == 'cluster'
    
    if is_cluster:
        resource['queue'] = execution_config.get('queue', 'normal')
    elif skip_queue_on_local:
        pass
    
    if logger:
        logger.debug(f"Resource allocation: {resource_type} -> {resource}")
    
    return resource

# -----------------------------------------------------------------------------
# 路径辅助函数
# -----------------------------------------------------------------------------

def get_log_path(rule_name, wildcards=None, suffix='log'):
    """生成标准化的日志文件路径"""
    if wildcards:
        if hasattr(wildcards, 'sample'):
            return f"logs/{rule_name}_{wildcards.sample}.{suffix}"
        elif hasattr(wildcards, 'comparison'):
            return f"logs/{rule_name}_{wildcards.comparison}.{suffix}"
        elif isinstance(wildcards, dict):
            if 'sample' in wildcards:
                return f"logs/{rule_name}_{wildcards['sample']}.{suffix}"
    return f"logs/{rule_name}.{suffix}"


def get_benchmark_path(rule_name, wildcards=None):
    """生成标准化的benchmark文件路径"""
    if wildcards:
        if hasattr(wildcards, 'sample'):
            return f"benchmarks/{rule_name}_{wildcards.sample}.txt"
        elif hasattr(wildcards, 'comparison'):
            return f"benchmarks/{rule_name}_{wildcards.comparison}.txt"
        elif isinstance(wildcards, dict):
            if 'sample' in wildcards:
                return f"benchmarks/{rule_name}_{wildcards['sample']}.txt"
    return f"benchmarks/{rule_name}.txt"

# -----------------------------------------------------------------------------
# 辅助函数
# -----------------------------------------------------------------------------

def get_input_file(wildcards):
    """获取输入文件路径
    
    支持的输入格式: .pep, .fa, .fasta, .faa, .protein
    以及复合扩展名（如 .fa.TD2.1k.pep）
    按顺序查找，返回第一个存在的文件
    """
    import glob
    extensions = [".pep", ".fa", ".fasta", ".faa", ".protein"]
    base = wildcards.sample
    
    # 1. 先尝试精确匹配常见简单扩展名
    for ext in extensions:
        path = os.path.join(INPUT_DIR, f"{base}{ext}")
        if os.path.exists(path):
            return path
    
    # 2. 再尝试匹配以 sample 开头、以任一允许扩展名结尾的复合扩展名文件
    for ext in extensions:
        pattern = os.path.join(INPUT_DIR, f"{base}*{ext}")
        candidates = glob.glob(pattern)
        if candidates:
            return candidates[0]
    
    # 兜底：返回默认路径（让 Snakemake 后续报错提示）
    return os.path.join(INPUT_DIR, f"{base}.pep")


def get_all_outputs():
    """获取所有输出文件列表 - 按分析步骤分目录"""
    outputs = []
    for sample in SAMPLES:
        # 01.eggnog 注释结果
        outputs.append(f"01.eggnog/{sample}_eggnog.tsv")
        outputs.append(f"01.eggnog/{sample}_eggnog_highconf.tsv")
        
        # 02.kofam 注释结果
        outputs.append(f"02.kofam/{sample}_kofam.tsv")
        outputs.append(f"02.kofam/{sample}_kofam_highconf.tsv")
        
        # 03.merge 整合与汇总结果
        outputs.append(f"03.merge/{sample}_integrated.tsv")
        outputs.append(f"03.merge/{sample}_integrated_report.txt")
        outputs.append(f"03.merge/{sample}_summary.txt")
    
    # 多样本合并结果
    outputs.append("03.merge/eggnog_all_samples.tsv")
    outputs.append("03.merge/eggnog_highconf.tsv")
    outputs.append("03.merge/kofam_all_samples.tsv")
    outputs.append("03.merge/kofam_highconf.tsv")
    outputs.append("03.merge/SUMMARY_REPORT.txt")
    
    # AI 分析结果（如果启用）
    if AI_ENABLED:
        for sample in SAMPLES:
            outputs.append(f"04.ai/{sample}_ai_report.md")
            outputs.append(f"04.ai/{sample}_ai_analysis.json")
        outputs.append("04.ai/AI_MULTI_SAMPLE_SUMMARY.md")
    
    return outputs
