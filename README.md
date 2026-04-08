# KEGG Annotation Pipeline

基于 eggnog-mapper 和 KofamScan 的基因功能注释流程，提供质量过滤和可信度评估。

## 项目特点

- ✅ **模块化设计**: 使用 Snakemake 管理分析流程，支持灵活配置
- ✅ **质量过滤**: 基于 E-value、Bit-score 等多维度过滤
- ✅ **可信度评估**: 三级可信度分级 (High/Medium/Low)，0-100分评分体系
- ✅ **结果合并**: 支持多样本结果合并，便于下游分析
- ✅ **Conda 环境**: 自动管理依赖环境，保证可重复性
- ✅ **AI 驱动分析**: 支持 AI 注释质量评估和功能解读（Ollama/OpenAI/Claude）

---

## 目录结构

```
.
├── snakefile                 # 主工作流文件
├── config.yaml              # 示例配置文件（详细说明）
├── conf/
│   └── config.yaml          # 生产配置文件（实际使用）
├── rules/                   # Snakemake 规则目录
│   ├── config.smk          # 全局配置
│   ├── common.smk          # 通用规则
│   ├── eggnog.smk          # eggnog 分析规则
│   ├── kofamscan.smk       # KofamScan 分析规则
│   ├── report.smk          # 报告生成规则
│   └── merge.smk           # 结果合并规则
├── env/                     # Conda 环境配置
│   ├── eggnog-mapper.yaml
│   └── kofamscan.yaml
├── scripts/                 # Python 处理脚本
│   ├── eggnog_processor.py
│   ├── KofamScan_processor.py
│   └── merge_results.py
├── dataset/                 # 数据库目录
│   ├── eggnog-mapper/      # eggnog 数据库
│   └── kegg_*_ko_dataset/  # KofamScan 数据库
└── test/                    # 测试数据
    └── test_sample_100.pep
```

---

## 快速开始

### 1. 环境准备

确保已安装 [Snakemake](https://snakemake.readthedocs.io/) 和 [Conda](https://docs.conda.io/) (推荐 Miniconda):

```bash
# 安装 Snakemake
conda install -n base -c conda-forge -c bioconda snakemake
```

### 2. 配置文件设置

```bash
# 复制示例配置文件到生产配置
cp config.yaml conf/config.yaml

# 编辑生产配置
vim conf/config.yaml
```

### 3. 运行分析

```bash
# 运行完整流程（会自动创建 conda 环境）
snakemake --use-conda --cores 8

# 查看帮助
snakemake --help
```

---

## 详细使用方法

### 配置文件说明

配置文件 `conf/config.yaml` 包含以下主要参数：

```yaml
# 样本配置
samples:
  - test_sample_100
  - sample2
  - sample3

input_dir: "./test"        # 输入序列目录
output_dir: "./results"    # 输出结果目录

# eggnog-mapper 配置
eggnog_data_dir: "./dataset/eggnog-mapper"
eggnog_cpu: 8

# KofamScan 配置  
kofam_ko_list: "./dataset/kegg_2026-02-01_ko_dataset/ko_list"
kofam_profiles: "./dataset/kegg_2026-02-01_ko_dataset/profiles"
kofam_cpu: 8

# 过滤阈值
evalue_threshold: 1.0e-5      # E-value 阈值
bitscore_threshold: 60         # Bit-score 阈值
min_confidence: "High"         # 最低可信度
require_kegg: true             # 要求有 KEGG 注释
require_go: false              # 要求有 GO 注释
```

### Snakemake 常用命令

```bash
# 1. 运行完整流程
snakemake --use-conda --cores 8

# 2. 仅运行 eggnog 流程（跳过 KofamScan）
snakemake --use-conda --cores 8 eggnog_only

# 3. 处理已有的 eggnog 结果（不重新运行 eggnog-mapper）
snakemake --use-conda --cores 4 process_existing_eggnog

# 4. 只保留高可信度 + KEGG 注释的结果
snakemake --use-conda --cores 4 \
    --config min_confidence=High require_kegg=true \
    high_confidence_only

# 5. 强制重新运行（删除旧结果后重跑）
snakemake --use-conda --cores 8 --forceall

# 6. 试运行（不实际执行，查看执行计划）
snakemake --use-conda --cores 8 -n

# 7. 生成有向无环图（DAG）
snakemake --dag | dot -Tpng > dag.png
```

### 命令行参数覆盖

可以在命令行使用 `--config` 参数临时覆盖配置文件：

```bash
snakemake --use-conda --cores 8 \
    --config samples=["sample1","sample2"] \
             evalue_threshold=1e-10 \
             min_confidence=High
```

---

## 分析流程详解

### 流程图

```
输入序列 (.pep/.fa)
    │
    ├── eggnog-mapper 流程 ─────────────────────────┐
    │    │                                           │
    │    ▼                                           │
    │ .emapper.annotations                          │
    │    │                                           │
    │    ▼                                           │
    │ eggnog_processor.py                           │
    │    │                                           │
    │    ▼                                           │
    │ _eggnog_formatted.tsv                         │
    │ _eggnog_high_confidence.tsv                   │
    │                                                │
    ├── KofamScan 流程 ─────────────────────────────┤
    │    │                                           │
    │    ▼                                           │
    │ _kofam_detail.txt                             │
    │    │                                           │
    │    ▼                                           │
    │ KofamScan_processor.py                        │
    │    │                                           │
    │    ▼                                           │
    │ _kofam_formatted.tsv                          │
    │ _kofam_high_confidence.tsv                    │
    │                                                │
    └── 结果合并 ───────────────────────────────────┘
         │
         ▼
    merged/eggnog_all_samples.tsv
    merged/kofam_all_samples.tsv
    merged/ALL_SAMPLES_SUMMARY_REPORT.txt
```

### 各步骤说明

| 步骤 | 工具 | 输入 | 输出 | 说明 |
|------|------|------|------|------|
| 1 | eggnog-mapper | protein sequences | .annotations | 功能注释 |
| 2 | eggnog_processor | .annotations | _formatted.tsv | 质量过滤和可信度评估 |
| 3 | KofamScan | protein sequences | _detail.txt | KO 注释 |
| 4 | KofamScan_processor | _detail.txt | _formatted.tsv | 可信度评估 |
| 5 | merge_results | 各样本结果 | merged/*.tsv | 多样本合并 |

---

## 结果解读

### 输出文件结构

```
results/
├── {sample}/                          # 单样本结果目录
│   ├── {sample}.emapper.annotations   # eggnog 原始输出
│   ├── {sample}.emapper.hits          # 比对详情
│   ├── {sample}.emapper.seed_orthologs
│   ├── {sample}_eggnog_formatted.tsv  # 处理后的 eggnog 结果 ⭐
│   ├── {sample}_eggnog_high_confidence.tsv  # 高可信度子集 ⭐
│   ├── {sample}_eggnog_report.txt     # 处理报告
│   ├── {sample}_kofam_detail.txt      # KofamScan 原始输出
│   ├── {sample}_kofam_formatted.tsv   # 处理后的 Kofam 结果
│   └── {sample}_kofam_high_confidence.tsv
│
└── merged/                              # 多样本合并结果
    ├── eggnog_all_samples.tsv          # eggnog 合并结果 ⭐⭐
    ├── eggnog_high_confidence.tsv      # eggnog 高可信度合并
    ├── eggnog_summary_stats.txt        # 统计报告
    └── ALL_SAMPLES_SUMMARY_REPORT.txt  # 整体汇总报告
```

### 结果文件格式

#### 1. `{sample}_eggnog_formatted.tsv`

主结果文件，包含完整的注释信息和可信度评估：

| 列名 | 说明 | 示例 |
|------|------|------|
| query | 查询序列 ID | rb_2.p2 |
| seed_ortholog | 最佳匹配的种子同源基因 | 71139.XP_010029570.1 |
| evalue | E-value（越小越好）| 1.58e-168 |
| score | Bit-score（越大越好）| 485.0 |
| eggnog_ogs | eggNOG 直系同源组 | COG0679@1\|root,... |
| cog_category | COG 功能分类 | S |
| description | 功能描述 | Transporter |
| kegg_ko | KEGG KO 编号 | ko:K07088 |
| kegg_pathway | KEGG 通路 | ko03030,map03030 |
| gos | GO 注释 | GO:0003674,GO:0005215 |
| ec | EC 编号 | 1.8.4.12 |
| pfams | Pfam 结构域 | Mem_trans |
| **confidence_level** | 可信度等级 | High/Medium/Low |
| **confidence_score** | 可信度分数 (0-100) | 95 |
| **confidence_reason** | 可信度说明 | High quality annotation |

#### 2. `{sample}_eggnog_high_confidence.tsv`

高可信度子集，只包含 confidence_level = "High" 的记录，格式同上。

#### 3. `merged/eggnog_all_samples.tsv`

多样本合并结果，**新增 sample 列**标识样本来源：

| sample | query | evalue | score | kegg_ko | confidence_level |
|--------|-------|--------|-------|---------|------------------|
| sample1 | gene1 | 1e-100 | 200 | ko:K00001 | High |
| sample1 | gene2 | 1e-50 | 150 | ko:K00002 | Medium |
| sample2 | gene1 | 1e-120 | 250 | ko:K00001 | High |

### 统计报告解读

#### 处理报告示例 (`*_report.txt`)

```
EggNOG Annotation Processing Report
======================================================================

Parameters:
  E-value threshold: 1e-05
  Bit-score threshold: 60
  Mode: Standard
  Min confidence: High

Statistics:
  Total records: 99          ← 原始注释数
  Passed filter: 63 (63.6%)  ← 通过质量过滤
  Filtered out: 36 (36.4%)   ← 被过滤掉

Confidence Distribution:
  High: 92 (92.9%)           ← 高可信度 (推荐)
  Medium: 7 (7.1%)           ← 中等可信度
  Low: 0 (0.0%)              ← 低可信度

Annotation Coverage:
  With KEGG: 64 (64.6%)      ← 有 KEGG 注释
  With GO: 60 (60.6%)        ← 有 GO 注释
  With both KEGG and GO: 43 (43.4%)  ← 同时有两者
```

#### 可信度评分标准

| 指标 | 优秀 | 良好 | 达标 | 一般 | 较差 |
|------|------|------|------|------|------|
| **E-value** | ≤1e-20 (40分) | ≤1e-10 (35分) | ≤1e-5 (30分) | ≤0.001 (20分) | ≤0.01 (10分) |
| **Bit-score** | ≥200 (30分) | ≥100 (25分) | ≥60 (20分) | ≥40 (10分) | <40 (0分) |
| **注释丰富度** | ≥4类 (30分) | 3类 (25分) | 2类 (20分) | 1类 (10分) | 0类 (0分) |

| 等级 | 总分范围 | 说明 | 建议 |
|------|----------|------|------|
| **High** | 80-100 | 高质量注释 | 可放心使用 |
| **Medium** | 50-79 | 中等质量 | 建议复核关键结果 |
| **Low** | 0-49 | 低质量 | 建议谨慎使用或丢弃 |

---

## 示例分析

### 示例数据: test_sample_100.pep

**样本信息**: 100 条蛋白质序列（来自植物转录组）

**运行命令**:
```bash
# 单样本分析
snakemake --use-conda --cores 4 \
    --config samples=["test_sample_100"] \
             min_confidence=High \
             require_kegg=true \
    results/test_sample_100/test_sample_100_eggnog_formatted.tsv
```

**分析结果**:

| 指标 | 数值 | 说明 |
|------|------|------|
| 输入序列 | 100 | 蛋白质序列 |
| 成功注释 | 99 | 99% 注释率 |
| 通过质量过滤 | 63 (63.6%) | 符合阈值要求 |
| 高可信度 | 63 (100%) | 通过过滤的都是 High |
| 有 KEGG | 63 (100%) | 都有 KO 编号 |
| 有 GO | 43 (68.3%) | 大部分有 GO |

**代表性注释结果**:

| 基因 | E-value | Score | KO | 功能描述 | 可信度 |
|------|---------|-------|-----|----------|--------|
| rb_13.p3 | 0.0 | 1486 | K11450 | 组蛋白去甲基化酶 | High/95 |
| rb_18.p1 | 6.2e-189 | 578 | K12854 | U5 snRNP 200kDa | High/90 |
| rb_44.p1 | 8.6e-110 | 348 | K01652 | C2结构域蛋白 | High/85 |

---

## 脚本独立使用

### eggnog_processor.py

```bash
# 基本用法
python3 scripts/eggnog_processor.py \
    -i results/test_sample_100/test_sample_100.emapper.annotations \
    -o test_output

# 高可信度 + KEGG 过滤
python3 scripts/eggnog_processor.py \
    -i test.emapper.annotations \
    -o filtered \
    --min-confidence High \
    --require-kegg

# 自定义阈值
python3 scripts/eggnog_processor.py \
    -i test.emapper.annotations \
    -o strict_filtered \
    --evalue 1e-10 \
    --bitscore 80
```

### merge_results.py

```bash
# 合并多个样本结果
python3 scripts/merge_results.py \
    --input-dir results \
    --samples sample1 sample2 sample3 \
    --tool eggnog \
    --output-all merged/eggnog_all.tsv \
    --output-high merged/eggnog_high.tsv \
    --output-stats merged/stats.txt
```

---

## 常见问题

### Q1: 首次运行很慢？

A: 首次运行时需要下载并创建 Conda 环境，可能需要 10-30 分钟。环境创建后会缓存，后续运行会很快。

### Q2: eggnog-mapper 找不到数据库？

A: 确保在 `conf/config.yaml` 中正确设置了 `eggnog_data_dir`，且该目录包含 `eggnog.db` 等数据库文件。

### Q3: 如何只处理已有结果，不重新跑注释？

A: 使用 `process_existing_eggnog` 规则：
```bash
snakemake --use-conda --cores 4 process_existing_eggnog
```

### Q4: 如何调整过滤严格程度？

A: 修改 `conf/config.yaml` 中的参数：
```yaml
# 严格模式
evalue_threshold: 1.0e-10
bitscore_threshold: 80
min_confidence: "High"

# 宽松模式
evalue_threshold: 1.0e-5
bitscore_threshold: 40
min_confidence: "Medium"
```

### Q5: 多样本如何合并分析？

A: 在配置文件中列出所有样本：
```yaml
samples:
  - sample1
  - sample2
  - sample3
```
运行后会自动生成 `results/merged/` 目录下的合并结果。

---

## 过滤阈值参考

| 质量标准 | 标准模式 | 严格模式 | 说明 |
|----------|----------|----------|------|
| E-value | ≤ 1e-5 | ≤ 1e-10 | 控制假阳性 |
| Bit-score | ≥ 60 | ≥ 80 | 比对得分 |
| Percentage identity | ≥ 40-50% | ≥ 70% | 序列同一性 |
| Query coverage | ≥ 20% | ≥ 30% | 查询序列覆盖率 |
| Subject coverage | ≥ 20% | ≥ 30% | 参考序列覆盖率 |

---

## 依赖

- Python 3.8+
- pandas
- eggnog-mapper 2.1.13
- KofamScan 1.3.0
- Snakemake 7.0+
- Conda/Mamba

---

## 引用

如果使用本流程，请引用：

1. eggNOG-mapper v2: [https://doi.org/10.1093/molbev/msab293](https://doi.org/10.1093/molbev/msab293)
2. eggNOG 5.0: [https://doi.org/10.1093/nar/gky1085](https://doi.org/10.1093/nar/gky1085)
3. KofamScan: [https://doi.org/10.1093/bioinformatics/btz859](https://doi.org/10.1093/bioinformatics/btz859)
