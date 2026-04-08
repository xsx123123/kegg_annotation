#!/usr/bin/env python3
# *---utf-8---*
"""
Reference Path Update Utilities
================================
Helper functions for resolving database paths to absolute paths.
"""

import os
from .resolve_db_paths import resolve_db_paths, check_db_paths

__all__ = ['resolve_db_paths', 'check_db_paths']
