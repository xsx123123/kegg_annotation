#!/usr/bin/env python3
# *---utf-8---*
"""
Pipeline Logger Utility
=======================
Unified logging interface for KEGG Annotation Pipeline.
Supports rich-loguru, standard loguru, and builtin logging.
"""

import sys
import os

# Try to import rich-loguru (custom plugin)
try:
    from snakemake_logger_plugin_rich_loguru import get_analysis_logger
    
    def get_pipeline_logger():
        """Get the analysis logger instance."""
        return get_analysis_logger()
    
    HAS_RICH_LOGURU = True

except ImportError:
    # Fall back to standard loguru
    try:
        from loguru import logger
        
        def get_pipeline_logger():
            """Get the loguru logger instance."""
            logger.remove()  # Remove default handler
            logger.add(
                sys.stderr,
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
            )
            return logger
        
        HAS_RICH_LOGURU = False
    
    except ImportError:
        # Fall back to builtin logging
        import logging
        
        def get_pipeline_logger():
            """Get the builtin logger instance."""
            logger = logging.getLogger('kegg_annotation')
            logger.setLevel(logging.INFO)
            
            if not logger.handlers:
                handler = logging.StreamHandler(sys.stderr)
                handler.setLevel(logging.INFO)
                formatter = logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(message)s',
                    datefmt='%H:%M:%S'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            
            return logger
        
        HAS_RICH_LOGURU = False


# Export the function
__all__ = ['get_pipeline_logger', 'HAS_RICH_LOGURU']
