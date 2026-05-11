#app.services.ai_insights_service.py

import asyncio
from app.core.config import get_settings
from app.db.cache import make_cache_key, get_cached_response, set_cached_response
from google import genai
import json
import re

settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)
PROMPT_VERSION = "ai_insights_v3"


def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON in Gemini response")
    return json.loads(match.group())


def _build_prompt(summary: dict, retry: bool = False) -> str:
    retry_instruction = ""
    if retry:
        retry_instruction = """
Your previous response missed required insight sections.
Return the same JSON shape again, but make sure emerging_trends and
declining_areas are non-empty arrays.
"""

    return f"""
You are a senior business consultant.

Analyze the following business summary and provide insights and recommendations.

Rules:
- Be concise, executive-friendly
- Focus on business impact
- Recommendations must be actionable
- emerging_trends and declining_areas are required and must not be empty
- emerging_trends and declining_areas must contain only trend and mentions
- mentions must be a number
- Do not include description or evidence inside emerging_trends or declining_areas
- Do not use placeholder text such as "No issue found"
- If detected_emerging_trends or detected_declining_areas are empty, infer trends from overview,
  performance_by_category, key strengths, key issues, and business goals
- Each actionable recommendation must include description and evidence
- description explains the recommendation in plain business language
- evidence must be a short metric/reference string, for example:
  "23 mentions in last 30 days (+15% vs previous month) | Reference: customer reviews mentioning slow service"

{retry_instruction}
Return STRICT JSON ONLY:

{{
  "business_health_score": number,
  "quick_insights": {{
    "what_customers_love": "string",
    "what_customers_dislike": "string",
    "emerging_opportunities": "string"
  }},
  "emerging_trends": [
    {{
      "trend": "string",
      "mentions": number
    }}
  ],
  "declining_areas": [
    {{
      "trend": "string",
      "mentions": number
    }}
  ],
  "actionable_recommendations": [
    {{
      "title": "string",
      "priority": "High|Medium|Low",
      "description": "string",
      "evidence": "string",
      "business_impact": "string",
      "expected_improvement": "string",
      "actions": ["string"]
    }}
  ]
}}

Business summary:
{json.dumps(summary, indent=2)}
"""


def _has_required_ai_sections(result: dict) -> bool:
    def has_trends(name: str) -> bool:
        trends = result.get(name)
        return (
            isinstance(trends, list)
            and len(trends) > 0
            and all(
                isinstance(trend, dict)
                and "trend" in trend
                and "mentions" in trend
                for trend in trends
            )
        )

    return has_trends("emerging_trends") and has_trends("declining_areas")


def _normalize_trend_sections(result: dict) -> dict:
    for section in ("emerging_trends", "declining_areas"):
        result[section] = [
            {
                "trend": item["trend"],
                "mentions": item["mentions"],
            }
            for item in result.get(section, [])
            if isinstance(item, dict)
            and "trend" in item
            and "mentions" in item
        ]

    return result


async def _generate(prompt: str):
    return await asyncio.to_thread(
        client.models.generate_content,
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )


async def generate_ai_insights(summary: dict) -> dict:
    cache_key = make_cache_key(
        "ai_insights",
        settings.GEMINI_MODEL,
        PROMPT_VERSION,
        summary,
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    response = await _generate(_build_prompt(summary))
    result = extract_json(response.text)

    if not _has_required_ai_sections(result):
        response = await _generate(_build_prompt(summary, retry=True))
        result = extract_json(response.text)

    if not _has_required_ai_sections(result):
        raise ValueError(
            "Gemini response missing required emerging_trends or declining_areas."
        )

    result = _normalize_trend_sections(result)

    await set_cached_response(
        cache_key,
        result,
        "ai_insights",
        settings.GEMINI_MODEL,
        PROMPT_VERSION,
    )
    return result
