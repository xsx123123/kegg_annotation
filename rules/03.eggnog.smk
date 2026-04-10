# =============================================================================
# EggNOG-Mapper Rules
# =============================================================================

rule eggnog_mapper:
    """
    Run eggnog-mapper for functional annotation.
    """
    input:
        get_input_file
    output:
        formatted = "01.eggnog/{sample}.eggnog_temp.fa",
        annotations = "01.eggnog/{sample}.emapper.annotations",
        seed_orthologs = "01.eggnog/{sample}.emapper.seed_orthologs",
        hits = "01.eggnog/{sample}.emapper.hits"
    conda:
        workflow.source_path("../env/eggnog-mapper.yaml")
    params:
        data_dir = EGGNOG_DATA_DIR,
        temp_dir = lambda wildcards: f"/tmp/emapper_{wildcards.sample}"
    threads:
        EGGNOG_CPU
    resources:
        **rule_resource(config, 'high_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/01.eggnog/{sample}_eggnog_mapper.log"
    benchmark:
        "benchmarks/01.eggnog/{sample}_eggnog_mapper.txt"
    message:
        "🧬 Running eggnog-mapper on {wildcards.sample}"
    shell:
        """
        mkdir -p {params.temp_dir}

        awk '/^>/{{print; next}} {{gsub(/[*]/,""); gsub(/[.]/,""); print}}' {input} > {output.formatted}
        
        mkdir -p 01.eggnog && \
        emapper.py \
            -i {output.formatted} \
            --data_dir {params.data_dir} \
            -o {wildcards.sample} \
            --output_dir 01.eggnog \
            --cpu {threads} \
            --temp_dir {params.temp_dir} \
            --override \
            > {log} 2>&1
        
        rm -rf {params.temp_dir}
        """

rule eggnog_processor:
    """
    Process eggnog results with quality filtering.
    """
    input:
        annotations = "01.eggnog/{sample}.emapper.annotations"
    output:
        formatted = "01.eggnog/{sample}_eggnog.tsv",
        high_conf = "01.eggnog/{sample}_eggnog_highconf.tsv",
        report = "01.eggnog/{sample}_eggnog_report.txt"
    conda:
        workflow.source_path("../env/python3.yaml")
    params:
        output_prefix = "01.eggnog/{sample}_eggnog",
        evalue = EVALUE_THRESHOLD,
        bitscore = BITSCORE_THRESHOLD,
        min_confidence = MIN_CONFIDENCE,
        require_kegg = "--require-kegg" if REQUIRE_KEGG else "",
        require_go = "--require-go" if REQUIRE_GO else "",
    resources:
        **rule_resource(config, 'default', skip_queue_on_local=True, logger=logger)
    log:
        "logs/01.eggnog/{sample}_eggnog_processor.log"
    benchmark:
        "benchmarks/01.eggnog/{sample}_eggnog_processor.txt"
    message:
        "🔬 Processing eggnog for {wildcards.sample}"
    shell:
        """
        chmod +x "{EGGNOG_PROCESSOR}" && \
        python3 "{EGGNOG_PROCESSOR}" \
            -i {input.annotations} \
            -o {params.output_prefix} \
            --evalue {params.evalue} \
            --bitscore {params.bitscore} \
            --min-confidence {params.min_confidence} \
            {params.require_kegg} \
            {params.require_go} \
            --log {log} \
            > {log} 2>&1
        """