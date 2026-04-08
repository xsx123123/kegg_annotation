# AI 注释分析功能

KEGG Annotation Pipeline 现在支持 AI 驱动的注释质量评估和功能解读！

## 功能特点

- **智能质量评估**: AI 自动评估注释结果的可靠性和完整性
- **功能摘要生成**: 自动撰写样本的功能特征描述
- **问题识别**: 发现潜在的注释冲突和低质量结果
- **改进建议**: 提供针对性的分析优化建议
- **通路解读**: 对关键生物学通路进行智能解读

## 支持的 AI 提供商

| 提供商 | 模型示例 | 特点 |
|--------|---------|------|
| **Ollama** (默认) | llama3.2, mistral | 本地运行，无需联网，免费 |
| **OpenAI** | gpt-4, gpt-3.5-turbo | 云端 API，性能强 |
| **Claude** | claude-3-sonnet | 云端 API，擅长长文本 |

## 快速开始

### 1. 使用本地 Ollama（推荐）

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型（以 llama3.2 为例，4GB 左右）
ollama pull llama3.2

# 确认服务运行
curl http://localhost:11434/api/tags
```

### 2. 启用 AI 分析

编辑 `conf/config.yaml`:

```yaml
ai:
  enabled: true
  provider: "ollama"
  model: "llama3.2"
  # api_base: "http://localhost:11434"  # 可选：自定义端点
```

### 3. 运行分析

```bash
# 运行完整流程（包含 AI 分析）
snakemake --use-conda --cores 8

# 或仅运行 AI 分析（已有注释结果）
snakemake --use-conda --config ai.enabled=true ai_analysis
```

## 使用云端 API

### OpenAI

```yaml
ai:
  enabled: true
  provider: "openai"
  model: "gpt-4"
  api_key: "sk-..."  # 或通过环境变量 AI_API_KEY
```

设置环境变量：
```bash
export AI_API_KEY="sk-your-api-key"
snakemake --use-conda --cores 8
```

### Claude (Anthropic)

```yaml
ai:
  enabled: true
  provider: "claude"
  model: "claude-3-sonnet-20240229"
  api_key: "sk-ant-..."  # 或通过环境变量 AI_API_KEY
```

## 输出结果

AI 分析会生成以下文件：

```
results/
├── {sample}/
│   ├── {sample}_ai_report.md          # AI 分析报告（Markdown）
│   └── {sample}_ai_analysis.json      # 结构化数据（JSON）
└── merged/
    └── AI_MULTI_SAMPLE_SUMMARY.md     # 多样本汇总（多样本时）
```

### 报告内容示例

```markdown
# AI 注释分析报告

## 样本信息
**样本名称**: sample_1

## 功能摘要
该样本主要涉及代谢相关功能，包含丰富的碳水化合物代谢和能量产生相关基因...

## 质量评估
- **评分**: 85/100
- **等级**: High
- **评价**: 注释质量良好，KEGG 覆盖率高

## 关键功能
- 碳水化合物代谢: 包含多个糖酵解和 TCA 循环关键酶
- 能量代谢: 丰富的氧化磷酸化相关基因

## 潜在问题
- ⚠️ 部分膜蛋白注释可信度较低

## 改进建议
- 💡 建议手动检查 K07088 家族的注释

## 通路洞察
样本在次级代谢通路方面表现活跃，可能与环境适应性相关...
```

## 命令行覆盖

可以在运行时不修改配置文件直接启用 AI：

```bash
# 启用 AI 并指定提供商
snakemake --use-conda --cores 8 \
    --config ai.enabled=true ai.provider=ollama ai.model=llama3.2

# 使用 OpenAI
snakemake --use-conda --cores 8 \
    --config ai.enabled=true ai.provider=openai ai.model=gpt-4
```

## 故障排除

### Ollama 连接失败

```
Error: Connection refused
```

**解决**:
```bash
# 检查 Ollama 是否运行
ollama list

# 手动启动
ollama serve

# 或设置远程地址
export AI_API_BASE="http://your-ollama-server:11434"
```

### API 密钥错误

```
Error: Authentication failed
```

**解决**:
```bash
# 检查环境变量
echo $AI_API_KEY

# 或直接在配置中指定（不推荐，不安全）
```

### 模型不存在

```
Error: model "xxx" not found
```

**解决**:
```bash
# 拉取模型
ollama pull llama3.2

# 查看可用模型
ollama list
```

## 注意事项

1. **隐私保护**: 使用云端 API 时，注释数据会发送到第三方服务器。敏感数据建议使用本地 Ollama。

2. **成本考虑**: OpenAI/Claude 按 token 收费，大批量样本建议使用 Ollama。

3. **结果参考**: AI 分析结果仅供参考，关键结论请结合生物学背景知识判断。

4. **性能**: 本地模型（如 llama3.2）需要足够的内存（建议 8GB+）和显卡（可选，GPU 加速）。

## 技术细节

AI Curator 使用精心设计的提示词（prompt）引导模型：

1. **统计信息提取**: 自动计算注释覆盖率、可信度分布等
2. **结构化输出**: 要求模型返回 JSON 格式，便于解析
3. **多维度评估**: 从完整性、准确性、一致性等角度评价
4. **上下文理解**: 结合 KEGG 通路和 COG 分类进行解读

自定义提示词可修改 `scripts/ai_curator.py` 中的 `_build_analysis_prompt()` 方法。
