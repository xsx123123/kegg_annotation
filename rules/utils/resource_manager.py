#!/usr/bin/env python3
# *---utf-8---*
"""
Resource Management Utilities
==============================
Helper functions for managing computational resources in different execution environments.
"""

import os


def rule_resource(config, resource_type='default', skip_queue_on_local=False, logger=None):
    """
    根据运行环境返回资源配置
    
    从 conf/resource.yaml 读取 resource_presets 配置，如果没有则使用默认值
    
    Args:
        config: Snakemake配置字典
        resource_type: 资源类型 (default, high_resource, low_resource)
        skip_queue_on_local: 本地运行时是否跳过队列
        logger: 日志记录器
    
    Returns:
        dict: 资源配置字典
    """
    # 默认资源配置
    default_presets = {
        'default': {
            'mem_gb': 8,
            'runtime': 60,
        },
        'high_resource': {
            'mem_gb': 32,
            'runtime': 240,
        },
        'low_resource': {
            'mem_gb': 4,
            'runtime': 30,
        }
    }
    
    # 从配置中读取 resource_presets
    resource_presets = config.get('resource_presets', default_presets)
    
    # 获取指定类型的资源
    resource = resource_presets.get(
        resource_type, 
        resource_presets.get('default', default_presets['default'])
    ).copy()
    
    # 检查是否在集群环境运行
    execution_config = config.get('execution', {})
    is_cluster = execution_config.get('environment', 'local') == 'cluster'
    
    if is_cluster:
        resource['queue'] = execution_config.get('queue', 'normal')
    elif skip_queue_on_local:
        pass
    
    if logger:
        logger.debug(f"Resource allocation: {resource_type} -> {resource}")
    
    return resource


__all__ = ['rule_resource']
