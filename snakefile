#!/usr/bin/env python3
# *---utf-8---*
# Version: KEGG-Annotator v1.0.0
# Author: JZHANG
"""
KEGG Annotation Pipeline
========================
Integrated gene function annotation pipeline combining eggnog-mapper and KofamScan

Usage:
    Local:   snakemake --use-conda --cores 8
    Cluster: snakemake --use-conda --profile cluster_profile
    With AI: snakemake --use-conda --cores 8 --config ai.enabled=true
"""

import sys
import os
from snakemake.utils import min_version, validate

# ------- Import Custom Modules ------- #
from rules.utils.validate import load_user_config
from rules.utils.reference_update import resolve_db_paths
from rules.utils.resource_manager import rule_resource


# Lock Snakemake Version
min_version("9.9.0")


# --------- 1. Config Loading --------- #
# Load default configs from conf/ directory
configfile: "conf/config.yaml"
configfile: "conf/resource.yaml"
configfile: "conf/parameter.yaml"
configfile: "conf/ai.yaml"

# Load CLI argument config (Highest Priority)
load_user_config(config, cmd_arg_name='analysisyaml')


# --------- 2. Processing & Validation --------- #
# Update absolute paths for database directories
resolve_db_paths(config, base_path=config.get('dataset_dir'))

# Get logger instance for pipeline logging
from rules.utils.logger import get_pipeline_logger
logger = get_pipeline_logger()
logger.info("Configuration loaded and validated")


# --------- 3. Workspaces Setup --------- #
# Redirect workspace to config['workflow'] directory
workflow_dir = config.get("workflow", os.getcwd())
workdir: workflow_dir
logger.info(f"Redirect workspaces to {workflow_dir}")


# --------- 4. Rules Import --------- #
include: "rules/config.smk" # Global configuration definitions
include: "rules/common.smk" # Common utilities and helper functions
include: "rules/eggnog.smk" # eggnog-mapper annotation rules
include: "rules/kofamscan.smk" # KofamScan annotation rules
include: "rules/report.smk" # Report generation rules
include: "rules/integrate.smk" # Integrate eggnog + KofamScan with scoring
include: "rules/merge.smk" # Results merging rules
if AI_ENABLED:
    include: "rules/ai_curator.smk" # AI curator rules (optional, loaded only if ai.enabled=true)
# --------- 5. Pipeline Initialization --------- #
# Log pipeline startup information
logger.info("=" * 60)
logger.info("KEGG Annotation Pipeline Started")
logger.info("=" * 60)
logger.info(f"Working directory: {workflow_dir}")
logger.info(f"Samples: {SAMPLES}")
logger.info(f"Input directory: {INPUT_DIR}")
logger.info(f"Output directory: {OUTPUT_DIR}")
if AI_ENABLED:
    logger.info(f"AI Analysis: Enabled ({AI_CONFIG.get('provider', 'unknown')}/{AI_CONFIG.get('model', 'unknown')})")
logger.info("=" * 60)


# --------- 6. Target Rules --------- #
# Default target: run all analysis steps
rule all:
    """
    Default target rule - generates all outputs for all samples.
    
    This rule serves as the primary entry point for the pipeline.
    Running 'snakemake' without specifying a target will execute this rule.
    
    Outputs:
        - Per-sample eggnog annotations (formatted + high confidence)
        - Per-sample KofamScan annotations (formatted + high confidence)
        - Per-sample summary reports
        - Merged results (if multiple samples)
        - Multi-sample summary report (if multiple samples)
        - AI analysis reports (if AI is enabled)
    """
    input:
        get_all_outputs()
    message:
        "✅ Pipeline complete! All outputs generated."


# Target: annotation only (skip merging and AI)
rule annotate:
    """
    Target rule for annotation only (skip merging and AI analysis).
    
    Use this target to run annotation for all samples without
    generating merged summary files:
        snakemake --use-conda annotate
    """
    input:
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_eggnog.tsv", sample=SAMPLES),
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_kofam.tsv", sample=SAMPLES)
    message:
        "✅ Annotation complete for all samples"


# Target: generate summary reports
rule reports:
    """
    Target rule for generating all reports.
    
    Generates summary reports for all samples:
        snakemake --use-conda reports
    """
    input:
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_summary.txt", sample=SAMPLES)
    message:
        "✅ Reports generated for all samples"


# Target: AI-powered analysis (requires ai.enabled=true)
rule ai_analysis:
    """
    Target rule for AI-powered annotation analysis.
    
    Requires AI to be enabled in config (ai.enabled: true).
    Generates AI-curated reports for each sample:
        snakemake --use-conda --config ai.enabled=true ai_analysis
    """
    input:
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_ai_report.md", sample=SAMPLES) if AI_ENABLED else []
    message:
        "🤖 AI analysis complete!"


# Target: merge results from multiple samples
rule merge:
    """
    Target rule for merging results from all samples.
    
    Always generates merged outputs in merged/ directory:
        snakemake --use-conda merge
    """
    input:
        "merged/eggnog_all_samples.tsv",
        "merged/kofam_all_samples.tsv",
        "merged/SUMMARY_REPORT.txt"
    message:
        "✅ Results merged successfully"
