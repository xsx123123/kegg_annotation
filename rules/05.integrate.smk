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
        eggnog = "01.eggnog/{sample}_eggnog.tsv",
        kofam = "02.kofam/{sample}_kofam.tsv"
    output:
        tsv = "03.merge/{sample}_integrated.tsv",
        report = "03.merge/{sample}_integrated_report.txt"
    conda:
        workflow.source_path("../env/python3.yaml"),
    resources:
        **rule_resource(config, 'low_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/03.merge/{sample}_integrate.log"
    benchmark:
        "benchmarks/03.merge/{sample}_integrate.txt"
    message:
        "🔗 Integrating annotations for {wildcards.sample}"
    shell:
        """
        chmod +x "{INTEGRATE_ANNOTATIONS}" && \
        mkdir -p 03.merge && \
        python3 "{INTEGRATE_ANNOTATIONS}" \
            -e {input.eggnog} \
            -k {input.kofam} \
            -s {wildcards.sample} \
            -o 03.merge/{wildcards.sample}_integrated \
            > {log} 2>&1
        """