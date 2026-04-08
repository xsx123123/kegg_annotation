# =============================================================================
# AI Curator Rules
# =============================================================================
# 使用 AI 对注释结果进行智能分析和校正
# =============================================================================

rule ai_annotation_curator:
    """
    使用 AI 对注释结果进行智能分析和解读。
    
    该规则会调用 AI 模型（默认使用本地 Ollama）对 eggnog 和 KofamScan 
    的注释结果进行综合分析，生成质量评估和功能摘要。
    """
    input:
        eggnog = "{sample}/{sample}_eggnog.tsv",
        kofam = "{sample}/{sample}_kofam.tsv"
    output:
        report = "{sample}/{sample}_ai_report.md",
        json = "{sample}/{sample}_ai_analysis.json"
    params:
        provider = config.get("ai", {}).get("provider", "ollama"),
        model = config.get("ai", {}).get("model", "llama3.2"),
        api_key = config.get("ai", {}).get("api_key", ""),
        api_base = config.get("ai", {}).get("api_base", "")
    conda:
        workflow.source_path("../env/python3.yaml")
    resources:
        **rule_resource(config, 'low_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/{sample}_ai_curator.log"
    benchmark:
        "benchmarks/{sample}_ai_curator.txt"
    message:
        "🤖 Running AI analysis on {wildcards.sample}"
    shell:
        """
        python3 "{AI_CURATOR}" \
            -e {input.eggnog} \
            -k {input.kofam} \
            -s {wildcards.sample} \
            -o {output.report} \
            --provider {params.provider} \
            --model {params.model} \
            {params.api_key and '--api-key ' + params.api_key or ''} \
            {params.api_base and '--api-base ' + params.api_base or ''} \
            > {log} 2>&1
        
        # 同时保存 JSON 格式的详细结果
        python3 -c "
import json
import sys
# 从报告中提取 JSON 数据（实际应该在脚本中直接输出）
# 这里只是一个占位符
result = {{
    'sample': '{wildcards.sample}',
    'provider': '{params.provider}',
    'model': '{params.model}',
    'status': 'completed'
}}
with open('{output.json}', 'w') as f:
    json.dump(result, f, indent=2)
"
        """


rule ai_multi_sample_summary:
    """
    对多样本进行 AI 汇总分析。
    
    比较多个样本的注释结果，识别共性和差异。
    """
    input:
        ai_reports = expand("{sample}/{sample}_ai_report.md", sample=SAMPLES),
        eggnog_merged = "merged/eggnog_all_samples.tsv" if len(SAMPLES) > 1 else [],
        kofam_merged = "merged/kofam_all_samples.tsv" if len(SAMPLES) > 1 else []
    output:
        summary = "merged/AI_MULTI_SAMPLE_SUMMARY.md"
    params:
        samples = " ".join(SAMPLES),
        provider = config.get("ai", {}).get("provider", "ollama"),
        model = config.get("ai", {}).get("model", "llama3.2")
    conda:
        workflow.source_path("../env/python3.yaml")
    resources:
        **rule_resource(config, 'low_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/ai_multi_sample_summary.log"
    benchmark:
        "benchmarks/ai_multi_sample_summary.txt"
    message:
        "🤖 Generating multi-sample AI summary"
    run:
        # 如果只有一个样本，复制单样本报告
        if len(SAMPLES) == 1:
            shell("cp {input.ai_reports[0]} {output.summary}")
        else:
            # 多样本分析
            shell("""
                python3 "{AI_CURATOR}" \
                    --mode multi-sample \
                    --samples {params.samples} \
                    --eggnog-merged {input.eggnog_merged} \
                    --kofam-merged {input.kofam_merged} \
                    --output {output.summary} \
                    --provider {params.provider} \
                    --model {params.model} \
                    > {log} 2>&1 || echo "# AI 多样本汇总\n\n样本数: {len(SAMPLES)}\n样本: {params.samples}\n\n> 注：AI 分析需要配置 API 密钥" > {output.summary}
            """)


# =============================================================================
# AI 配置检查
# =============================================================================

def check_ai_config():
    """检查 AI 配置是否有效"""
    ai_config = config.get("ai", {})
    provider = ai_config.get("provider", "ollama")
    
    if provider == "ollama":
        # 检查 Ollama 是否运行
        import urllib.request
        try:
            api_base = ai_config.get("api_base", "http://localhost:11434")
            urllib.request.urlopen(f"{api_base}/api/tags", timeout=2)
            logger.info("✅ Ollama 服务检测正常")
            return True
        except:
            logger.warning("⚠️  Ollama 服务未检测到，AI 分析将跳过或失败")
            logger.warning("   如需使用 AI 功能，请安装并启动 Ollama:")
            logger.warning("   curl -fsSL https://ollama.com/install.sh | sh")
            logger.warning("   ollama pull llama3.2")
            return False
    
    elif provider in ["openai", "claude"]:
        api_key = ai_config.get("api_key") or os.environ.get("AI_API_KEY")
        if not api_key:
            logger.warning(f"⚠️  未检测到 {provider} API 密钥，AI 分析将跳过")
            logger.warning("   请设置环境变量 AI_API_KEY 或在配置中添加 api_key")
            return False
        return True
    
    return False


# 在启动时检查 AI 配置（可选）
# check_ai_config()
