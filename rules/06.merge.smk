# =============================================================================
# Merge Results Rules
# =============================================================================

rule merge_eggnog_results:
    """
    Merge eggnog results from all samples.
    """
    input:
        expand("01.eggnog/{sample}_eggnog.tsv", sample=SAMPLES)
    output:
        all_samples = "03.merge/eggnog_all_samples.tsv",
        high_conf = "03.merge/eggnog_highconf.tsv",
        stats = "03.merge/eggnog_stats.txt"
    params:
        samples = " ".join(SAMPLES),
    conda:
        workflow.source_path("../env/python3.yaml")
    resources:
        **rule_resource(config, 'default', skip_queue_on_local=True, logger=logger)
    log:
        "logs/03.merge/merge_eggnog.log"
    benchmark:
        "benchmarks/03.merge/merge_eggnog.txt"
    message:
        "📦 Merging eggnog results | {params.samples}"
    shell:
        """
        mkdir -p 03.merge && \
        chmod +x "{MERGE_RESULTS}" && \
        python3 "{MERGE_RESULTS}" \
            --input-dir 01.eggnog \
            --samples {params.samples} \
            --tool eggnog \
            --output-all {output.all_samples} \
            --output-high {output.high_conf} \
            --output-stats {output.stats} \
            > {log} 2>&1
        """

rule merge_kofam_results:
    """
    Merge KofamScan results from all samples.
    """
    input:
        expand("02.kofam/{sample}_kofam.tsv", sample=SAMPLES)
    output:
        all_samples = "03.merge/kofam_all_samples.tsv",
        high_conf = "03.merge/kofam_highconf.tsv",
        stats = "03.merge/kofam_stats.txt"
    params:
        samples = " ".join(SAMPLES),
    conda:
        workflow.source_path("../env/python3.yaml")
    resources:
        **rule_resource(config, 'default', skip_queue_on_local=True, logger=logger)
    log:
        "logs/03.merge/merge_kofam.log"
    benchmark:
        "benchmarks/03.merge/merge_kofam.txt"
    message:
        "📦 Merging KofamScan results | {params.samples}"
    shell:
        """
        mkdir -p 03.merge && \
        chmod +x "{MERGE_RESULTS}" && \
        python3 "{MERGE_RESULTS}" \
            --input-dir 02.kofam \
            --samples {params.samples} \
            --tool kofam \
            --output-all {output.all_samples} \
            --output-high {output.high_conf} \
            --output-stats {output.stats} \
            > {log} 2>&1
        """

rule merge_summary_report:
    """
    Generate comprehensive summary report.
    """
    input:
        eggnog_stats = "03.merge/eggnog_stats.txt",
        kofam_stats = "03.merge/kofam_stats.txt"
    output:
        report = "03.merge/SUMMARY_REPORT.txt"
    params:
        samples = " ".join(SAMPLES)
    resources:
        **rule_resource(config, 'low_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/03.merge/merge_summary.log"
    benchmark:
        "benchmarks/03.merge/merge_summary.txt"
    message:
        "📝 Generating summary report"
    shell:
        """
        cat > {output.report} << EOF
================================================================================
KEGG Annotation Pipeline - Summary Report
================================================================================
Date: $(date '+%Y-%m-%d %H:%M:%S')
Samples: {params.samples}
================================================================================

eggnog-mapper Statistics:
EOF

        cat {input.eggnog_stats} >> {output.report}
        
        echo "" >> {output.report}
        echo "KofamScan Statistics:" >> {output.report}
        cat {input.kofam_stats} >> {output.report}
        
        echo "" >> {output.report}
        echo "================================================================================" >> {output.report}
        echo "Output Files:" >> {output.report}
        echo "  - 03.merge/eggnog_all_samples.tsv" >> {output.report}
        echo "  - 03.merge/kofam_all_samples.tsv" >> {output.report}
        echo "================================================================================" >> {output.report}
        """
