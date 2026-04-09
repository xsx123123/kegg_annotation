#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# AI Curator Rules
# =============================================================================
# 使用 AI 对注释结果进行智能分析和校正
# =============================================================================

# 导入必要的模块（在文件顶部导入，避免在 run 中重复导入）
import os
import subprocess
import json
import shutil


rule ai_annotation_curator:
    """
    使用 AI 对注释结果进行智能分析和解读。
    
    该规则会调用 AI 模型（默认使用本地 Ollama）对 eggnog 和 KofamScan 
    的注释结果进行综合分析，生成质量评估和功能摘要。
    """
    input:
        eggnog = "01.eggnog/{sample}_eggnog.tsv",
        kofam = "02.kofam/{sample}_kofam.tsv"
    output:
        report = "04.ai/{sample}_ai_report.md",
        json = "04.ai/{sample}_ai_analysis.json"
    params:
        provider = lambda wc: config.get("ai", {}).get("provider", "ollama"),
        model = lambda wc: config.get("ai", {}).get("model", "llama3.2"),
        api_key = lambda wc: config.get("ai", {}).get("api_key", ""),
        api_base = lambda wc: config.get("ai", {}).get("api_base", ""),
        taxonomy = lambda wc: config.get("ai", {}).get("taxonomy", "Unknown"),
        max_proteins = lambda wc: config.get("ai", {}).get("max_proteins", 50),
        # 将脚本路径作为参数传递
        ai_curator_script = AI_CURATOR
    conda:
        workflow.source_path("../env/openai.yaml")
    log:
        "logs/04.ai/{sample}_ai_curator.log"
    benchmark:
        "benchmarks/04.ai/{sample}_ai_curator.txt"
    message:
        "🤖 Running AI analysis on {wildcards.sample}"
    shell:
        """
        # 构建基础命令
        CMD="python3 {params.ai_curator_script} -e {input.eggnog} -k {input.kofam} -s {wildcards.sample} -o {output.report} --output-json {output.json} --provider {params.provider} --model {params.model} --taxonomy '{params.taxonomy}' --max-proteins {params.max_proteins}"
        
        # 追加 API key 和 API base 参数
        if [ -n "{params.api_key}" ]; then
            CMD="$CMD --api-key '{params.api_key}'"
            if ! echo "{params.api_key}" | grep -qE '^[A-Z_]+$'; then
                export AI_API_KEY="{params.api_key}"
            fi
        fi
        if [ -n "{params.api_base}" ]; then
            CMD="$CMD --api-base '{params.api_base}'"
            if ! echo "{params.api_base}" | grep -qE '^[A-Z_]+$'; then
                export AI_API_BASE="{params.api_base}"
            fi
        fi
        
        # 执行命令
        eval $CMD > {log} 2>&1
        """


rule ai_multi_sample_summary:
    """
    对多样本进行 AI 汇总分析。
    
    比较多个样本的注释结果，识别共性和差异。
    """
    input:
        ai_reports = expand("04.ai/{sample}_ai_report.md", sample=SAMPLES) if AI_ENABLED else [],
        eggnog_merged = "03.merge/eggnog_all_samples.tsv" if len(SAMPLES) > 1 and AI_ENABLED else [],
        kofam_merged = "03.merge/kofam_all_samples.tsv" if len(SAMPLES) > 1 and AI_ENABLED else []
    output:
        summary = "04.ai/AI_MULTI_SAMPLE_SUMMARY.md"
    params:
        samples = " ".join(SAMPLES),
        n_samples = len(SAMPLES),
        first_sample = SAMPLES[0] if SAMPLES else "",
        first_report = f"04.ai/{SAMPLES[0]}_ai_report.md" if SAMPLES else "",
        provider = lambda wc: config.get("ai", {}).get("provider", "ollama"),
        model = lambda wc: config.get("ai", {}).get("model", "llama3.2")
    conda:
        workflow.source_path("../env/openai.yaml")
    log:
        "logs/04.ai/ai_multi_sample_summary.log"
    benchmark:
        "benchmarks/04.ai/ai_multi_sample_summary.txt"
    message:
        "🤖 Generating multi-sample AI summary"
    shell:
        """
        if [ {params.n_samples} -eq 1 ]; then
            # 单样本，复制报告
            if [ -f "{params.first_report}" ]; then
                cp "{params.first_report}" "{output.summary}"
            else
                echo "# AI Analysis Summary\n\nSample: {params.first_sample}\n" > "{output.summary}"
            fi
        else
            # 多样本，创建汇总
            cat > "{output.summary}" << 'EOF'
# AI Multi-Sample Summary

Samples analyzed: {params.n_samples}
Samples: {params.samples}

## Individual Reports

EOF
            for report in {input.ai_reports}; do
                echo "- $report" >> "{output.summary}"
            done
        fi
        """


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
            print("✅ Ollama 服务检测正常")
            return True
        except:
            print("⚠️  Ollama 服务未检测到，AI 分析将跳过或失败")
            print("   如需使用 AI 功能，请安装并启动 Ollama:")
            print("   curl -fsSL https://ollama.com/install.sh | sh")
            print("   ollama pull llama3.2")
            return False
    
    elif provider in ["openai", "claude"]:
        api_key = ai_config.get("api_key") or os.environ.get("AI_API_KEY")
        if not api_key:
            print(f"⚠️  未检测到 {provider} API 密钥，AI 分析将跳过")
            print("   请设置环境变量 AI_API_KEY 或在配置中添加 api_key")
            return False
        return True
    
    return False
