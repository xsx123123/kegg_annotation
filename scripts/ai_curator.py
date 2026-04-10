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
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

    def _get_kofam_ratio(self, kofam_record: Optional[Dict]) -> float:
        """计算 KofamScan score/threshold 比值"""
        if not kofam_record:
            return 0.0
        thresh = float(kofam_record.get('kofam_threshold') or kofam_record.get('threshold', 1) or 1)
        score = float(kofam_record.get('score', 0) or 0)
        return score / thresh if thresh > 0 else 0.0

    def _get_eggnog_evalue(self, eggnog_record: Dict) -> float:
        """安全提取 eggnog e-value"""
        ev = eggnog_record.get('evalue', 999.0)
        if ev is None or (isinstance(ev, str) and ev.strip() == ''):
            return 999.0
        try:
            return float(ev)
        except (ValueError, TypeError):
            return 999.0

    def _classify_protein(self, eggnog_record: Dict, kofam_record: Optional[Dict]) -> Tuple[str, Dict]:
        """
        分层筛选：判断蛋白是否值得送 AI 评估
        返回: (category, preset_result)
        category: 'high_conf' | 'low_qual' | 'ambiguous'
        """
        evalue = self._get_eggnog_evalue(eggnog_record)
        ratio = self._get_kofam_ratio(kofam_record)
        eggnog_ko = str(eggnog_record.get('kegg_ko', '') or '').replace('ko:', '').strip()
        kofam_ko_raw = str(kofam_record.get('KO', '') or '') if kofam_record else ''
        kofam_ko = kofam_ko_raw.replace('ko:', '').strip()

        # 高置信：e-value 极显著且 Kofam 比值高
        if evalue < 1e-10 and ratio > 1.5:
            return "high_conf", {
                "eggnog_reliability": {"score": 95, "level": "High", "reasons": [f"e-value={evalue:.0e} 极显著", "Kofam ratio={ratio:.2f}x 高可信"]},
                "kofam_reliability": {"score": 95, "level": "High", "reasons": [f"score/threshold={ratio:.2f}x > 1.5"]},
                "cross_tool_consistency": "Consistent" if kofam_ko and eggnog_ko == kofam_ko else ("Inconsistent" if kofam_ko and eggnog_ko else "Unknown"),
                "species_plausibility": "Plausible",
                "overall_confidence": "High",
                "flags": [],
                "recommended_action": "Accept",
                "_source": "rule_based",
                "eggnog_kegg_ko": eggnog_ko if eggnog_ko else None,
                "kofam_ko": kofam_ko if kofam_ko else None,
            }

        # 明显低质量：e-value 差 或 Kofam 比值极低
        if evalue > 1e-3 or ratio < 0.5:
            return "low_qual", {
                "eggnog_reliability": {"score": 20, "level": "Low", "reasons": [f"e-value={evalue:.0e}"] if evalue > 1e-3 else ["e-value 可接受但 Kofam 极弱"]},
                "kofam_reliability": {"score": max(10, int(ratio*50)), "level": "Low", "reasons": [f"score/threshold={ratio:.2f}x < 0.5"]},
                "cross_tool_consistency": "Unknown",
                "species_plausibility": "Uncertain",
                "overall_confidence": "Low",
                "flags": ["Low quality by traditional thresholds"],
                "recommended_action": "Reject",
                "_source": "rule_based",
                "eggnog_kegg_ko": eggnog_ko if eggnog_ko else None,
                "kofam_ko": kofam_ko if kofam_ko else None,
            }

        # 其余为模糊区域，需要 AI 判断
        return "ambiguous", {}

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

        ratio = self._get_kofam_ratio(kofam_record)

        if kofam_record:
            ko_id = str(kofam_record.get('KO', 'N/A'))
            ko_def = str(kofam_record.get('Description', 'N/A'))
            thresh = float(kofam_record.get('kofam_threshold') or kofam_record.get('threshold', 1) or 1)
            score = float(kofam_record.get('score', 0) or 0)
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

## Taxonomic scope 匹配等级评估（重要）
Taxonomic scope 表示 eggNOG 最佳同源物所在的分类群。匹配层级越精细，可信度越高：
- **精确匹配**：tax_scope 是物种的科/属/种级（如 Enterobacteriaceae 对应 E. coli）→ 高度可信
- **宽泛匹配**：tax_scope 是门/纲级（如 Bacteria 对应具体菌株）→ 匹配过于宽泛，应降级处理
- **严重不匹配**：tax_scope 包含 Eukaryota 而物种是原核生物（或反之）→ 可能为污染或水平转移，标记为异常

## KofamScan 阈值比值背景（重要）
KofamScan 的 score/threshold 比值是核心可信度指标，但不同 KO 的阈值设定本身有差异：
- 管家基因（如核糖体蛋白）通常阈值较高，需要很强的相似性才算命中
- 稀有功能基因或物种特异性基因阈值较低，ratio=1.1 不一定代表"弱可信"
- 因此评估时应结合该 KO 的功能类型，避免简单以 ratio 划线

## 评估任务
请从以下角度评估注释可靠性，以 JSON 格式返回：

1. **eggNOG 可靠性**：
   - e-value/bitscore 是否支持可信注释（一般 e-value < 1e-5, bitscore > 50 为可信）
   - tax_scope 与该蛋白物种分类是否匹配（参考上方的匹配等级评估）
   - 功能描述是否与 COG 分类吻合

2. **KofamScan 可靠性**：
   - Score/Threshold 比值（>1.5 高可信，1.0-1.5 中等，<1.0 仅参考）
   - 结合该 KO 的功能类型（管家基因 vs 稀有基因）判断，不要简单以 ratio 划线
   - 与 eggNOG KO 注释是否一致

3. **物种合理性**：
   - 该功能/通路在 {species_taxonomy} 中是否合理存在

返回 JSON（不含 markdown 标记）：
{{
  "protein_id": "{protein_id}",
  "eggnog_kegg_ko": "{str(kegg_ko).replace('ko:', '').strip() if kegg_ko else ''}",
  "kofam_ko": "{str(ko_id).replace('ko:', '').strip() if ko_id else ''}",
  "eggnog_reliability": {{
    "score": 85,
    "level": "High",
    "reasons": ["e-value=1e-10 高度可信", "tax_scope 精确匹配"]
  }},
  "kofam_reliability": {{
    "score": 70,
    "level": "Medium",
    "reasons": ["score/threshold=1.2x，中等置信", "结合 KO 类型判断为中等", "与 eggNOG KO 一致"]
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
        auto_filter: bool = True,
    ) -> Tuple[List[Dict], Dict]:
        """批量评估每个蛋白的注释可靠性
        
        返回: (results, token_usage_summary)
        """
        results = []
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        ai_count = 0
        rule_count = 0
        categories = {"high_conf": 0, "low_qual": 0, "ambiguous": 0}

        # 1. 先全部分类
        classified = []
        for prot in proteins:
            cat, preset = self._classify_protein(prot.get('eggnog', {}), prot.get('kofam'))
            categories[cat] = categories.get(cat, 0) + 1
            classified.append((prot, cat, preset))

        logger.info(
            f"分层筛选结果: {categories['high_conf']} 高置信, "
            f"{categories['low_qual']} 低质量, "
            f"{categories['ambiguous']} 模糊区域 (待 AI 评估)"
        )

        # 2. 确定实际需要送 AI 的蛋白
        ai_candidates = [item for item in classified if item[1] == "ambiguous"]
        if len(ai_candidates) > max_proteins:
            # 优先保留有 Kofam 记录的，其次随机截断
            ai_candidates = ai_candidates[:max_proteins]
            logger.warning(f"模糊区域蛋白过多，AI 评估限制为前 {max_proteins} 个")

        ai_set = {id(item[0]) for item in ai_candidates}

        # 3. 逐个处理
        total_to_evaluate = len(ai_candidates) if auto_filter else len([p for p in classified if id(p[0]) in ai_set])
        current_ai_idx = 0

        for prot, cat, preset in classified:
            protein_id = prot.get('protein_id', prot.get('query', 'N/A'))

            if not auto_filter or cat != "ambiguous" or id(prot) not in ai_set:
                # 规则直接判定
                result = dict(preset)
                result['protein_id'] = protein_id
                result['_tokens'] = None
                rule_count += 1
                action = result.get("recommended_action", "N/A")
                level = result.get("overall_confidence", "N/A")
                logger.debug(
                    f"[Rule] {protein_id} | category={cat} | "
                    f"overall={level} | action={action}"
                )
            else:
                current_ai_idx += 1
                # 调用 AI
                prompt = self._build_per_protein_prompt(
                    protein_id, species_taxonomy, prot.get('eggnog', {}), prot.get('kofam')
                )
                try:
                    raw_resp, usage = self._call_ai(prompt)
                    result = self._parse_response(raw_resp, protein_id=protein_id)
                    result['protein_id'] = protein_id
                    if usage:
                        result['_tokens'] = usage
                        total_tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
                        total_tokens["completion_tokens"] += usage.get("completion_tokens", 0)
                        total_tokens["total_tokens"] += usage.get("total_tokens", 0)
                    else:
                        result['_tokens'] = None

                    egg_level = result.get("eggnog_reliability", {}).get("level", "N/A")
                    kof_level = result.get("kofam_reliability", {}).get("level", "N/A")
                    action = result.get("recommended_action", "N/A")
                    flags = result.get("flags", [])
                    consistency = result.get("cross_tool_consistency", "N/A")
                    tok_str = f" | tokens={usage['total_tokens']}" if usage else ""
                    logger.info(
                        f"[AI {current_ai_idx}/{total_to_evaluate}] {protein_id} | "
                        f"overall={result.get('overall_confidence', 'N/A')} | "
                        f"eggNOG={egg_level} | Kofam={kof_level} | "
                        f"consistency={consistency} | action={action}{tok_str}"
                    )
                    if flags:
                        logger.warning(f"  [Flags] {protein_id}: {', '.join(flags)}")
                except Exception as e:
                    err_str = str(e)
                    # 认证类错误快速失败，避免后续所有调用都浪费
                    if "401" in err_str or "403" in err_str or "invalid_api_key" in err_str.lower() or "authentication" in err_str.lower():
                        logger.error(f"AI 认证失败 ({err_str[:100]}...)，终止评估。请检查 API key 和权限。")
                        raise RuntimeError(f"AI authentication failed: {err_str}") from e
                    logger.warning(
                        f"[AI {current_ai_idx}/{total_to_evaluate}] {protein_id} 评估失败: {e}"
                    )
                    result = {
                        "protein_id": protein_id,
                        "eggnog_reliability": {"score": 0, "level": "Unknown", "reasons": [f"AI 调用失败: {e}"]},
                        "kofam_reliability": {"score": 0, "level": "Unknown", "reasons": []},
                        "cross_tool_consistency": "Unknown",
                        "species_plausibility": "Unknown",
                        "overall_confidence": "Unknown",
                        "flags": [err_str],
                        "recommended_action": "Review",
                        "_tokens": None,
                    }
                ai_count += 1

            # 统一注入原始 KO 信息（确保任何来源的结果都有这两个字段）
            egg_raw = str(prot.get('eggnog', {}).get('kegg_ko', '') or '').replace('ko:', '').strip()
            kof_raw = str(prot.get('kofam', {}).get('KO', '') or '').replace('ko:', '').strip() if prot.get('kofam') else ''
            result['eggnog_kegg_ko'] = egg_raw if egg_raw else None
            result['kofam_ko'] = kof_raw if kof_raw else None

            results.append(result)

        logger.info(
            f"评估完成: 总计 {len(results)} 个蛋白 | "
            f"规则判定={rule_count} | AI 调用={ai_count} | "
            f"Token(prompt={total_tokens['prompt_tokens']}, completion={total_tokens['completion_tokens']}, total={total_tokens['total_tokens']})"
        )
        return results, {"total_tokens": total_tokens, "ai_calls": ai_count, "rule_based": rule_count, "categories": categories}

    def _call_ai(self, prompt: str) -> Tuple[str, Optional[Dict]]:
        """调用 AI API，返回 (content, usage_dict)"""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的生物信息学注释分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            content = response.choices[0].message.content
            usage = None
            if getattr(response, "usage", None):
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return content, usage

        elif self.provider == "claude":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            usage = None
            if getattr(response, "usage", None):
                usage = {
                    "prompt_tokens": getattr(response.usage, "input_tokens", 0),
                    "completion_tokens": getattr(response.usage, "output_tokens", 0),
                    "total_tokens": getattr(response.usage, "input_tokens", 0) + getattr(response.usage, "output_tokens", 0),
                }
            return content, usage

        elif self.provider == "ollama":
            import requests
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=300,
            )
            response.raise_for_status()
            content = response.json()["response"]
            # Ollama 不统一返回 token usage
            return content, None

        else:
            raise ValueError(f"不支持的提供商: {self.provider}")

    def _parse_response(self, response: str, protein_id: str = "") -> Dict:
        """解析 AI 响应（增强容错）"""
        raw = response
        # 1. 尝试从 markdown code block 中提取
        import re
        code_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            response = code_match.group(1)

        # 2. 尝试直接解析 JSON
        try:
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            pass

        # 3. 尝试提取第一个 { ... } 块
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return result
            except json.JSONDecodeError:
                pass

        # 4. 全部失败，回退
        logger.warning(f"蛋白 {protein_id} AI 响应 JSON 解析失败")
        return {
            "protein_id": protein_id,
            "error": "parse_failed",
            "raw_response": raw[:800],
            "eggnog_reliability": {"score": 0, "level": "Unknown", "reasons": ["JSON 解析失败"]},
            "kofam_reliability": {"score": 0, "level": "Unknown", "reasons": []},
            "cross_tool_consistency": "Unknown",
            "species_plausibility": "Unknown",
            "overall_confidence": "Unknown",
            "flags": ["parse_failed"],
            "recommended_action": "Review",
        }


def generate_report(ai_results: List[Dict], sample_name: str, output_file: str, usage_summary: Optional[Dict] = None):
    """生成 AI 分析报告（基于逐蛋白评估结果）"""

    # 统计汇总
    total = len(ai_results)
    high = sum(1 for r in ai_results if r.get("overall_confidence") == "High")
    medium = sum(1 for r in ai_results if r.get("overall_confidence") == "Medium")
    low = sum(1 for r in ai_results if r.get("overall_confidence") == "Low")
    unknown = total - high - medium - low
    conflicts = sum(1 for r in ai_results if r.get("cross_tool_consistency") == "Inconsistent")
    flags = [r for r in ai_results if r.get("flags")]
    ai_evaluated = sum(1 for r in ai_results if r.get("_source") != "rule_based")
    rule_based = total - ai_evaluated

    report = f"""# AI 注释分析报告（逐蛋白评估）

## 样本信息
**样本名称**: {sample_name}
**分析时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**评估蛋白数**: {total}

## 处理策略与 Token 消耗
- **规则直接判定**: {rule_based} 个蛋白（高置信/低质量两端，不消耗 token）
- **AI 实际评估**: {ai_evaluated} 个蛋白
"""
    if usage_summary:
        tok = usage_summary.get("total_tokens", {})
        report += f"- **Prompt tokens**: {tok.get('prompt_tokens', 'N/A')}\n"
        report += f"- **Completion tokens**: {tok.get('completion_tokens', 'N/A')}\n"
        report += f"- **Total tokens**: {tok.get('total_tokens', 'N/A')}\n"

    report += f"""
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
        src = "AI" if r.get("_source") != "rule_based" else "Rule"
        fl = ", ".join(r.get("flags", [])) if r.get("flags") else "None"
        report += f"- `{pid}` | Overall: **{ov}** | Action: **{act}** | Source: **{src}** | Flags: {fl}\n"

    report += "\n## 逐蛋白详细评估\n"
    for r in ai_results:
        pid = r.get("protein_id", "N/A")
        egg = r.get("eggnog_reliability", {})
        kof = r.get("kofam_reliability", {})
        src = "AI" if r.get("_source") != "rule_based" else "Rule"
        tokens = r.get("_tokens")
        tok_str = f" | Tokens: {tokens['total_tokens']}" if tokens else ""
        report += f"""
### {pid}
- **Overall confidence**: {r.get('overall_confidence', 'N/A')}
- **Species plausibility**: {r.get('species_plausibility', 'N/A')}
- **Cross-tool consistency**: {r.get('cross_tool_consistency', 'N/A')}
- **eggNOG**: {egg.get('level', 'N/A')} (score={egg.get('score', 'N/A')})
- **KofamScan**: {kof.get('level', 'N/A')} (score={kof.get('score', 'N/A')})
- **Recommended action**: {r.get('recommended_action', 'N/A')}
- **Flags**: {', '.join(r.get('flags', [])) or 'None'}
- **Source**: {src}{tok_str}
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"AI 分析报告已保存: {output_file}")


def flatten_ai_results(results: List[Dict]) -> pd.DataFrame:
    """将嵌套的 AI 评估结果展平为 DataFrame，便于输出 TSV/CSV"""
    rows = []
    for r in results:
        egg = r.get("eggnog_reliability", {})
        kof = r.get("kofam_reliability", {})
        rows.append({
            "protein_id": r.get("protein_id", ""),
            "eggnog_kegg_ko": r.get("eggnog_kegg_ko", ""),
            "kofam_ko": r.get("kofam_ko", ""),
            "overall_confidence": r.get("overall_confidence", ""),
            "cross_tool_consistency": r.get("cross_tool_consistency", ""),
            "species_plausibility": r.get("species_plausibility", ""),
            "recommended_action": r.get("recommended_action", ""),
            "eggnog_level": egg.get("level", ""),
            "eggnog_score": egg.get("score", ""),
            "eggnog_reasons": "; ".join(egg.get("reasons", [])),
            "kofam_level": kof.get("level", ""),
            "kofam_score": kof.get("score", ""),
            "kofam_reasons": "; ".join(kof.get("reasons", [])),
            "flags": "; ".join(r.get("flags", [])),
            "source": r.get("_source", ""),
            "error": r.get("error", ""),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description='AI Curator for KEGG Annotation (per-protein)')
    parser.add_argument('-e', '--eggnog', required=True, help='eggnog 结果 TSV')
    parser.add_argument('-k', '--kofam', required=True, help='KofamScan 结果 TSV')
    parser.add_argument('-s', '--sample', required=True, help='样本名称')
    parser.add_argument('-o', '--output', required=True, help='输出 Markdown 报告')
    parser.add_argument('--output-json', required=True, help='输出 JSON 评估结果')
    parser.add_argument('--output-tsv', help='输出 TSV 格式评估结果（可选）')
    parser.add_argument('--output-csv', help='输出 CSV 格式评估结果（可选）')
    parser.add_argument('--taxonomy', default='Unknown', help='物种分类信息（如 Bacteria;Firmicutes;Bacillales）')
    parser.add_argument('--max-proteins', type=int, default=50, help='最大 AI 评估蛋白数（仅针对模糊区域，默认 50）')
    parser.add_argument('--no-auto-filter', action='store_true', help='关闭分层筛选，所有蛋白都送 AI（Token 消耗高）')
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
        results, usage_summary = curator.evaluate_per_protein(
            proteins,
            args.taxonomy,
            max_proteins=args.max_proteins,
            auto_filter=not args.no_auto_filter,
        )
    except Exception as e:
        logger.error(f"AI 评估失败: {e}")
        sys.exit(1)

    # 生成 Markdown 报告
    generate_report(results, args.sample, args.output, usage_summary)

    # 保存 JSON
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'sample': args.sample,
            'taxonomy': args.taxonomy,
            'provider': args.provider,
            'model': args.model,
            'total_proteins': len(proteins),
            'evaluated_by_ai': usage_summary.get("ai_calls", 0),
            'rule_based': usage_summary.get("rule_based", 0),
            'token_usage': usage_summary.get("total_tokens", {}),
            'categories': usage_summary.get("categories", {}),
            'results': results,
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON 结果已保存: {args.output_json}")

    # 从内存结果直接展平输出 TSV/CSV（无需重新运行 AI）
    if args.output_tsv or args.output_csv:
        logger.info("生成 TSV/CSV 表格...")
        df = flatten_ai_results(results)
        if args.output_tsv:
            df.to_csv(args.output_tsv, sep='\t', index=False)
            logger.info(f"TSV 结果已保存: {args.output_tsv}")
        if args.output_csv:
            df.to_csv(args.output_csv, index=False)
            logger.info(f"CSV 结果已保存: {args.output_csv}")

    logger.success("AI 分析完成!")


if __name__ == '__main__':
    main()
