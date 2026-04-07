#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析并更新 KEGG 注释流程中数据库的绝对路径。

这个函数用于将 config.yaml 中的相对路径转换为绝对路径，
基于 dataset_dir 配置项作为根目录。
"""

import os


def resolve_db_paths(config, base_path=None):
    """
    解析并更新 KEGG 注释流程中数据库的绝对路径。

    Args:
        config (dict): Snakemake 的配置字典
        base_path (str, optional): 数据库的根目录路径 (dataset_dir)。
                                   如果不传，默认尝试从 config['dataset_dir'] 获取。

    Returns:
        dict: 更新后的配置字典（原地修改，返回同一对象）
    
    Example:
        >>> config = {
        ...     'dataset_dir': '/path/to/datasets',
        ...     'eggnog_data_dir': 'dataset/eggnog-mapper',
        ...     'kofam_ko_list': 'dataset/ko_list'
        ... }
        >>> resolve_db_paths(config)
        {
            'dataset_dir': '/path/to/datasets',
            'eggnog_data_dir': '/path/to/datasets/dataset/eggnog-mapper',
            'kofam_ko_list': '/path/to/datasets/dataset/ko_list'
        }
    """
    # 0. 确定根目录 (参数优先级 > config优先级)
    root_dir = base_path or config.get("dataset_dir")

    if not root_dir:
        # 既没传参数，config 里也没有，无法处理
        return config
    
    # 确保 root_dir 是绝对路径
    root_dir = os.path.abspath(os.path.expanduser(root_dir))
    
    # 1. 定义需要处理的路径配置项
    # key: 配置项名称
    # value: (是否为目录, 默认值)
    path_configs = {
        "eggnog_data_dir": (True, "dataset/eggnog-mapper"),
        "kofam_ko_list": (False, "dataset/kegg_2026-02-01_ko_dataset/ko_list"),
        "kofam_profiles": (True, "dataset/kegg_2026-02-01_ko_dataset/profiles"),
    }
    
    # 2. 循环处理每个路径配置项
    for key, (is_dir, default_val) in path_configs.items():
        # 获取当前值，如果不存在则使用默认值
        current_value = config.get(key, default_val)
        
        # 如果值已经是绝对路径，则跳过
        if current_value.startswith("/"):
            continue
        
        # 拼接绝对路径
        full_path = os.path.join(root_dir, current_value)
        full_path = os.path.abspath(full_path)
        
        # 更新配置
        config[key] = full_path
    
    # 3. 同时更新 dataset_dir 为绝对路径（保持一致性）
    config["dataset_dir"] = root_dir
    
    return config


def check_db_paths(config, logger=None):
    """
    检查数据库路径是否存在。

    Args:
        config (dict): 已解析过路径的配置字典
        logger: 可选的日志记录器

    Returns:
        dict: 检查结果，包含存在和不存在的路径
    """
    import logging
    if logger is None:
        logger = logging.getLogger(__name__)
    
    path_configs = {
        "eggnog_data_dir": "EggNOG 数据目录",
        "kofam_ko_list": "Kofam KO 列表文件",
        "kofam_profiles": "Kofam profiles 目录",
    }
    
    result = {
        "exists": [],
        "missing": []
    }
    
    for key, desc in path_configs.items():
        path = config.get(key)
        if not path:
            continue
            
        if os.path.exists(path):
            result["exists"].append((key, desc, path))
        else:
            result["missing"].append((key, desc, path))
    
    # 输出检查结果
    if result["missing"]:
        logger.warning("以下数据库路径不存在:")
        for key, desc, path in result["missing"]:
            logger.warning(f"  [{key}] {desc}: {path}")
    
    if result["exists"]:
        logger.info("以下数据库路径已确认:")
        for key, desc, path in result["exists"]:
            logger.info(f"  [{key}] {desc}: {path}")
    
    return result


if __name__ == "__main__":
    # 简单的测试用例
    test_config = {
        "dataset_dir": "~/pipeline/kegg_annotation",
        "eggnog_data_dir": "dataset/eggnog-mapper",
        "kofam_ko_list": "dataset/kegg_2026-02-01_ko_dataset/ko_list",
        "kofam_profiles": "dataset/kegg_2026-02-01_ko_dataset/profiles",
    }
    
    print("原始配置:")
    for k, v in test_config.items():
        print(f"  {k}: {v}")
    
    resolve_db_paths(test_config)
    
    print("\n解析后配置:")
    for k, v in test_config.items():
        print(f"  {k}: {v}")
