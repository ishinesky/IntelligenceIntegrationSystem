from __future__ import annotations

from typing import Any, Dict, Optional

from ServiceComponent.IntelligenceAnalyzerProxy import analyze_with_ai


OPC_EDITORIAL_PROMPT = """
你是一个面向 OPC（一人公司 / AI 原生创业者 / 小团队）的产业信息编辑。

你的任务不是改写新闻，而是把原始文章拆成：事实、分析、观点、行动建议。
必须严格区分事实和你的编辑观点。

请只输出 JSON，不要输出 Markdown，不要解释 JSON 外的内容。

输出字段：
{
  "FACT_SUMMARY": "基于原文的事实摘要，不加入推测",
  "WHY_IT_MATTERS": "为什么这条信息对 OPC/AI创业者/园区/服务商重要",
  "OPPORTUNITY": "潜在机会，若没有则写空字符串",
  "RISK": "风险点或不确定性，若没有则写空字符串",
  "WHO_SHOULD_CARE": ["适合关注的人群"],
  "ACTION_SUGGESTION": "建议下一步行动",
  "EDITORIAL_VIEW": "明确标注为 AI 编辑观点的评论态度，不能冒充事实",
  "SOURCE_RELIABILITY": "S/A/B/C",
  "CONTENT_QUALITY_SCORE": 0,
  "ACTIONABILITY_SCORE": 0,
  "CONFIDENCE": 0.0
}

评分规则：
- CONTENT_QUALITY_SCORE：0-10，信息密度、来源质量、时效性越高分越高。
- ACTIONABILITY_SCORE：0-10，对用户是否能直接采取行动。
- CONFIDENCE：0-1，对分析可靠性的信心。
- SOURCE_RELIABILITY：政府/官方源优先 S，权威媒体 A，行业站 B，未经核验 C。

当前日期：{{CURRENT_DATE}}
""".strip()


def build_editorial_review(
    ai_client,
    article: Dict[str, Any],
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate an AI editorial review for one collected article.

    The input must include at least `content`; title/pub_time/informant are optional
    and passed through the existing analyzer message builder.
    """
    return analyze_with_ai(
        ai_client=ai_client,
        prompt=prompt or OPC_EDITORIAL_PROMPT,
        structured_data=article,
        context=None,
    )
