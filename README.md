# KEGG Annotation Pipeline

基于 eggnog-mapper 和 KofamScan 的基因功能注释流程，提供质量过滤、可信度评估、结果整合和 AI 驱动的逐蛋白可靠性分析。

## 项目特点

- ✅ **模块化设计**: 使用 Snakemake 管理分析流程，规则按步骤编号（01-08），结构清晰
- ✅ **质量过滤**: 基于 E-value、Bit-score 等多维度过滤
- ✅ **可信度评估**: 三级可信度分级 (High/Medium/Low)，0-100分评分体系
- ✅ **结果整合**: 对 eggnog 和 KofamScan 结果进行横向整合与冲突裁决
- ✅ **多样本合并**: 支持多样本结果合并，便于下游分析
- ✅ **Conda 环境**: 自动管理依赖环境，保证可重复性
- ✅ **AI 驱动分析**: 支持逐蛋白可靠性评估（Ollama/OpenAI/Claude），含分层筛选与 Token 消耗追踪
- ✅ **灵活输入**: 支持 `.pep`、`.fa`、`.fasta`、`.faa`、`.protein` 及复合扩展名（如 `.fa.TD2.1k.pep`）

---

## 目录结构

```
.
├── snakefile                 # 主工作流文件
├── config.yaml              # 示例配置文件
├── conf/
│   ├── config.yaml          # 生产配置
│   ├── resource.yaml        # 资源配置
│   ├── parameter.yaml       # 参数配置
│   └── ai.yaml              # AI 配置
├── rules/                   # Snakemake 规则目录（按步骤编号）
│   ├── 01.common.smk       # 通用规则与辅助函数
│   ├── 02.config.smk       # 全局配置变量
│   ├── 03.eggnog.smk       # eggnog-mapper 分析规则
│   ├── 04.kofamscan.smk    # KofamScan 分析规则
│   ├── 05.integrate.smk    # eggnog + KofamScan 整合评分
│   ├── 06.merge.smk        # 多样本结果合并
│   ├── 07.ai_curator.smk   # AI 逐蛋白评估
│   └── 08.report.smk       # 报告生成规则
├── env/                     # Conda 环境配置
│   ├── eggnog-mapper.yaml
│   ├── kofamscan.yaml
│   ├── python3.yaml
│   └── openai.yaml
├── scripts/                 # Python 处理脚本
│   ├── eggnog_processor.py
│   ├── KofamScan_processor.py
│   ├── integrate_annotations.py
│   ├── merge_results.py
│   └── ai_curator.py
├── docs/                    # 文档
│   └── filtering_standards.md   # 过滤与可信度评估标准详解
├── dataset/                 # 数据库目录
│   ├── eggnog-mapper/
│   └── kegg_*_ko_dataset/
└── test/                    # 测试数据
    └── test_sample_100.pep
```

---

## 快速开始

### 1. 环境准备

确保已安装 [Snakemake](https://snakemake.readthedocs.io/) 和 [Conda](https://docs.conda.io/) (推荐 Miniconda):

```bash
# 安装 Snakemake (需 9.9.0+)
conda install -n base -c conda-forge -c bioconda snakemake
```

### 2. 配置文件设置

```bash
# 复制示例配置文件到生产配置
cp config.yaml conf/config.yaml

# 编辑生产配置
vim conf/config.yaml
vim conf/ai.yaml  # 如需启用 AI 分析
```

### 3. 运行分析

```bash
# 运行完整流程（会自动创建 conda 环境）
snakemake --use-conda --cores 8

# 查看执行计划（不实际运行）
snakemake --use-conda --cores 8 -n
```

---

## 详细使用方法

### 配置文件说明

配置文件 `conf/config.yaml` 包含以下主要参数：

```yaml
# 样本配置（支持复合扩展名，如 rnabloom_transcript_LongOrfs.fa.TD2.1k.pep）
samples:
  - test_sample_100
  - rnabloom_transcript_LongOrfs

input_dir: "./test"        # 输入序列目录
output_dir: "./results"    # 输出结果目录（当前版本主要作为配置保留，实际输出按步骤目录存放）

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

# 2. 仅运行注释步骤（跳过合并和 AI）
snakemake --use-conda --cores 8 annotate

# 3. 仅运行 AI 分析（已有注释结果时）
snakemake --use-conda --cores 8 ai_analysis

# 4. 仅合并多样本结果
snakemake --use-conda --cores 4 merge

# 5. 只保留高可信度 + KEGG 注释的结果
snakemake --use-conda --cores 4 \
    --config min_confidence=High require_kegg=true

# 6. 强制重新运行（删除旧结果后重跑）
snakemake --use-conda --cores 8 --forceall

# 7. 试运行（不实际执行，查看执行计划）
snakemake --use-conda --cores 8 -n

# 8. 生成有向无环图（DAG）
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
输入序列 (.pep/.fa/.fasta/.faa/.protein，支持复合扩展名)
    │
    ├── eggnog-mapper 流程 ─────────────────────────┐
    │    │                                           │
    │    ▼                                           │
    │ 01.eggnog/{sample}.emapper.annotations        │
    │    │                                           │
    │    ▼                                           │
    │ eggnog_processor.py                           │
    │    │                                           │
    │    ▼                                           │
    │ 01.eggnog/{sample}_eggnog.tsv                 │
    │ 01.eggnog/{sample}_eggnog_highconf.tsv        │
    │                                                │
    ├── KofamScan 流程 ─────────────────────────────┤
    │    │                                           │
    │    ▼                                           │
    │ 02.kofam/{sample}_kofam_detail.txt            │
    │    │                                           │
    │    ▼                                           │
    │ KofamScan_processor.py                        │
    │    │                                           │
    │    ▼                                           │
    │ 02.kofam/{sample}_kofam.tsv                   │
    │ 02.kofam/{sample}_kofam_highconf.tsv          │
    │                                                │
    ├── 整合评分流程 ───────────────────────────────┤
    │    │                                           │
    │    ▼                                           │
    │ integrate_annotations.py                      │
    │    │                                           │
    │    ▼                                           │
    │ 03.merge/{sample}_integrated.tsv              │
    │ 03.merge/{sample}_integrated_report.txt       │
    │                                                │
    ├── 结果合并 ───────────────────────────────────┤
    │    │                                           │
    │    ▼                                           │
    │ merge_results.py                              │
    │    │                                           │
    │    ▼                                           │
    │ 03.merge/eggnog_all_samples.tsv               │
    │ 03.merge/kofam_all_samples.tsv                │
    │ 03.merge/SUMMARY_REPORT.txt                   │
    │                                                │
    └── AI 逐蛋白评估 ──────────────────────────────┘
         │
         ▼
    04.ai/{sample}_ai_report.md
    04.ai/{sample}_ai_analysis.json
    04.ai/AI_MULTI_SAMPLE_SUMMARY.md
```

### 各步骤说明

| 步骤 | 规则文件 | 工具 | 输入 | 输出 | 说明 |
|------|---------|------|------|------|------|
| 1 | 03.eggnog.smk | eggnog-mapper | protein sequences | 01.eggnog/*.annotations | 功能注释 |
| 2 | 03.eggnog.smk | eggnog_processor | .annotations | 01.eggnog/*_eggnog.tsv | 质量过滤和可信度评估 |
| 3 | 04.kofamscan.smk | KofamScan | protein sequences | 02.kofam/*_kofam_detail.txt | KO 注释 |
| 4 | 04.kofamscan.smk | KofamScan_processor | _detail.txt | 02.kofam/*_kofam.tsv | 可信度评估 |
| 5 | 05.integrate.smk | integrate_annotations | eggnog + kofam TSV | 03.merge/*_integrated.tsv | 横向整合与冲突裁决 |
| 6 | 06.merge.smk | merge_results | 各样本结果 | 03.merge/*.tsv | 多样本合并与统计 |
| 7 | 07.ai_curator.smk | ai_curator | eggnog + kofam TSV | 04.ai/*_ai_report.md | 逐蛋白 AI 可靠性评估 |
| 8 | 08.report.smk | shell | 各步骤结果 | 03.merge/*_summary.txt | 样本摘要报告 |

---

## 结果解读

### 输出文件结构

```
01.eggnog/                          # eggnog-mapper 结果目录
├── {sample}.emapper.annotations   # eggnog 原始输出
├── {sample}.emapper.hits          # 比对详情
├── {sample}.emapper.seed_orthologs
├── {sample}_eggnog.tsv            # 处理后的 eggnog 结果 ⭐
├── {sample}_eggnog_highconf.tsv   # 高可信度子集 ⭐
└── {sample}_eggnog_report.txt     # 处理报告

02.kofam/                           # KofamScan 结果目录
├── {sample}_kofam_detail.txt      # KofamScan 原始输出
├── {sample}_kofam_raw.tsv         # mapper 格式原始输出
├── {sample}_kofam.tsv             # 处理后的 Kofam 结果
├── {sample}_kofam_highconf.tsv    # 高可信度子集
└── {sample}_kofam_report.txt      # 处理报告

03.merge/                           # 整合与合并结果目录
├── {sample}_integrated.tsv        # 单样本整合结果
├── {sample}_integrated_report.txt # 整合评分报告
├── {sample}_summary.txt           # 单样本摘要报告
├── eggnog_all_samples.tsv         # eggnog 多样本合并 ⭐⭐
├── eggnog_highconf.tsv            # eggnog 高可信度合并
├── kofam_all_samples.tsv          # kofam 多样本合并
├── kofam_highconf.tsv             # kofam 高可信度合并
└── SUMMARY_REPORT.txt             # 整体汇总报告

04.ai/                              # AI 分析结果目录
├── {sample}_ai_report.md          # AI 逐蛋白评估报告（Markdown）
├── {sample}_ai_analysis.json      # 结构化评估数据（JSON）
└── AI_MULTI_SAMPLE_SUMMARY.md     # 多样本 AI 汇总
```

### 结果文件格式

#### 1. `{sample}_eggnog.tsv`

主结果文件，包含完整的注释信息和可信度评估：

| 列名 | 说明 | 示例 |
|------|------|------|
| query | 查询序列 ID | gene_1 |
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
| **confidence_level** | 可信度等级 | High/Medium/Low |
| **confidence_score** | 可信度分数 (0-100) | 95 |
| **confidence_reason** | 可信度说明 | High quality annotation |

#### 2. `{sample}_eggnog_highconf.tsv`

高可信度子集，只包含 confidence_level = "High" 的记录，格式同上。

#### 3. `03.merge/eggnog_all_samples.tsv`

多样本合并结果，**新增 sample 列**标识样本来源：

| sample | query | evalue | score | kegg_ko | confidence_level |
|--------|-------|--------|-------|---------|------------------|
| sample1 | gene1 | 1e-100 | 200 | ko:K00001 | High |
| sample1 | gene2 | 1e-50 | 150 | ko:K00002 | Medium |
| sample2 | gene1 | 1e-120 | 250 | ko:K00001 | High |

#### 4. `03.merge/{sample}_integrated.tsv`

整合评分结果，同时包含 eggNOG 和 KofamScan 的字段，以及综合评分：

| 列名 | 说明 |
|------|------|
| query | 蛋白 ID |
| integrated_ko | 最终选定的 KO |
| ko_agreement | agree / conflict / single_source |
| integrated_score | 综合评分 (0-100) |
| integrated_level | High / Medium / Low |
| eggnog_kegg_ko | eggNOG 的 KO |
| kofam_ko | KofamScan 的 KO |
| ... | 其余 eggnog + kofam 原始字段 |

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

详见 `docs/filtering_standards.md`。简要如下：

**eggnog_processor**（0-100分）
- E-value 评分（0-40分）
- Bit-score 评分（0-30分）
- 注释完整性评分（0-30分，基于 GO/KO/EC/Pfam/CAZy）

**KofamScan_processor**（40-95分）
- High：通过阈值（`*`）且 score ≥ threshold
- Medium：未过阈值但 score > 100 或 evalue < 1e-20
- Low：score < 60 或 evalue > 1e-5

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
# 单样本完整分析
snakemake --use-conda --cores 4 \
    --config samples=["test_sample_100"] \
             min_confidence=High \
             require_kegg=true
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

---

## 脚本独立使用

### eggnog_processor.py

```bash
# 基本用法
python3 scripts/eggnog_processor.py \
    -i 01.eggnog/test_sample_100.emapper.annotations \
    -o 01.eggnog/test_sample_100_eggnog

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

### KofamScan_processor.py

```bash
python3 scripts/KofamScan_processor.py \
    -i 02.kofam/test_sample_100_kofam_detail.txt \
    -o 02.kofam/test_sample_100_kofam \
    -e 01.eggnog/test_sample_100.emapper.annotations \
    --min-confidence High
```

### integrate_annotations.py

```bash
python3 scripts/integrate_annotations.py \
    -e 01.eggnog/test_sample_100_eggnog.tsv \
    -k 02.kofam/test_sample_100_kofam.tsv \
    -s test_sample_100 \
    -o 03.merge/test_sample_100
```

### merge_results.py

```bash
# 合并 eggnog 结果
python3 scripts/merge_results.py \
    --input-dir 01.eggnog \
    --samples sample1 sample2 sample3 \
    --tool eggnog \
    --output-all 03.merge/eggnog_all.tsv \
    --output-high 03.merge/eggnog_high.tsv \
    --output-stats 03.merge/eggnog_stats.txt

# 合并 kofam 结果
python3 scripts/merge_results.py \
    --input-dir 02.kofam \
    --samples sample1 sample2 sample3 \
    --tool kofam \
    --output-all 03.merge/kofam_all.tsv \
    --output-high 03.merge/kofam_high.tsv \
    --output-stats 03.merge/kofam_stats.txt
```

---

## AI 注释分析功能

KEGG Annotation Pipeline 支持 AI 驱动的**逐蛋白可靠性评估**，而非仅样本级汇总统计。

### 功能特点

- **逐蛋白可靠性评估**: 对每条蛋白分别评估 eggNOG 和 KofamScan 的可靠性
- **物种合理性判断**: 结合 `taxonomy` 参数，判断注释功能对该物种是否合理
- **Tax_scope 精确度检查**: 评估 eggNOG `tax_scope` 与物种分类的匹配层级
- **KofamScan 阈值比值解读**: 结合 KO 类型（管家基因 vs 稀有基因）判断 ratio 可信度
- **工具一致性检测**: 自动标记 eggNOG 与 KofamScan 的 KO 冲突
- **分层筛选降本**: 高置信/低质量两端由规则直接判定，仅模糊区域送 AI
- **Token 消耗追踪**: 自动统计 prompt/completion/total tokens，便于成本控制

### 支持的 AI 提供商

| 提供商 | 模型示例 | 特点 |
|--------|---------|------|
| **Ollama** (默认) | llama3.2, mistral | 本地运行，无需联网，免费 |
| **OpenAI** | gpt-4, gpt-3.5-turbo | 云端 API，性能强 |
| **Claude** | claude-3-sonnet | 云端 API，擅长长文本 |

### 快速开始

#### 1. 使用本地 Ollama（推荐）

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型（以 llama3.2 为例，4GB 左右）
ollama pull llama3.2

# 确认服务运行
curl http://localhost:11434/api/tags
```

#### 2. 启用 AI 分析

编辑 `conf/ai.yaml`:

```yaml
ai:
  enabled: true
  provider: "ollama"
  model: "llama3.2"
  taxonomy: "Bacteria;Firmicutes;Bacillales"  # 你的物种分类
  max_proteins: 50                              # 仅对模糊区域最多评估 50 个蛋白
  # api_base: "http://localhost:11434"         # 可选：自定义端点
```

#### 3. 运行分析

```bash
# 运行完整流程（包含 AI 分析）
snakemake --use-conda --cores 8

# 或仅运行 AI 分析（已有注释结果时）
snakemake --use-conda --cores 8 ai_analysis
```

### 输出结果

AI 分析会生成以下文件：

```
04.ai/
├── {sample}_ai_report.md          # AI 逐蛋白评估报告（Markdown）⭐
├── {sample}_ai_analysis.json      # 结构化评估数据（JSON）⭐
└── AI_MULTI_SAMPLE_SUMMARY.md     # 多样本汇总（多样本时）
```

#### AI 报告内容示例

```markdown
# AI 注释分析报告（逐蛋白评估）

## 处理策略与 Token 消耗
- 规则直接判定: 230 个蛋白（不消耗 token）
- AI 实际评估: 50 个蛋白
- Total tokens: 184,320

## 整体质量汇总
- High confidence: 42 (14.0%)
- Medium confidence: 28 (9.3%)
- Low confidence: 8 (2.7%)
- Cross-tool conflicts: 5

## 潜在问题蛋白（Top 20）
- `gene_23` | Overall: Low | Action: Reject | Source: AI | Flags: Eukaryota tax_scope in bacteria
...
```

### 分层筛选策略说明

为控制 Token 成本，`ai_curator.py` 默认开启**分层筛选**（可用 `--no-auto-filter` 关闭）：

| 分类 | 判定标准 | 处理方式 | Token 消耗 |
|------|----------|----------|-----------|
| **高置信** | `e-value < 1e-10` **且** `Kofam ratio > 1.5` | 规则直接 `Accept` | 0 |
| **低质量** | `e-value > 1e-3` **或** `Kofam ratio < 0.5` | 规则直接 `Reject` | 0 |
| **模糊区域** | 其余蛋白 | 送 AI 评估 | 有 |

这意味着对于一个 3000 蛋白的基因组，可能只有 300-600 个蛋白进入模糊区域，再按 `--max-proteins` 限制后，实际 API 调用可能只有几十个，大幅降低成本。

---

## 安全指南 🔒

### API 密钥安全最佳实践

**⚠️  绝对不要直接在配置文件中写入真实 API key！**

#### 安全风险

| 方式 | 风险等级 | 说明 |
|------|---------|------|
| 明文写在 config.yaml | 🔴 极高 | 可能被提交到 Git，泄露密钥 |
| 命令行参数传递 | 🟠 高 | 会被记录在 shell 历史和进程列表 |
| 环境变量（✅ 推荐） | 🟢 低 | 只在内存中存在，不会持久化到文件 |

#### ✅ 推荐做法：使用环境变量

##### 步骤 1：设置环境变量（在运行前）

```bash
# 方式 1：当前 shell 会话（推荐用于测试）
export AI_API_KEY="sk-your-actual-api-key"

# 方式 2：写入 ~/.bashrc 或 ~/.zshrc（长期有效）
echo 'export AI_API_KEY="sk-your-actual-api-key"' >> ~/.bashrc
source ~/.bashrc
```

##### 步骤 2：在配置中只写变量名

```yaml
ai:
  enabled: true
  provider: "openai"
  model: "glm-4.7"
  api_key: "AI_API_KEY"      # ← ✅ 只写变量名，不写真实 key
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

##### 步骤 3：运行分析

```bash
snakemake --use-conda --cores 8
```

### 🔐 安全机制说明

本流程已实施以下安全措施：

1. **配置文件安全**：脚本会检测 `api_key` 是否为全大写的环境变量名格式，如果是，从环境变量读取而非直接使用
2. **命令行保护**：即使通过命令行传入 key，也会立即转移到环境变量，避免在 `ps` 进程列表中暴露
3. **日志脱敏**：API key 不会出现在任何日志文件中，日志只显示 `长度: 32` 而非真实内容
4. **Git 保护**：`.gitignore` 已包含 `.env`、`*.log`、`test/` 产物等，防止意外提交敏感信息

### 使用不同云平台

#### 阿里云百炼 (DashScope)

```bash
export DASHSCOPE_API_KEY="sk-your-dashscope-key"
```

```yaml
ai:
  enabled: true
  provider: "openai"  # 阿里云使用兼容模式
  model: "glm-4.7"
  api_key: "DASHSCOPE_API_KEY"
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

#### OpenAI 官方

```bash
export OPENAI_API_KEY="sk-your-openai-key"
```

```yaml
ai:
  enabled: true
  provider: "openai"
  model: "gpt-4"
  api_key: "OPENAI_API_KEY"
  # api_base 默认为 https://api.openai.com/v1
```

#### 本地 Ollama（最安全，无需 API key）

```bash
# 无需设置 API key
ollama serve
```

```yaml
ai:
  enabled: true
  provider: "ollama"
  model: "llama3.2"
  # api_key 留空
  # api_base: "http://localhost:11434"
```

---

## 常见问题

### Q1: 首次运行很慢？

A: 首次运行时需要下载并创建 Conda 环境，可能需要 10-30 分钟。环境创建后会缓存，后续运行会很快。

### Q2: eggnog-mapper 找不到数据库？

A: 确保在 `conf/config.yaml` 中正确设置了 `eggnog_data_dir`，且该目录包含 `eggnog.db` 等数据库文件。

### Q3: 如何只处理已有结果，不重新跑注释？

A: 已有 `01.eggnog/*.emapper.annotations` 后，可直接运行后续处理步骤：
```bash
snakemake --use-conda --cores 4 annotate
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
运行 `snakemake --use-conda --cores 8` 后会自动生成 `03.merge/` 目录下的合并结果。

### Q6: AI 分析为什么没有评估所有蛋白？

A: 这是正常的成本控制设计。默认开启分层筛选：高置信和低质量蛋白由规则直接判定，只有模糊区域才送 AI。如需全量评估，在 `conf/ai.yaml` 中把 `max_proteins` 调大，或在命令行覆盖：
```bash
snakemake --use-conda --cores 4 --config ai.max_proteins=200 ai_analysis
```
（注意：全量评估会消耗大量 Token）

### Q7: 输入文件名带复合扩展名（如 `.fa.TD2.1k.pep`）如何配置？

A: `get_input_file()` 已支持复合扩展名。只需在 `samples` 中写基础名即可：
```yaml
samples:
  - rnabloom_transcript_LongOrfs
```
系统会自动匹配 `rnabloom_transcript_LongOrfs.fa.TD2.1k.pep`。

---

## 过滤阈值参考

| 质量标准 | 标准模式 | 严格模式 | 说明 |
|----------|----------|----------|------|
| E-value | ≤ 1e-5 | ≤ 1e-10 | 控制假阳性 |
| Bit-score | ≥ 60 | ≥ 80 | 比对得分 |
| Percentage identity | ≥ 40-50% | ≥ 70% | 序列同一性 |
| Query coverage | ≥ 20% | ≥ 30% | 查询序列覆盖率 |
| Subject coverage | ≥ 30% | ≥ 50% | 参考序列覆盖率 |

---

## 文档与参考

- **过滤标准详解**: 见 `docs/filtering_standards.md`
- **Snakemake 官方文档**: https://snakemake.readthedocs.io/
- **eggnog-mapper 文档**: https://github.com/eggnogdb/eggnog-mapper
- **KofamScan 文档**: https://www.genome.jp/tools/kofamkoala/

---

## 依赖

- Python 3.8+
- pandas, loguru, rich, requests
- eggnog-mapper 2.1.13
- KofamScan 1.3.0
- Snakemake 9.9.0+
- Conda/Mamba

---

## 引用

如果使用本流程，请引用：

1. eggNOG-mapper v2: [https://doi.org/10.1093/molbev/msab293](https://doi.org/10.1093/molbev/msab293)
2. eggNOG 5.0: [https://doi.org/10.1093/nar/gky1085](https://doi.org/10.1093/nar/gky1085)
3. KofamScan: [https://doi.org/10.1093/bioinformatics/btz859](https://doi.org/10.1093/bioinformatics/btz859)
