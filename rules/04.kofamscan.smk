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
        formatted = "02.kofam/{sample}_kofam_temp.fa",
        detail = "02.kofam/{sample}_kofam_detail.txt",
        tsv = "02.kofam/{sample}_kofam_raw.tsv"
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
        "logs/02.kofam/{sample}_kofamscan.log"
    benchmark:
        "benchmarks/02.kofam/{sample}_kofamscan.txt"
    message:
        "🎯 Running KofamScan on {wildcards.sample}"
    shell:
        """
        mkdir -p {params.tmp_dir}

        awk '/^>/{{print; next}} {{gsub(/[*]/,""); gsub(/[.]/,""); print}}' {input} > {output.formatted}
        
        exec_annotation \
            -o {output.detail} \
            --ko-list {params.ko_list} \
            --profile {params.profiles} \
            --cpu {threads} \
            --tmp-dir {params.tmp_dir} \
            -f detail \
            {output.formatted} \
            > {log} 2>&1
        
        exec_annotation \
            -o {output.tsv} \
            --ko-list {params.ko_list} \
            --profile {params.profiles} \
            --cpu {threads} \
            --tmp-dir {params.tmp_dir} \
            -f mapper \
            {output.formatted} \
            >> {log} 2>&1
        
        rm -rf {params.tmp_dir}
        """

rule kofamscan_processor:
    """
    Process KofamScan results with confidence assessment.
    """
    input:
        detail = "02.kofam/{sample}_kofam_detail.txt",
        eggnog_annotations = "01.eggnog/{sample}.emapper.annotations"
    output:
        formatted = "02.kofam/{sample}_kofam.tsv",
        high_conf = "02.kofam/{sample}_kofam_highconf.tsv",
        report = "02.kofam/{sample}_kofam_report.txt"
    conda:
        workflow.source_path("../env/python3.yaml")
    params:
        output_prefix = "02.kofam/{sample}_kofam",
        min_confidence = MIN_CONFIDENCE
    resources:
        **rule_resource(config, 'default', skip_queue_on_local=True, logger=logger)
    log:
        "logs/02.kofam/{sample}_kofam_processor.log"
    benchmark:
        "benchmarks/02.kofam/{sample}_kofam_processor.txt"
    message:
        "📊 Processing KofamScan for {wildcards.sample}"
    shell:
        """
        chmod +x "{KOFAMSCAN_PROCESSOR}" && \
        python3 "{KOFAMSCAN_PROCESSOR}" \
            -i {input.detail} \
            -o {params.output_prefix} \
            -e {input.eggnog_annotations} \
            --min-confidence {params.min_confidence} \
            --log {log} \
            > {log} 2>&1
        """
