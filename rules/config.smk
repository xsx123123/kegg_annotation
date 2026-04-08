#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# Global Configuration - 全局配置变量定义文件
# =============================================================================

import os  # 导入 os 模块，用于路径操作
#
# 【文件作用】
# 这个文件是 KEGG 注释流程的"配置转换中心"。它将用户在 conf/config.yaml 中
# 定义的小写配置项，转换为全大写的全局变量，供所有规则文件使用。
#
# 【为什么要这样设计？】
# 1. 默认值机制：如果用户没有在 config.yaml 中设置某项，这里提供默认值
# 2. 代码简洁：规则文件中直接使用 SAMPLES 而不是 config.get("samples")
# 3. 统一维护：所有配置的默认值集中在一个地方，方便修改
# 4. 可读性：全大写表示"这是全局配置常量，不应在运行时修改"
#
# 【如何使用？】
# 1. 如需修改默认值：直接修改本文件中 = 右侧的值
# 2. 如需添加新配置：按照相同模式添加，记得在 conf/config.yaml 中也添加说明
# 3. 在规则文件中使用：直接使用大写变量名，如 expand("...", sample=SAMPLES)
#
# 【注意事项】
# - 这个文件在 snakefile 中通过 include: "rules/config.smk" 加载
# - 变量名必须全大写（约定俗成）
# - 不要在规则文件中修改这些变量（它们是常量）
#
# =============================================================================


# =============================================================================
# 第一部分：样本配置 (Sample Configuration)
# =============================================================================
# 这些变量定义了要分析的样本、输入文件位置和输出结果位置

# SAMPLES: 要分析的样本名称列表
# - 对应 conf/config.yaml 中的 samples:
# - 默认值: ["test_sample_100"]（单个测试样本）
# - 使用场景: expand() 函数中为每个样本生成任务
# - 示例: expand("{sample}/eggnog/...", sample=SAMPLES)
SAMPLES = config.get("samples", ["test_sample_100"])

# INPUT_DIR: 输入序列文件所在的目录
# - 对应 conf/config.yaml 中的 input_dir
# - 默认值: "test"（当前目录下的 test 文件夹）
# - 注意: 支持相对路径（相对于 workdir）或绝对路径
INPUT_DIR = config.get("input_dir", "test")

# OUTPUT_DIR: 分析结果输出目录
# - 对应 conf/config.yaml 中的 output_dir
# - 默认值: "results"
# - 说明: 所有样本的分析结果都会放在这个目录下
OUTPUT_DIR = config.get("output_dir", "results")


# =============================================================================
# 第二部分：Conda 环境配置 (Conda Environment)
# =============================================================================
# 这些变量定义了各个分析步骤使用的 Conda 环境文件路径
# 使用 Conda 可以自动安装和管理软件依赖，保证可重复性

# ENV_DIR: Conda 环境配置文件的根目录
# - 默认值: "env"
# - 说明: 所有 .yaml 环境文件都放在这个目录下
ENV_DIR = config.get("env_dir", "env")

# EGGNOG_ENV: eggnog-mapper 分析的 Conda 环境
# - 默认值: "env/eggnog-mapper.yaml"
# - 说明: 包含 eggnog-mapper 2.1.13 及其依赖
# - 注意: 使用 f-string 引用 ENV_DIR，保持路径一致性
EGGNOG_ENV = config.get("eggnog_env", f"{ENV_DIR}/eggnog-mapper.yaml")

# KOFAM_ENV: KofamScan 分析的 Conda 环境
# - 默认值: "env/kofamscan.yaml"
# - 说明: 包含 KofamScan 1.3.0、HMMER 等
KOFAM_ENV = config.get("kofam_env", f"{ENV_DIR}/kofamscan.yaml")


# =============================================================================
# 第三部分：数据库路径配置 (Database Paths)
# =============================================================================
# 这些变量定义了功能注释数据库的位置
# 首次使用前需要下载这些数据（详见 README）

# EGGNOG_DATA_DIR: eggnog-mapper 数据库目录
# - 对应 conf/config.yaml 中的 eggnog_data_dir
# - 默认值: "dataset/eggnog-mapper"
# - 说明: 需要包含 eggnog.db、eggnog_proteins.dmnd 等文件
# - 下载: 运行 download_eggnog_data.py 或手动下载
EGGNOG_DATA_DIR = config.get("eggnog_data_dir", "dataset/eggnog-mapper")

# KOFAM_KO_LIST: KofamScan 的 KO 列表文件
# - 对应 conf/config.yaml 中的 kofam_ko_list
# - 默认值: "dataset/kegg_2026-02-01_ko_dataset/ko_list"
# - 说明: 包含所有 KO 条目的阈值信息
KOFAM_KO_LIST = config.get("kofam_ko_list", "dataset/kegg_2026-02-01_ko_dataset/ko_list")

# KOFAM_PROFILES: KofamScan 的 HMM 配置文件目录
# - 对应 conf/config.yaml 中的 kofam_profiles
# - 默认值: "dataset/kegg_2026-02-01_ko_dataset/profiles"
# - 说明: 包含所有 KO 的 HMM 模型文件 (*.hmm)
KOFAM_PROFILES = config.get("kofam_profiles", "dataset/kegg_2026-02-01_ko_dataset/profiles")


# =============================================================================
# 第四部分：计算资源配置 (Resource Configuration)
# =============================================================================
# 这些变量定义了各分析步骤使用的 CPU 线程数
# 可根据机器配置调整

# EGGNOG_CPU: eggnog-mapper 使用的线程数
# - 对应 conf/config.yaml 中的 eggnog_cpu
# - 默认值: 8
# - 建议: 根据 CPU 核心数设置，通常设置为物理核心数
# - 注意: eggnog-mapper 是计算密集型，更多线程 = 更快，但内存消耗也大
EGGNOG_CPU = config.get("eggnog_cpu", 8)

# KOFAM_CPU: KofamScan 使用的线程数
# - 对应 conf/config.yaml 中的 kofam_cpu
# - 默认值: 8
# - 说明: KofamScan 使用 HMMER 进行搜索，支持多线程
KOFAM_CPU = config.get("kofam_cpu", 8)


# =============================================================================
# 第五部分：脚本路径配置 (Script Paths)
# =============================================================================
# 这些变量定义了 Python 处理脚本的绝对路径
# 使用辅助函数 _resolve_script_path 确保路径正确解析

# _scripts: 临时变量，获取 config 中的 scripts 字典
_scripts = config.get("scripts", {})


def _resolve_script_path(script_path):
    """
    将脚本路径解析为绝对路径
    
    这个辅助函数确保无论用户如何设置工作目录，脚本路径都能正确找到。
    
    参数:
        script_path: 配置文件中的脚本路径（相对或绝对）
    
    返回:
        绝对路径字符串
    
    逻辑:
        1. 如果路径为空，返回 None
        2. 如果已经是绝对路径（以 / 开头），直接返回
        3. 如果是相对路径，基于 snakefile 所在目录（workflow.basedir）拼接
    
    示例:
        "scripts/eggnog_processor.py" → "/path/to/pipeline/scripts/eggnog_processor.py"
    """
    if not script_path:
        return None
    if os.path.isabs(script_path):
        return script_path
    # 相对于工作目录（snakefile 所在目录）
    return os.path.join(workflow.basedir, script_path)


# EGGNOG_PROCESSOR: eggnog 结果处理脚本
# - 对应 conf/config.yaml 中的 scripts.eggnog_processor
# - 默认值: "scripts/eggnog_processor.py"
# - 作用: 对 eggnog-mapper 输出进行质量过滤和可信度评分
EGGNOG_PROCESSOR = _resolve_script_path(_scripts.get("eggnog_processor", "scripts/eggnog_processor.py"))

# KOFAMSCAN_PROCESSOR: KofamScan 结果处理脚本
# - 对应 conf/config.yaml 中的 scripts.KofamScan_processor
# - 默认值: "scripts/KofamScan_processor.py"
# - 作用: 解析 KofamScan detail 输出，评估可信度
KOFAMSCAN_PROCESSOR = _resolve_script_path(_scripts.get("KofamScan_processor", "scripts/KofamScan_processor.py"))

# MERGE_RESULTS: 结果合并脚本
# - 对应 conf/config.yaml 中的 scripts.merge_results
# - 默认值: "scripts/merge_results.py"
# - 作用: 合并多个样本的注释结果
MERGE_RESULTS = _resolve_script_path(_scripts.get("merge_results", "scripts/merge_results.py"))

# AI_CURATOR: AI 分析脚本（可选功能）
# - 对应 conf/config.yaml 中的 scripts.ai_curator
# - 默认值: "scripts/ai_curator.py"
# - 作用: 使用 AI 模型对注释结果进行智能解读
# - 注意: 仅当 ai.enabled=true 时才会被调用
AI_CURATOR = _resolve_script_path(_scripts.get("ai_curator", "scripts/ai_curator.py"))


# =============================================================================
# 第六部分：AI 分析配置 (AI Configuration)
# =============================================================================
# 这些变量控制可选的 AI 分析功能
# 需要配置 API 密钥或本地 Ollama 服务

# AI_CONFIG: AI 配置的原始字典（供其他模块使用）
# - 包含 provider, model, api_key, api_base 等
AI_CONFIG = config.get("ai", {})

# AI_ENABLED: 是否启用 AI 分析
# - 对应 conf/config.yaml 中的 ai.enabled
# - 默认值: False
# - 说明: 只有当设为 true 时，ai_curator.smk 规则才会被加载
AI_ENABLED = AI_CONFIG.get("enabled", False)


# =============================================================================
# 第七部分：过滤阈值配置 (Filter Thresholds)
# =============================================================================
# 这些变量定义了注释结果的质量过滤标准
# 调整这些值可以控制输出结果的严格程度

# EVALUE_THRESHOLD: E-value 阈值
# - 对应 conf/config.yaml 中的 evalue_threshold
# - 默认值: 1e-5 (0.00001)
# - 说明: 只保留 E-value ≤ 此值的注释
# - 建议: 更严格用 1e-10，更宽松用 1e-3
# - 科普: E-value 越小，序列相似性越显著，假阳性率越低
EVALUE_THRESHOLD = config.get("evalue_threshold", 1e-5)

# BITSCORE_THRESHOLD: Bit-score 阈值
# - 对应 conf/config.yaml 中的 bitscore_threshold
# - 默认值: 60
# - 说明: 只保留 Bit-score ≥ 此值的注释
# - 建议: 更严格用 80-100，更宽松用 40
# - 科普: Bit-score 衡量序列比对质量，分数越高越可靠
BITSCORE_THRESHOLD = config.get("bitscore_threshold", 60)

# MIN_CONFIDENCE: 最低可信度等级
# - 对应 conf/config.yaml 中的 min_confidence
# - 默认值: "High"
# - 可选值: "High"（高）、"Medium"（中）、"Low"（低）
# - 说明: 只保留可信度 ≥ 此等级的结果
# - 注意: 这是处理器脚本的参数，不是 eggnog-mapper 本身的过滤
MIN_CONFIDENCE = config.get("min_confidence", "High")

# REQUIRE_KEGG: 是否要求必须有 KEGG 注释
# - 对应 conf/config.yaml 中的 require_kegg
# - 默认值: True
# - 说明: 设为 True 时，过滤掉没有 KO 编号的基因
# - 用途: 如果下游分析依赖 KEGG 通路，建议设为 True
REQUIRE_KEGG = config.get("require_kegg", True)

# REQUIRE_GO: 是否要求必须有 GO 注释
# - 对应 conf/config.yaml 中的 require_go
# - 默认值: False
# - 说明: 设为 True 时，过滤掉没有 GO 条目的基因
# - 用途: 如果需要进行 GO 富集分析，设为 True
REQUIRE_GO = config.get("require_go", False)


# =============================================================================
# 使用示例 (Usage Examples)
# =============================================================================
#
# 【在规则文件中使用这些变量】
#
# 1. 为每个样本生成输入文件路径:
#    expand("{sample}/eggnog/{sample}.emapper.annotations", sample=SAMPLES)
#
# 2. 设置规则使用的线程数:
#    threads: EGGNOG_CPU
#
# 3. 在 shell 命令中调用处理脚本:
#    python3 "{EGGNOG_PROCESSOR}" -i {input} -o {output}
#
# 4. 根据 AI 是否启用加载不同规则:
#    if AI_ENABLED:
#        include: "rules/ai_curator.smk"
#
# 5. 使用过滤阈值作为参数:
#    params:
#        evalue = EVALUE_THRESHOLD,
#        min_conf = MIN_CONFIDENCE
#
# =============================================================================
