# EggNOG & KofamScan Processor 过滤与可信度评估标准

本文档汇总了 `eggnog_processor.py` 和 `KofamScan_processor.py` 两个脚本的质量过滤逻辑与可信度（Confidence）评分体系。

---

## 1. eggnog_processor（EggNOG-Mapper 结果处理）

### 1.1 命令行过滤参数（硬阈值）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--evalue` | `1e-5` | 最大允许 E-value，> 此值丢弃 |
| `--bitscore` | `60` | 最小允许 Bit-score，< 此值丢弃 |
| `--pident` | 无 | 最小序列一致性（%），若指定则过滤 |
| `--qcov` | 无 | 最小 Query 覆盖度（%），若指定则过滤 |
| `--scov` | 无 | 最小 Subject 覆盖度（%），若指定则过滤 |
| `--min-confidence` | `Low` | 最低可信度等级：`High` / `Medium` / `Low` |
| `--require-kegg` | False | 仅保留带 KEGG KO 注释的记录 |
| `--require-go` | False | 仅保留带 GO 注释的记录 |
| `--strict` | False | 严格模式（在评分阶段采用更严标准） |
| `--keep-all` | False | 保留所有记录，只做评分不过滤 |

**过滤顺序**
1. 最低可信度检查（`confidence_level` 必须 ≥ `--min-confidence`）
2. E-value 阈值检查
3. Bit-score 阈值检查
4. 若开启 `--require-kegg`，检查是否存在 KEGG KO
5. 若开启 `--require-go`，检查是否存在 GO 注释

### 1.2 可信度评分体系（0–100 分）

评分函数 `calculate_confidence_score()` 从三个维度打分：

#### ① E-value 评分（0–40 分）
| E-value 范围 | 得分 | 评级 |
|--------------|------|------|
| ≤ 1e-20 | 40 | excellent |
| ≤ 1e-10 | 35 | very good |
| ≤ 1e-5 | 30 | good |
| ≤ 0.001 | 20 | moderate |
| ≤ 0.01 | 10 | marginal |
| > 0.01 | 0 | poor |

#### ② Bit-score 评分（0–30 分）
| Score 范围 | 得分 | 评级 |
|------------|------|------|
| ≥ 200 | 30 | excellent |
| ≥ 100 | 25 | very good |
| ≥ `--bitscore`（默认 60） | 20 | good |
| ≥ 40 | 10 | moderate |
| < 40 | 0 | low |

#### ③ 注释完整性评分（0–30 分）
统计以下 5 类注释中存在的种类数（GO、KEGG KO、EC、Pfam、CAZy）：
| 存在种类数 | 得分 | 评级 |
|------------|------|------|
| ≥ 4 | 30 | rich |
| 3 | 25 | comprehensive |
| 2 | 20 | good |
| 1 | 10 | limited |
| 0 | 0 | no annotations |

#### 可信度等级判定
| 总得分 | 等级 | 含义 |
|--------|------|------|
| ≥ 80 | **High** | 高质量注释 |
| 50–79 | **Medium** | 中等质量注释 |
| < 50 | **Low** | 低质量注释 |

---

## 2. KofamScan_processor（KofamScan 结果处理）

### 2.1 输入解析与预过滤

脚本读取 KofamScan `detail` 格式输出：
- 忽略空行与 `#` 注释行
- **星号标记（`*`）** = `is_significant=True`，表示该 hit 通过了 KofamScan 的内置阈值
- 解析字段：`gene_name`、`KO`、`threshold`、`score`、`E-value`、`definition`

> 注意：KofamScan_processor **不会**在解析阶段丢弃未带星号的 hit，所有 hit 都会进入后续分析；最终过滤由 `--min-confidence` 控制。

### 2.2 最佳 KO 选择策略

对每个基因（`query`）的所有 hit：
1. 先按 `is_significant` 降序（带星号的优先）
2. 再按 `score` 降序
3. 取排名第一的 hit 作为该基因的**最佳 KO**

### 2.3 可信度评分体系（三级评估）

函数 `calculate_confidence()` 为最佳 hit 评定等级：

#### ① High Confidence（高置信）
**条件**：通过阈值（`is_significant=True`）且 `score >= threshold`
- 若该基因**只有一个显著 hit**：得分 95，原因 `Pass threshold, unique significant hit`
- 若存在**多个显著 hit**：得分 90，原因 `Pass threshold, multiple significant hits`

#### ② Medium Confidence（中置信）
**条件**：未通过阈值，但满足以下任一条件
- `score > 100`
- `evalue < 1e-20`

细分：
- 若该基因有多个 hit，且最佳 hit 与次佳 hit 的 `score_gap < 5`：得分 75，原因 `High score but close to other hits (ambiguous)`
- 否则：得分 80，原因 `High score but marginally below threshold`

#### ③ Low Confidence（低置信）
**触发条件**（满足任一即落入低置信）：
- `score < 60`
- `evalue > 1e-5`

**额外降级规则**：
- 若该基因有多个 hit，且 top1 与 top2 的 score 差异 `< 10%`：得分 50，原因 `Multiple hits with similar scores (ambiguous family)`

#### 默认兜底
- 未触发以上任何明确条件：得分 60，等级 `Medium`，原因 `Moderate evidence, no clear threshold pass`

### 2.4 最低可信度过滤

脚本支持 `--min-confidence` 参数（`High` / `Medium` / `Low`）：
- 主输出 `.tsv` **保留所有基因**的最佳 KO（即不过滤）
- `_highconf.tsv` 仅输出 `confidence_level == "High"` 的记录
- 报告中的统计数字会按 `--min-confidence` 进行汇总

---

## 3. 两Processor对比速查

| 维度 | eggnog_processor | KofamScan_processor |
|------|------------------|---------------------|
| **输入** | `*.emapper.annotations` | KofamScan `detail` 输出 |
| **核心过滤** | E-value、Bit-score、可选 KEGG/GO 强制 | KofamScan 内置阈值（星号）+ score 评估 |
| **评分维度** | E-value + Score + 注释完整性（3项） | 是否过阈值 + score/evalue + hit 竞争（3项） |
| **得分范围** | 0–100 | 40–95 |
| **High 阈值** | ≥ 80 分 | 通过阈值且为最佳 hit |
| **输出格式** | 类 eggNOG annotations TSV | 类 eggNOG annotations TSV |
| **对比功能** | 无 | 可选与 eggNOG 结果进行 KO 一致性对比 |
