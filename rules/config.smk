# =============================================================================
# Global Configuration
# =============================================================================
# 全局配置定义
# 通过 conf/config.yaml 或 --config 参数覆盖默认值
# =============================================================================

# -----------------------------------------------------------------------------
# 样本配置
# -----------------------------------------------------------------------------
SAMPLES = config.get("samples", ["test_sample_100"])
INPUT_DIR = config.get("input_dir", "test")
OUTPUT_DIR = config.get("output_dir", "results")

# -----------------------------------------------------------------------------
# Conda 环境配置
# -----------------------------------------------------------------------------
ENV_DIR = config.get("env_dir", "env")
EGGNOG_ENV = config.get("eggnog_env", f"{ENV_DIR}/eggnog-mapper.yaml")
KOFAM_ENV = config.get("kofam_env", f"{ENV_DIR}/kofamscan.yaml")

# -----------------------------------------------------------------------------
# eggnog-mapper 配置
# -----------------------------------------------------------------------------
EGGNOG_DATA_DIR = config.get("eggnog_data_dir", "dataset/eggnog-mapper")
EGGNOG_CPU = config.get("eggnog_cpu", 8)

# -----------------------------------------------------------------------------
# KofamScan 配置
# -----------------------------------------------------------------------------
KOFAM_KO_LIST = config.get("kofam_ko_list", "dataset/kegg_2026-02-01_ko_dataset/ko_list")
KOFAM_PROFILES = config.get("kofam_profiles", "dataset/kegg_2026-02-01_ko_dataset/profiles")
KOFAM_CPU = config.get("kofam_cpu", 8)

# -----------------------------------------------------------------------------
# 脚本路径配置
# -----------------------------------------------------------------------------
# 使用 workflow.source_path 将相对路径转换为绝对路径
# 注意：这里假设 config 中的路径是相对于 pipeline 根目录的
_scripts = config.get("scripts", {})

# 辅助函数：解析脚本路径
def _resolve_script_path(script_path):
    """将脚本路径解析为绝对路径"""
    if not script_path:
        return None
    if os.path.isabs(script_path):
        return script_path
    # 相对于工作目录（snakefile 所在目录）
    return os.path.join(workflow.basedir, script_path)

EGGNOG_PROCESSOR = _resolve_script_path(_scripts.get("eggnog_processor", "scripts/eggnog_processor.py"))
KOFAMSCAN_PROCESSOR = _resolve_script_path(_scripts.get("KofamScan_processor", "scripts/KofamScan_processor.py"))
MERGE_RESULTS = _resolve_script_path(_scripts.get("merge_results", "scripts/merge_results.py"))

# -----------------------------------------------------------------------------
# 过滤阈值配置
# -----------------------------------------------------------------------------
EVALUE_THRESHOLD = config.get("evalue_threshold", 1e-5)
BITSCORE_THRESHOLD = config.get("bitscore_threshold", 60)
MIN_CONFIDENCE = config.get("min_confidence", "High")
REQUIRE_KEGG = config.get("require_kegg", True)
REQUIRE_GO = config.get("require_go", False)
