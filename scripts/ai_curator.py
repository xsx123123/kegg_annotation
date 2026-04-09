#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Curator for KEGG Annotation Results

使用 AI 对注释结果进行逐蛋白智能分析、校正和解读。
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

    def __init__(self, provider: str = "ollama", model: str = "llama3.2",
                 api_key: Optional[str] = None, api_base: Optional[str] = None):
        self.provider = provider.lower()
        self.model = model

        self._api_key_source = None
        if api_key:
            if api_key.isupper() and '_' in api_key:
                env_value = os.getenv(api_key)
                if env_value:
                    self.api_key = env_value
                    self._api_key_source = f"env:{api_key}"
                    logger.debug(f"从环境变量 {api_key} 读取 API key (长度: {len(env_value)})")
                else:
                    logger.warning(f"环境变量 {api_key} 未设置")
                    self.api_key = None
            else:
                self.api_key = api_key
                self._api_key_source = "direct"
                logger.warning("⚠️  API key 以明文形式传入，存在安全风险！建议使用环境变量。")
        else:
            env_value = os.getenv("AI_API_KEY")
            if env_value:
                self.api_key = env_value
                self._api_key_source = "env:AI_API_KEY"
                logger.debug(f"从环境变量 AI_API_KEY 读取 API key (长度: {len(env_value)})")
            else:
                self.api_key = None

        if api_base:
            if api_base.isupper() and '_' in api_base:
                env_value = os.getenv(api_base)
                if env_value:
                    self.api_base = env_value
                else:
                    self.api_base = None
            else:
                self.api_base = api_base
        else:
            self.api_base = os.getenv("AI_API_BASE")

        self._init_client()

    def _init_client(self):
        """初始化 AI 客户端"""
        if self.provider == "openai":
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base)
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        elif self.provider == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装 anthropic: pip install anthropic")
        elif self.provider == "ollama":
            self.client = None
            self.ollama_url = self.api_base or "http://localhost:11434"
        else:
            raise ValueError(f"不支持的 AI 提供商: {self.provider}")

    def _build_per_protein_prompt(
        self,
        protein_id: str,
        species_taxonomy: str,
        eggnog_record: Dict,
        kofam_record: Optional[Dict],
    ) -> str:
        """构建单蛋白注释可靠性评估 prompt"""

        e_val = eggnog_record.get('evalue', 'N/A')
        bitscore = eggnog_record.get('score', 'N/A')
        tax_scope = eggnog_record.get('tax_scope', 'N/A')
        cog = eggnog_record.get('cog_category', '')
        kegg_ko = eggnog_record.get('kegg_ko', '')
        desc = eggnog_record.get('description', '')
        seed = eggnog_record.get('seed_ortholog', '')
        ec = eggnog_record.get('ec', '')
        go = eggnog_record.get('gos', '')

        if kofam_record:
            ko_id = str(kofam_record.get('KO', 'N/A'))
            ko_def = str(kofam_record.get('Description', 'N/A'))
            thresh = float(kofam_record.get('kofam_threshold') or kofam_record.get('threshold', 1) or 1)
            score = float(kofam_record.get('score', 0) or 0)
            ratio = score / thresh if thresh > 0 else 0
            sig = str(kofam_record.get('pass_threshold', '-'))
            kofam_evalue = kofam_record.get('evalue', 'N/A')
            kofam_section = f"""### KofamScan 注释
- KO: {ko_id} | 定义: {ko_def}
- Score: {score:.1f} / Threshold: {thresh:.1f} (比值: {ratio:.2f}x)
- E-value: {kofam_evalue}
- 是否通过阈值: {'是 (*)' if sig.lower() in ('true', '1', 'yes', '*') else '否 (-)'}
"""
        else:
            ko_id = None
            kofam_section = "\n### KofamScan 注释\n- 无匹配结果\n"

        consistency_note = ""
        if kofam_record and kegg_ko and ko_id and ko_id != 'N/A':
            eggnog_kos = set(str(kegg_ko).replace("ko:", "").split(","))
            kofam_ko_clean = str(ko_id).replace("ko:", "").strip()
            if any(kofam_ko_clean == ek.strip() for ek in eggnog_kos if ek.strip()):
                consistency_note = "✅ 注意：eggNOG 与 KofamScan 的 KO 注释**一致**，可相互印证。"
            else:
                consistency_note = "⚠️ 注意：eggNOG 与 KofamScan 的 KO 注释**不一致**，存在冲突。"

        prompt = f"""你是一位生物信息学专家，请对以下蛋白的功能注释进行可靠性评估。

## 蛋白信息
- 蛋白 ID: {protein_id}
- 所属物种/分类: {species_taxonomy}

## eggNOG-mapper 注释
- Seed ortholog: {seed}
- E-value: {e_val} | Bitscore: {bitscore}
- Taxonomic scope: {tax_scope}
- COG 分类: {cog}
- 功能描述: {desc}
- KEGG KO: {kegg_ko}
- GO terms: {go}
- EC: {ec}
{kofam_section}
{consistency_note}

## 评估任务
请从以下角度评估注释可靠性，以 JSON 格式返回：

1. **eggNOG 可靠性**：
   - e-value/bitscore 是否支持可信注释（一般 e-value < 1e-5, bitscore > 50 为可信）
   - tax_scope 与该蛋白物种分类是否匹配（如细菌蛋白对应的 tax_scope 不应是 Eukaryota）
   - 功能描述是否与 COG 分类吻合

2. **KofamScan 可靠性**：
   - Score/Threshold 比值（>1.5 高可信，1.0-1.5 中等，<1.0 仅参考）
   - 与 eggNOG KO 注释是否一致

3. **物种合理性**：
   - 该功能/通路在 {species_taxonomy} 中是否合理存在

返回 JSON（不含 markdown 标记）：
{{
  "protein_id": "{protein_id}",
  "eggnog_reliability": {{
    "score": 85,
    "level": "High",
    "reasons": ["e-value=1e-10 高度可信", "tax_scope 与物种匹配"]
  }},
  "kofam_reliability": {{
    "score": 70,
    "level": "Medium",
    "reasons": ["score/threshold=1.2x，中等置信", "与 eggNOG KO 一致"]
  }},
  "cross_tool_consistency": "Consistent",
  "species_plausibility": "Plausible",
  "overall_confidence": "High",
  "flags": [],
  "recommended_action": "Accept"
}}"""
        return prompt

    def evaluate_per_protein(
        self,
        proteins: List[Dict],
        species_taxonomy: str,
        max_proteins: int = 50,
    ) -> List[Dict]:
        """批量评估每个蛋白的注释可靠性"""
        results = []
        total = min(len(proteins), max_proteins)
        logger.info(f"开始逐蛋白 AI 评估，共 {len(proteins)} 个，本次评估前 {total} 个...")

        for idx, prot in enumerate(proteins[:total], 1):
            protein_id = prot.get('protein_id', prot.get('query', f"prot_{idx}"))
            eggnog_record = prot.get('eggnog', {})
            kofam_record = prot.get('kofam')

            prompt = self._build_per_protein_prompt(
                protein_id, species_taxonomy, eggnog_record, kofam_record
            )
            try:
                raw_resp = self._call_ai(prompt)
                result = self._parse_response(raw_resp, {})
                result['protein_id'] = protein_id
                result['_prompt'] = prompt  # 可选，调试用
            except Exception as e:
                logger.warning(f"蛋白 {protein_id} AI 评估失败: {e}")
                result = {
                    "protein_id": protein_id,
                    "eggnog_reliability": {"score": 0, "level": "Unknown", "reasons": [f"AI 调用失败: {e}"]},
                    "kofam_reliability": {"score": 0, "level": "Unknown", "reasons": []},
                    "cross_tool_consistency": "Unknown",
                    "species_plausibility": "Unknown",
                    "overall_confidence": "Unknown",
                    "flags": [str(e)],
                    "recommended_action": "Review",
                }
            results.append(result)

        logger.info(f"逐蛋白评估完成: {len(results)} 个")
        return results

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
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=300,
            )
            response.raise_for_status()
            return response.json()["response"]
        else:
            raise ValueError(f"不支持的提供商: {self.provider}")

    def _parse_response(self, response: str, stats: Dict) -> Dict:
        """解析 AI 响应"""
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    result = self._create_fallback_result(response, stats)
            else:
                result = self._create_fallback_result(response, stats)
        result['raw_stats'] = stats
        return result

    def _create_fallback_result(self, response: str, stats: Dict) -> Dict:
        """创建回退结果"""
        logger.warning("AI 响应解析失败，使用文本格式")
        return {
            "summary": "AI 分析完成，但返回格式非标准 JSON",
            "quality_assessment": {"score": 0, "level": "Unknown", "reason": "解析失败"},
            "key_functions": [],
            "potential_issues": [],
            "recommendations": ["请检查 AI 模型输出格式"],
            "pathway_insights": "",
            "raw_response": response,
            "raw_stats": stats,
        }


def generate_report(ai_results: List[Dict], sample_name: str, output_file: str):
    """生成 AI 分析报告（基于逐蛋白评估结果）"""

    # 统计汇总
    total = len(ai_results)
    high = sum(1 for r in ai_results if r.get("overall_confidence") == "High")
    medium = sum(1 for r in ai_results if r.get("overall_confidence") == "Medium")
    low = sum(1 for r in ai_results if r.get("overall_confidence") == "Low")
    unknown = total - high - medium - low
    conflicts = sum(1 for r in ai_results if r.get("cross_tool_consistency") == "Inconsistent")
    flags = [r for r in ai_results if r.get("flags")]

    report = f"""# AI 注释分析报告（逐蛋白评估）

## 样本信息
**样本名称**: {sample_name}
**分析时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**评估蛋白数**: {total}

## 整体质量汇总
- **High confidence**: {high} ({high/max(total,1)*100:.1f}%)
- **Medium confidence**: {medium} ({medium/max(total,1)*100:.1f}%)
- **Low confidence**: {low} ({low/max(total,1)*100:.1f}%)
- **Unknown / Failed**: {unknown}
- **Cross-tool conflicts**: {conflicts}
- **Flagged proteins**: {len(flags)}

## 关键发现与建议
"""

    # 推荐动作统计
    actions = {}
    for r in ai_results:
        act = r.get("recommended_action", "Review")
        actions[act] = actions.get(act, 0) + 1
    for act, cnt in sorted(actions.items(), key=lambda x: -x[1]):
        report += f"- **{act}**: {cnt} 个蛋白\n"

    report += "\n## 潜在问题蛋白（Top 20）\n"
    # 按问题数量排序，优先展示有 flags 或 confidence 低的
    def _sort_key(r):
        conf_order = {"Low": 0, "Medium": 1, "High": 2, "Unknown": 3}
        return (conf_order.get(r.get("overall_confidence"), 3), len(r.get("flags", [])), r.get("protein_id", ""))

    for r in sorted(ai_results, key=_sort_key)[:20]:
        pid = r.get("protein_id", "N/A")
        ov = r.get("overall_confidence", "N/A")
        act = r.get("recommended_action", "N/A")
        fl = ", ".join(r.get("flags", [])) if r.get("flags") else "None"
        report += f"- `{pid}` | Overall: **{ov}** | Action: **{act}** | Flags: {fl}\n"

    report += "\n## 逐蛋白详细评估\n"
    for r in ai_results:
        pid = r.get("protein_id", "N/A")
        egg = r.get("eggnog_reliability", {})
        kof = r.get("kofam_reliability", {})
        report += f"""
### {pid}
- **Overall confidence**: {r.get('overall_confidence', 'N/A')}
- **Species plausibility**: {r.get('species_plausibility', 'N/A')}
- **Cross-tool consistency**: {r.get('cross_tool_consistency', 'N/A')}
- **eggNOG**: {egg.get('level', 'N/A')} (score={egg.get('score', 'N/A')})
- **KofamScan**: {kof.get('level', 'N/A')} (score={kof.get('score', 'N/A')})
- **Recommended action**: {r.get('recommended_action', 'N/A')}
- **Flags**: {', '.join(r.get('flags', [])) or 'None'}
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"AI 分析报告已保存: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='AI Curator for KEGG Annotation (per-protein)')
    parser.add_argument('-e', '--eggnog', required=True, help='eggnog 结果 TSV')
    parser.add_argument('-k', '--kofam', required=True, help='KofamScan 结果 TSV')
    parser.add_argument('-s', '--sample', required=True, help='样本名称')
    parser.add_argument('-o', '--output', required=True, help='输出 Markdown 报告')
    parser.add_argument('--output-json', required=True, help='输出 JSON 评估结果')
    parser.add_argument('--taxonomy', default='Unknown', help='物种分类信息（如 Bacteria;Firmicutes;Bacillales）')
    parser.add_argument('--max-proteins', type=int, default=50, help='最大评估蛋白数（默认 50）')
    parser.add_argument('--provider', default='ollama', choices=['openai', 'claude', 'ollama'])
    parser.add_argument('--model', default='llama3.2')
    parser.add_argument('--api-key', help='API 密钥（也可通过环境变量 AI_API_KEY 设置）')
    parser.add_argument('--api-base', help='API 基础 URL')
    args = parser.parse_args()

    if args.api_key and not (args.api_key.isupper() and '_' in args.api_key):
        logger.warning("⚠️  安全警告: API key 通过命令行参数传入，可能在进程列表中暴露！")

    for fpath in [args.eggnog, args.kofam]:
        if not Path(fpath).exists():
            logger.error(f"文件不存在: {fpath}")
            sys.exit(1)

    logger.info("读取注释结果...")
    try:
        eggnog_df = pd.read_csv(args.eggnog, sep='\t', low_memory=False, comment='#')
    except Exception as e:
        logger.error(f"解析 eggnog 失败: {e}")
        sys.exit(1)

    try:
        kofam_df = pd.read_csv(args.kofam, sep='\t', low_memory=False, comment='#')
    except Exception as e:
        logger.error(f"解析 kofam 失败: {e}")
        sys.exit(1)

    logger.info(f"eggnog: {len(eggnog_df)} 条, Kofam: {len(kofam_df)} 条")

    # 建立 query -> record 映射
    eggnog_map = {}
    if not eggnog_df.empty and 'query' in eggnog_df.columns:
        for _, row in eggnog_df.iterrows():
            eggnog_map[str(row['query'])] = row.to_dict()

    kofam_map = {}
    if not kofam_df.empty and 'query' in kofam_df.columns:
        for _, row in kofam_df.iterrows():
            kofam_map[str(row['query'])] = row.to_dict()

    all_queries = sorted(set(eggnog_map.keys()) | set(kofam_map.keys()))
    proteins = []
    for q in all_queries:
        proteins.append({
            'protein_id': q,
            'query': q,
            'eggnog': eggnog_map.get(q, {}),
            'kofam': kofam_map.get(q) if q in kofam_map else None,
        })

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

    logger.info("运行逐蛋白 AI 评估...")
    try:
        results = curator.evaluate_per_protein(
            proteins, args.taxonomy, max_proteins=args.max_proteins
        )
    except Exception as e:
        logger.error(f"AI 评估失败: {e}")
        sys.exit(1)

    # 生成 Markdown 报告
    generate_report(results, args.sample, args.output)

    # 保存 JSON
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'sample': args.sample,
            'taxonomy': args.taxonomy,
            'provider': args.provider,
            'model': args.model,
            'total_proteins': len(proteins),
            'evaluated': len(results),
            'results': results,
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON 结果已保存: {args.output_json}")
    logger.success("AI 分析完成!")


if __name__ == '__main__':
    main()
