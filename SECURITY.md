# 安全指南 🔒

## API 密钥安全

本项目高度重视 API 密钥安全，实施了多层次的保护措施。

## 核心安全原则

### 1. 永远不要提交密钥到 Git

```bash
# 确保 .gitignore 包含以下内容
echo ".env" >> .gitignore
echo "*.log" >> .gitignore
echo "logs/" >> .gitignore
```

### 2. 优先使用环境变量

✅ **推荐** - 环境变量方式：
```bash
export AI_API_KEY="sk-your-key"
snakemake --use-conda --cores 8
```

❌ **禁止** - 明文配置文件：
```yaml
# config.yaml - 不要这样做！
ai:
  api_key: "sk-your-actual-key-here"
```

❌ **禁止** - 命令行参数：
```bash
# 会被记录在 shell 历史
snakemake --config ai.api_key="sk-your-key"
```

## 技术实现细节

### 配置解析层

`scripts/ai_curator.py` 实现了安全解析：

```python
# 如果 api_key 是全大写的环境变量名格式
if api_key.isupper() and '_' in api_key:
    # 从环境变量读取
    self.api_key = os.getenv(api_key)
    # 日志只显示来源，不显示内容
    logger.debug(f"从环境变量 {api_key} 读取 API key (长度: {len(env_value)})")
else:
    # 如果是明文 key，发出警告
    logger.warning("⚠️  API key 以明文形式传入，存在安全风险！")
```

### 规则执行层

`rules/ai_curator.smk` 实现了安全执行：

```python
# 在 run 指令中
if params.api_key.isupper() and '_' in params.api_key:
    # 环境变量名 - 脚本会自动从环境读取
    pass
else:
    # 如果是明文，设置为环境变量再执行
    env["AI_API_KEY"] = str(params.api_key)

# 使用 subprocess 执行，key 不会出现在进程参数中
subprocess.run(cmd, env=env)
```

## 安全检查清单

在运行带 AI 功能的分析前，确认：

- [ ] 配置文件中的 `api_key` 是环境变量名（如 `"AI_API_KEY"`），不是真实密钥
- [ ] `.gitignore` 包含 `.env` 和 `*.log`
- [ ] 环境变量已正确设置（`echo $AI_API_KEY` 能显示值）
- [ ] 日志文件不会被提交到 Git
- [ ] 不使用命令行参数传递密钥

## 发现安全问题

如果你发现代码中存在密钥泄露风险，请：

1. 立即撤销泄露的 API key
2. 更新配置文件使用环境变量方式
3. 清理 shell 历史（`history -c`）
4. 通知相关人员更换密钥

## 最佳实践

### 本地开发

使用本地 Ollama，无需 API key：

```bash
ollama pull llama3.2
export AI_PROVIDER=ollama
snakemake --use-conda --cores 8 --config ai.enabled=true
```

### 生产环境

使用专用的密钥管理服务（如 AWS Secrets Manager、HashiCorp Vault）：

```bash
# 从密钥管理服务获取
export AI_API_KEY=$(vault read -field=api_key secret/ai)
snakemake --use-conda --cores 8
```

### 团队协作

创建 `.env.example` 作为模板：

```bash
# .env.example - 提交到 Git，作为示例
AI_API_KEY=your-api-key-here
DASHSCOPE_API_KEY=your-dashscope-key-here
```

每个人创建自己的 `.env` 文件（不提交到 Git）：

```bash
# .env - 不提交到 Git
cp .env.example .env
# 编辑 .env 填入真实密钥
```

---

**记住：安全是每个人的责任。保护好你的 API key！**
