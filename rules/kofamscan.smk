# =============================================================================
# KofamScan Rules
# =============================================================================

rule kofamscan:
    """
    Run KofamScan for KO annotation.
    """
    input:
        get_input_file
    output:
        detail = "{sample}/kofam/{sample}_kofam_detail.txt",
        tsv = "{sample}/kofam/{sample}_kofam_raw.tsv"
    conda:
        workflow.source_path("../env/kofamscan.yaml")
    params:
        ko_list = KOFAM_KO_LIST,
        profiles = KOFAM_PROFILES,
        tmp_dir = lambda wildcards: f"/tmp/kofam_{wildcards.sample}"
    threads:
        KOFAM_CPU
    resources:
        **rule_resource(config, 'high_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/{sample}_kofamscan.log"
    benchmark:
        "benchmarks/{sample}_kofamscan.txt"
    message:
        "🎯 Running KofamScan on {wildcards.sample}"
    shell:
        """
        mkdir -p {params.tmp_dir}
        
        exec_annotation \
            -o {output.detail} \
            --ko-list {params.ko_list} \
            --profile {params.profiles} \
            --cpu {threads} \
            --tmp-dir {params.tmp_dir} \
            -f detail \
            {input} \
            > {log} 2>&1
        
        exec_annotation \
            -o {output.tsv} \
            --ko-list {params.ko_list} \
            --profile {params.profiles} \
            --cpu {threads} \
            --tmp-dir {params.tmp_dir} \
            -f mapper \
            {input} \
            >> {log} 2>&1
        
        rm -rf {params.tmp_dir}
        """

rule kofamscan_processor:
    """
    Process KofamScan results with confidence assessment.
    """
    input:
        detail = "{sample}/kofam/{sample}_kofam_detail.txt",
        eggnog_annotations = "{sample}/eggnog/{sample}.emapper.annotations"
    output:
        formatted = "{sample}/{sample}_kofam.tsv",
        high_conf = "{sample}/{sample}_kofam_highconf.tsv",
        report = "{sample}/{sample}_kofam_report.txt"
    conda:
        workflow.source_path("../env/python3.yaml")
    params:
        output_prefix = "{sample}/{sample}_kofam",
        min_confidence = MIN_CONFIDENCE
    resources:
        **rule_resource(config, 'default', skip_queue_on_local=True, logger=logger)
    log:
        "logs/{sample}_kofam_processor.log"
    benchmark:
        "benchmarks/{sample}_kofam_processor.txt"
    message:
        "📊 Processing KofamScan for {wildcards.sample}"
    shell:
        """
        python3 scripts/KofamScan_processor.py \
            -i {input.detail} \
            -o {params.output_prefix} \
            -e {input.eggnog_annotations} \
            --min-confidence {params.min_confidence} \
            > {log} 2>&1
        
        mv {params.output_prefix}_report.txt {output.report} 2>/dev/null || true
        """
