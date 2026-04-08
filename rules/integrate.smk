# =============================================================================
# Integrate eggnog + KofamScan annotations with scoring system
# =============================================================================
# 对每个样本，将 eggnog 和 KofamScan 的结果横向整合，并计算综合评分
# =============================================================================

rule integrate_annotations:
    """
    整合 eggnog 和 KofamScan 注释结果，生成统一评分。
    """
    input:
        eggnog = "{sample}/{sample}_eggnog.tsv",
        kofam = "{sample}/{sample}_kofam.tsv"
    output:
        tsv = "{sample}/{sample}_integrated.tsv",
        report = "{sample}/{sample}_integrated_report.txt"
    conda:
        workflow.source_path("../env/python3.yaml"),
    resources:
        **rule_resource(config, 'low_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/{sample}_integrate.log"
    benchmark:
        "benchmarks/{sample}_integrate.txt"
    message:
        "🔗 Integrating annotations for {wildcards.sample}"
    shell:
        """
        chmod +x "{INTEGRATE_ANNOTATIONS}" && \
        python3 "{INTEGRATE_ANNOTATIONS}" \
            -e {input.eggnog} \
            -k {input.kofam} \
            -s {wildcards.sample} \
            -o {wildcards.sample}/{wildcards.sample} \
            > {log} 2>&1
        """