# =============================================================================
# KEGG Annotation Pipeline
# =============================================================================
# Integrated gene function annotation pipeline combining eggnog-mapper and KofamScan
#
# Usage:
#   Local:   snakemake --use-conda --cores 8
#   Cluster: snakemake --use-conda --profile cluster_profile
# =============================================================================

import sys
import os
import yaml
from snakemake.utils import min_version, validate
from pathlib import Path


# =============================================================================
# Utility Functions (defined before use)
# =============================================================================

def load_user_config(config, cmd_arg_name="user_yaml") -> None:
    """
    Parse the configuration file path passed from the command line and merge it into the current config.

    Args:
        config (dict): Snakemake's global config object
        cmd_arg_name (str): The key name after --config in command line, defaults to "user_yaml"
    """
    custom_path = config.get(cmd_arg_name)

    # If the user didn't pass this parameter, return directly and use the default configuration
    if not custom_path:
        return

    # Check if the file exists
    if not os.path.exists(custom_path):
        print(f"\n\033[91m[Config Error] Cannot find the specified user configuration file: {custom_path}\033[0m\nPlease check if the path is correct.\n", file=sys.stderr)
        sys.exit(1)

    # Load and merge configuration
    print(f"\033[92m[Config Info] Loading external project configuration: {custom_path}\033[0m")
    
    try:
        with open(custom_path, 'r') as f:
            custom_data = yaml.safe_load(f)
        
        if custom_data:
            # Core step: recursively merge dictionaries
            def update_config(base, update):
                for key, value in update.items():
                    if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                        update_config(base[key], value)
                    else:
                        base[key] = value
            
            update_config(config, custom_data)
        else:
            print(f"[Config Warning] File {custom_path} is empty, skipping loading.")

    except Exception as e:
        sys.exit(f"\n[Config Error] Failed to parse YAML file: {e}\n")


# =============================================================================
# Version Lock
# =============================================================================
min_version("9.9.0")


# =============================================================================
# Load Configuration
# =============================================================================

# Load default configuration (if exists)
if os.path.exists("conf/config.yaml"):
    configfile: "conf/config.yaml"


# Load user-provided configuration via --config analysisyaml=/path/to/config.yaml
load_user_config(config, cmd_arg_name='analysisyaml')


# =============================================================================
# Setup Working Directory
# =============================================================================
# Redirect workspaces to user-specified workflow directory
# This enables separation of analysis code and working directory

workflow_dir = config.get("workflow", os.getcwd())
workdir: workflow_dir


# =============================================================================
# Resolve Database Paths
# =============================================================================
# Convert relative database paths to absolute paths based on dataset_dir

from rules.utils import resolve_db_paths

resolve_db_paths(config)


# =============================================================================
# Import Sub-rules
# =============================================================================

# Global configuration definitions
include: "rules/config.smk"

# Common utilities, helper functions, and logger setup
include: "rules/common.smk"

# eggnog-mapper annotation and processing rules
include: "rules/eggnog.smk"

# KofamScan annotation and processing rules
include: "rules/kofamscan.smk"

# Report generation rules
include: "rules/report.smk"

# Merge results rules
include: "rules/merge.smk"


# =============================================================================
# Logger Setup (Post-workdir)
# =============================================================================
# Log the workdir redirect after setup

logger.info("=" * 70)
logger.info("KEGG Annotation Pipeline Started")
logger.info("=" * 70)
logger.info(f"Working directory: {workflow_dir}")
logger.info(f"Samples: {SAMPLES}")
logger.info(f"Input directory: {INPUT_DIR}")
logger.info(f"Output directory: {OUTPUT_DIR}")
logger.info("=" * 70)


# =============================================================================
# Target Rules
# =============================================================================

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
    """
    input:
        get_all_outputs()
    message:
        "✅ Pipeline complete! All outputs generated."


rule annotate:
    """
    Target rule for annotation only (skip merging).
    
    Use this target to run annotation for all samples without
    generating merged summary files:
        snakemake --use-conda annotate
    """
    input:
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_eggnog_formatted.tsv", sample=SAMPLES),
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_kofam_formatted.tsv", sample=SAMPLES)
    message:
        "✅ Annotation complete for all samples"


rule reports:
    """
    Target rule for generating all reports.
    
    Generates summary reports for all samples:
        snakemake --use-conda reports
    """
    input:
        expand(f"{OUTPUT_DIR}/{{sample}}/{{sample}}_annotation_summary.txt", sample=SAMPLES)
    message:
        "✅ Reports generated for all samples"
