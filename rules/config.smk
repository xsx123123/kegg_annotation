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
# 过滤阈值配置
# -----------------------------------------------------------------------------
EVALUE_THRESHOLD = config.get("evalue_threshold", 1e-5)
BITSCORE_THRESHOLD = config.get("bitscore_threshold", 60)
MIN_CONFIDENCE = config.get("min_confidence", "High")
REQUIRE_KEGG = config.get("require_kegg", True)
REQUIRE_GO = config.get("require_go", False)
