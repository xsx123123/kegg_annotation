#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Curator for KEGG Annotation Results

使用 AI 对注释结果进行智能分析、校正和解读。
支持 OpenAI、Claude 等 API，或本地 Ollama 模型。
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

# 尝试导入 loguru
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(__name__)


class AICurator:
    """AI 注释校正器"""
    
    def __init__(self, provider: str = "ollama", model: str = "llama3.2", api_key: Optional[str] = None, api_base: Optional[str] = None):
        """
        初始化 AI Curator
        
        Args:
            provider: AI 提供商 (openai, claude, ollama)
            model: 模型名称
            api_key: API 密钥
            api_base: API 基础 URL（用于自定义端点）
        """
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv("AI_API_KEY")
        self.api_base = api_base or os.getenv("AI_API_BASE")
        
        self._init_client()
    
    def _init_client(self):
        """初始化 AI 客户端"""
        if self.provider == "openai":
            try:
                import openai
                self.client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=self.api_base
                )
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        
        elif self.provider == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装 anthropic: pip install anthropic")
        
        elif self.provider == "ollama":
            # Ollama 使用 HTTP 请求，不需要特殊客户端
            self.client = None
            self.ollama_url = self.api_base or "http://localhost:11434"
        
        else:
            raise ValueError(f"不支持的 AI 提供商: {self.provider}")
    
    def analyze_sample(self, eggnog_df: pd.DataFrame, kofam_df: pd.DataFrame, sample_name: str) -> Dict:
        """
        分析单个样本的注释结果
        
        Returns:
            {
                'summary': str,  # AI 生成的样本功能摘要
                'conflicts': List[Dict],  # 识别的冲突/问题
                'recommendations': List[str],  # 改进建议
                'pathway_insights': str,  # 通路洞察
            }
        """
        # 准备统计数据
        stats = self._prepare_stats(eggnog_df, kofam_df)
        
        # 构建提示词
        prompt = self._build_analysis_prompt(stats, sample_name)
        
        # 调用 AI
        response = self._call_ai(prompt)
        
        # 解析响应
        return self._parse_response(response, stats)
    
    def _prepare_stats(self, eggnog_df: pd.DataFrame, kofam_df: pd.DataFrame) -> Dict:
        """准备统计数据"""
        stats = {
            'eggnog_total': len(eggnog_df),
            'eggnog_high_conf': len(eggnog_df[eggnog_df.get('confidence_level', '') == 'High']),
            'eggnog_with_kegg': eggnog_df['kegg_ko'].notna().sum() if 'kegg_ko' in eggnog_df.columns else 0,
            'eggnog_with_go': eggnog_df['gos'].notna().sum() if 'gos' in eggnog_df.columns else 0,
            'kofam_total': len(kofam_df),
            'kofam_high_conf': len(kofam_df[kofam_df.get('confidence_level', '') == 'High']),
        }
        
        # 提取前 10 个高频 KO
        if 'kegg_ko' in eggnog_df.columns:
            kos = eggnog_df['kegg_ko'].dropna().str.split(',').explode()
            stats['top_kos'] = kos.value_counts().head(10).to_dict()
        
        # 提取前 10 个高频通路
        if 'kegg_pathway' in eggnog_df.columns:
            pathways = eggnog_df['kegg_pathway'].dropna().str.split(',').explode()
            stats['top_pathways'] = pathways.value_counts().head(10).to_dict()
        
        # COG 分类统计
        if 'cog_category' in eggnog_df.columns:
            stats['cog_categories'] = eggnog_df['cog_category'].value_counts().head(10).to_dict()
        
        return stats
    
    def _build_analysis_prompt(self, stats: Dict, sample_name: str) -> str:
        """构建 AI 分析提示词"""
        prompt = f"""你是一位生物信息学专家，专门负责基因功能注释的质量控制和解读。

请分析以下样本的基因注释数据，提供专业的分析和建议。

## 样本信息
样本名称: {sample_name}

## 注释统计
### eggnog-mapper 结果
- 总注释数: {stats['eggnog_total']}
- 高可信度注释: {stats['eggnog_high_conf']} ({stats['eggnog_high_conf']/max(stats['eggnog_total'],1)*100:.1f}%)
- 有 KEGG KO: {stats['eggnog_with_kegg']}
- 有 GO 注释: {stats['eggnog_with_go']}

### KofamScan 结果
- 总注释数: {stats['kofam_total']}
- 高可信度注释: {stats['kofam_high_conf']} ({stats['kofam_high_conf']/max(stats['kofam_total'],1)*100:.1f}%)

"""
        
        if 'top_kos' in stats and stats['top_kos']:
            prompt += "\n### 高频 KEGG KO（前10）\n"
            for ko, count in list(stats['top_kos'].items())[:10]:
                prompt += f"- {ko}: {count} 个基因\n"
        
        if 'cog_categories' in stats and stats['cog_categories']:
            prompt += "\n### COG 功能分类（前10）\n"
            for cog, count in list(stats['cog_categories'].items())[:10]:
                prompt += f"- {cog}: {count} 个基因\n"
        
        prompt += """

## 请提供以下分析（以 JSON 格式返回）

{
  "summary": "样本功能摘要（200字以内），描述该样本的主要生物学功能特征",
  "quality_assessment": {
    "score": 85,  // 整体注释质量评分 0-100
    "level": "High",  // High/Medium/Low
    "reason": "评分理由"
  },
  "key_functions": [
    "功能1: 描述",
    "功能2: 描述"
  ],
  "potential_issues": [
    "可能的问题1",
    "可能的问题2"
  ],
  "recommendations": [
    "改进建议1",
    "改进建议2"
  ],
  "pathway_insights": "对主要通路的解读（150字以内）"
}

请确保返回有效的 JSON 格式，不要包含 markdown 代码块标记。"""
        
        return prompt
    
    def _call_ai(self, prompt: str) -> str:
        """调用 AI API"""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的生物信息学注释分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        
        elif self.provider == "claude":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        
        elif self.provider == "ollama":
            import requests
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json()["response"]
        
        else:
            raise ValueError(f"不支持的提供商: {self.provider}")
    
    def _parse_response(self, response: str, stats: Dict) -> Dict:
        """解析 AI 响应"""
        try:
            # 尝试直接解析 JSON
            result = json.loads(response)
        except json.JSONDecodeError:
            # 如果失败，尝试提取 JSON 部分
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    result = self._create_fallback_result(response, stats)
            else:
                result = self._create_fallback_result(response, stats)
        
        # 添加原始统计数据
        result['raw_stats'] = stats
        
        return result
    
    def _create_fallback_result(self, response: str, stats: Dict) -> Dict:
        """创建回退结果（当 JSON 解析失败时）"""
        logger.warning("AI 响应解析失败，使用文本格式")
        return {
            "summary": "AI 分析完成，但返回格式非标准 JSON",
            "quality_assessment": {
                "score": 0,
                "level": "Unknown",
                "reason": "解析失败"
            },
            "key_functions": [],
            "potential_issues": [],
            "recommendations": ["请检查 AI 模型输出格式"],
            "pathway_insights": "",
            "raw_response": response,
            "raw_stats": stats
        }


def generate_report(ai_result: Dict, sample_name: str, output_file: str):
    """生成 AI 分析报告"""
    report = f"""# AI 注释分析报告

## 样本信息
**样本名称**: {sample_name}
**分析时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

## 功能摘要
{ai_result.get('summary', 'N/A')}

## 质量评估
- **评分**: {ai_result.get('quality_assessment', {}).get('score', 'N/A')}/100
- **等级**: {ai_result.get('quality_assessment', {}).get('level', 'N/A')}
- **评价**: {ai_result.get('quality_assessment', {}).get('reason', 'N/A')}

## 关键功能
"""
    
    for func in ai_result.get('key_functions', []):
        report += f"- {func}\n"
    
    report += "\n## 潜在问题\n"
    for issue in ai_result.get('potential_issues', []):
        report += f"- ⚠️ {issue}\n"
    
    report += "\n## 改进建议\n"
    for rec in ai_result.get('recommendations', []):
        report += f"- 💡 {rec}\n"
    
    report += f"\n## 通路洞察\n{ai_result.get('pathway_insights', 'N/A')}\n"
    
    # 添加原始统计数据
    stats = ai_result.get('raw_stats', {})
    report += f"""
## 统计详情
- eggnog 注释数: {stats.get('eggnog_total', 'N/A')}
- KofamScan 注释数: {stats.get('kofam_total', 'N/A')}
- 高可信度比例: {stats.get('eggnog_high_conf', 0)/max(stats.get('eggnog_total', 1), 1)*100:.1f}%
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"AI 分析报告已保存: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='AI Curator for KEGG Annotation')
    parser.add_argument('-e', '--eggnog', required=True, help='eggnog 结果文件')
    parser.add_argument('-k', '--kofam', required=True, help='KofamScan 结果文件')
    parser.add_argument('-s', '--sample', required=True, help='样本名称')
    parser.add_argument('-o', '--output', required=True, help='输出报告文件')
    parser.add_argument('--provider', default='ollama', choices=['openai', 'claude', 'ollama'],
                        help='AI 提供商')
    parser.add_argument('--model', default='llama3.2', help='模型名称')
    parser.add_argument('--api-key', help='API 密钥（也可通过环境变量 AI_API_KEY 设置）')
    parser.add_argument('--api-base', help='API 基础 URL')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not Path(args.eggnog).exists():
        logger.error(f"eggnog 文件不存在: {args.eggnog}")
        sys.exit(1)
    
    if not Path(args.kofam).exists():
        logger.error(f"Kofam 文件不存在: {args.kofam}")
        sys.exit(1)
    
    # 读取数据
    logger.info("读取注释结果...")
    eggnog_df = pd.read_csv(args.eggnog, sep='\t', low_memory=False)
    kofam_df = pd.read_csv(args.kofam, sep='\t', low_memory=False)
    
    logger.info(f"eggnog: {len(eggnog_df)} 条, Kofam: {len(kofam_df)} 条")
    
    # 初始化 AI Curator
    logger.info(f"初始化 AI ({args.provider}/{args.model})...")
    try:
        curator = AICurator(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            api_base=args.api_base
        )
    except Exception as e:
        logger.error(f"AI 初始化失败: {e}")
        sys.exit(1)
    
    # 运行 AI 分析
    logger.info("运行 AI 分析...")
    try:
        result = curator.analyze_sample(eggnog_df, kofam_df, args.sample)
    except Exception as e:
        logger.error(f"AI 分析失败: {e}")
        sys.exit(1)
    
    # 生成报告
    generate_report(result, args.sample, args.output)
    
    logger.success("AI 分析完成!")


if __name__ == '__main__':
    main()
