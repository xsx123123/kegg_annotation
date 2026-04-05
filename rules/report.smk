# =============================================================================
# Report Generation Rules
# =============================================================================

rule annotation_summary:
    """
    Generate annotation summary for a single sample.
    """
    input:
        eggnog_formatted = "{sample}/{sample}_eggnog.tsv",
        eggnog_high_conf = "{sample}/{sample}_eggnog_highconf.tsv",
        kofam_formatted = "{sample}/{sample}_kofam.tsv",
        kofam_high_conf = "{sample}/{sample}_kofam_highconf.tsv"
    output:
        summary = "{sample}/{sample}_summary.txt"
    resources:
        **rule_resource(config, 'low_resource', skip_queue_on_local=True, logger=logger)
    log:
        "logs/{sample}_summary.log"
    benchmark:
        "benchmarks/{sample}_summary.txt"
    message:
        "📝 Generating summary for {wildcards.sample}"
    shell:
        """
        cat > {output.summary} << EOF
================================================================================
Sample: {wildcards.sample}
Date: $(date '+%Y-%m-%d %H:%M:%S')
================================================================================

【eggnog-mapper】
EOF

        total=$(tail -n +14 {input.eggnog_formatted} | grep -v '^#' | wc -l)
        high=$(tail -n +2 {input.eggnog_high_conf} | grep -v '^#' | wc -l)
        
        echo "  Total: $total" >> {output.summary}
        echo "  High confidence: $high" >> {output.summary}
        
        kofam_total=$(tail -n +2 {input.kofam_formatted} | grep -v '^#' | wc -l)
        kofam_high=$(tail -n +2 {input.kofam_high_conf} | grep -v '^#' | wc -l)
        
        echo "" >> {output.summary}
        echo "【KofamScan】" >> {output.summary}
        echo "  Total: $kofam_total" >> {output.summary}
        echo "  High confidence: $kofam_high" >> {output.summary}
        
        echo "" >> {output.summary}
        echo "================================================================================" >> {output.summary}
        """
