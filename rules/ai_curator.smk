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
        provider = lambda wc: config.get("ai", {}).get("provider", "ollama"),
        model = lambda wc: config.get("ai", {}).get("model", "llama3.2"),
        api_key = lambda wc: config.get("ai", {}).get("api_key", ""),
        api_base = lambda wc: config.get("ai", {}).get("api_base", "")
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
    run:
        # 构建命令参数
        cmd = [
            "python3", str(AI_CURATOR),
            "-e", str(input.eggnog),
            "-k", str(input.kofam),
            "-s", str(wildcards.sample),
            "-o", str(output.report),
            "--provider", str(params.provider),
            "--model", str(params.model)
        ]
        
        # 添加可选参数
        if params.api_key:
            cmd.extend(["--api-key", str(params.api_key)])
        if params.api_base:
            cmd.extend(["--api-base", str(params.api_base)])
        
        # 执行命令
        import subprocess
        with open(str(log), 'w') as log_fh:
            result = subprocess.run(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True
            )
            if result.returncode != 0:
                raise Exception(f"AI curator failed with return code {result.returncode}")
        
        # 生成 JSON 输出
        import json
        result_data = {
            'sample': wildcards.sample,
            'provider': params.provider,
            'model': params.model,
            'status': 'completed'
        }
        with open(str(output.json), 'w') as f:
            json.dump(result_data, f, indent=2)


rule ai_multi_sample_summary:
    """
    对多样本进行 AI 汇总分析。
    
    比较多个样本的注释结果，识别共性和差异。
    """
    input:
        ai_reports = expand("{sample}/{sample}_ai_report.md", sample=SAMPLES) if AI_ENABLED else [],
        eggnog_merged = "merged/eggnog_all_samples.tsv" if len(SAMPLES) > 1 and AI_ENABLED else [],
        kofam_merged = "merged/kofam_all_samples.tsv" if len(SAMPLES) > 1 and AI_ENABLED else []
    output:
        summary = "merged/AI_MULTI_SAMPLE_SUMMARY.md"
    params:
        samples = " ".join(SAMPLES),
        provider = lambda wc: config.get("ai", {}).get("provider", "ollama"),
        model = lambda wc: config.get("ai", {}).get("model", "llama3.2")
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
            import shutil
            if len(input.ai_reports) > 0:
                shutil.copy(str(input.ai_reports[0]), str(output.summary))
            else:
                with open(str(output.summary), 'w') as f:
                    f.write(f"# AI Analysis Summary\n\nSample: {SAMPLES[0]}\n")
        else:
            # 多样本分析 - 创建简单的汇总
            with open(str(output.summary), 'w') as f:
                f.write("# AI Multi-Sample Summary\n\n")
                f.write(f"Samples analyzed: {len(SAMPLES)}\n")
                f.write(f"Samples: {', '.join(SAMPLES)}\n\n")
                f.write("## Individual Reports\n\n")
                for report in input.ai_reports:
                    f.write(f"- {report}\n")


# =============================================================================
# AI 配置检查（可选）
# =============================================================================

def check_ai_config():
    """检查 AI 配置是否有效"""
    ai_config = config.get("ai", {})
    provider = ai_config.get("provider", "ollama")
    
    if provider == "ollama":
        # 检查 Ollama 是否运行
        try:
            import urllib.request
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
