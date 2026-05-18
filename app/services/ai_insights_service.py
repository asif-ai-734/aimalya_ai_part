#app.services.ai_insights_service.py

import json
import re

from app.core.config import get_settings
from app.db.cache import make_cache_key, get_cached_response, set_cached_response
from app.services.openai_analysis_client import generate_structured_json


settings = get_settings()
PROMPT_VERSION = "ai_insights_openai_v1"
PROGRAM_RECOMMENDATIONS_PROMPT_VERSION = "ai_insight_program_recommendations_openai_v1"
PROGRAM_RECOMMENDATION_TITLES = (
    "Staff_training",
    "Operation Consulting",
    "Performance Programs",
)

AI_INSIGHTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "business_health_score": {"type": "number"},
        "quick_insights": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "what_customers_love": {"type": "string"},
                "what_customers_dislike": {"type": "string"},
                "emerging_opportunities": {"type": "string"},
            },
            "required": [
                "what_customers_love",
                "what_customers_dislike",
                "emerging_opportunities",
            ],
        },
        "emerging_trends": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "trend": {"type": "string"},
                    "mentions": {"type": "number"},
                },
                "required": ["trend", "mentions"],
            },
        },
        "declining_areas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "trend": {"type": "string"},
                    "mentions": {"type": "number"},
                },
                "required": ["trend", "mentions"],
            },
        },
        "actionable_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"],
                    },
                    "description": {"type": "string"},
                    "evidence": {"type": "string"},
                    "business_impact": {"type": "string"},
                    "expected_improvement": {"type": "string"},
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "title",
                    "priority",
                    "description",
                    "evidence",
                    "business_impact",
                    "expected_improvement",
                    "actions",
                ],
            },
        },
    },
    "required": [
        "business_health_score",
        "quick_insights",
        "emerging_trends",
        "declining_areas",
        "actionable_recommendations",
    ],
}

PROGRAM_RECOMMENDATIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "actionable_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {
                        "type": "string",
                        "enum": [
                            "Staff_training",
                            "Operation Consulting",
                            "Performance Programs",
                        ],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"],
                    },
                    "description": {"type": "string"},
                    "evidence": {"type": "string"},
                    "business_impact": {"type": "string"},
                    "improvement": {"type": "string"},
                    "actions_to_do": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "title",
                    "priority",
                    "description",
                    "evidence",
                    "business_impact",
                    "improvement",
                    "actions_to_do",
                ],
            },
        },
    },
    "required": ["actionable_recommendations"],
}


def _build_prompt(retry: bool = False) -> str:
    retry_instruction = ""
    if retry:
        retry_instruction = """
Your previous response missed required insight sections.
Return the same JSON shape again, but make sure emerging_trends and
declining_areas are non-empty arrays.
"""

    return f"""
You are a senior business consultant for local service businesses.

Analyze the supplied business summary JSON and produce decision-ready insights.
Return data that matches the schema exactly.

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
- Use only the supplied summary data. If a trend must be inferred, base it on
  the nearest available metrics, strengths, issues, goals, or category scores.
- Do not invent competitor names, exact counts, percentages, or ratings that
  are not supported by the summary.

{retry_instruction}
"""


def _build_program_recommendations_prompt(retry: bool = False) -> str:
    retry_instruction = ""
    if retry:
        retry_instruction = """
Your previous response did not match the required card format.
Return the same JSON shape again, but make sure:
- evidence is a short metric only, not a sentence
- business_impact includes a valid numeric score, percentage, rating, or count
- improvement includes a valid numeric score, percentage, rating, or count
"""

    return f"""
You are a senior business consultant for local service businesses.

Analyze the supplied business summary JSON and create exactly three actionable
recommendations. The recommendation titles must be exactly these values and in
this order:
1. Staff_training
2. Operation Consulting
3. Performance Programs

Rules:
- Be concise, executive-friendly, and specific to the business data
- Include priority as High, Medium, or Low
- evidence must be a short metric only, not descriptive text. Good examples:
  "23 mentions in last 30 days (+15% vs previous month)"
  "Service score 62/100 | 8 negative mentions"
- business_impact must show a valid score, percentage, rating, or count. Good examples:
  "High - affecting 18% of negative reviews"
  "Revenue risk score 7/10"
- improvement must show a valid score, percentage, rating, or count. Good examples:
  "+12% satisfaction"
  "+8 points service score"
- Do not use placeholder text such as "No issue found"
- Each actions_to_do list must contain concrete operational actions
- Use only the supplied summary data. If you infer an opportunity, tie it to the
  nearest available metric, review signal, goal, or category score.
- Do not invent exact counts, scores, percentages, ratings, or competitor names.

{retry_instruction}
"""


def _business_summary_input(summary: dict) -> str:
    return f"Business summary JSON:\n{json.dumps(summary, indent=2)}"


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


def _title_key(title: str) -> str:
    return "".join(
        character for character in str(title).casefold() if character.isalnum()
    )


def _string_value(value) -> str:
    return str(value or "").strip()


def _actions_to_do(value) -> list[str]:
    if isinstance(value, list):
        return [_string_value(item) for item in value if _string_value(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _priority_value(value) -> str:
    priority = _string_value(value).capitalize()
    if priority in {"High", "Medium", "Low"}:
        return priority
    return ""


def _has_metric(value: str) -> bool:
    return bool(re.search(r"\d", value or ""))


def _has_score(value: str) -> bool:
    if not _has_metric(value):
        return False

    return bool(
        re.search(
            r"%|/|score|points?|pts?|rating|reviews?|mentions?|satisfaction|"
            r"retention|conversion|revenue|risk|volume",
            value,
            re.IGNORECASE,
        )
    )


def _normalize_program_recommendations(result: dict) -> dict:
    raw_recommendations = (
        result.get("actionable_recommendations")
        or result.get("recommendations")
        or []
    )
    if not isinstance(raw_recommendations, list):
        raise ValueError("OpenAI response recommendations must be a list.")

    recommendations_by_title = {
        _title_key(item.get("title")): item
        for item in raw_recommendations
        if isinstance(item, dict) and item.get("title")
    }

    normalized = []
    for title in PROGRAM_RECOMMENDATION_TITLES:
        item = recommendations_by_title.get(_title_key(title))
        if not item:
            raise ValueError(f"OpenAI response missing recommendation: {title}.")

        recommendation = {
            "title": title,
            "priority": _priority_value(item.get("priority")),
            "description": _string_value(item.get("description")),
            "evidence": _string_value(item.get("evidence")),
            "business_impact": _string_value(item.get("business_impact")),
            "improvement": _string_value(
                item.get("improvement") or item.get("expected_improvement")
            ),
            "actions_to_do": _actions_to_do(
                item.get("actions_to_do") or item.get("actions")
            ),
        }

        missing_fields = [
            field
            for field in (
                "priority",
                "description",
                "evidence",
                "business_impact",
                "improvement",
            )
            if not recommendation[field]
        ]
        invalid_metric_fields = [
            field
            for field in ("evidence", "business_impact", "improvement")
            if not _has_score(recommendation[field])
        ]
        if (
            missing_fields
            or invalid_metric_fields
            or not recommendation["actions_to_do"]
        ):
            raise ValueError(
                "OpenAI response missing required recommendation fields."
            )

        normalized.append(recommendation)

    return {"actionable_recommendations": normalized}


async def generate_ai_insights(summary: dict) -> dict:
    cache_key = make_cache_key(
        "ai_insights",
        settings.OPENAI_MODEL,
        PROMPT_VERSION,
        summary,
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    result = await generate_structured_json(
        schema_name="ai_insights",
        schema=AI_INSIGHTS_SCHEMA,
        instructions=_build_prompt(),
        input_text=_business_summary_input(summary),
    )

    if not _has_required_ai_sections(result):
        result = await generate_structured_json(
            schema_name="ai_insights_retry",
            schema=AI_INSIGHTS_SCHEMA,
            instructions=_build_prompt(retry=True),
            input_text=_business_summary_input(summary),
        )

    if not _has_required_ai_sections(result):
        raise ValueError(
            "OpenAI response missing required emerging_trends or declining_areas."
        )

    result = _normalize_trend_sections(result)

    await set_cached_response(
        cache_key,
        result,
        "ai_insights",
        settings.OPENAI_MODEL,
        PROMPT_VERSION,
    )
    return result


async def generate_program_recommendations(summary: dict) -> dict:
    cache_key = make_cache_key(
        "ai_insight_program_recommendations",
        settings.OPENAI_MODEL,
        PROGRAM_RECOMMENDATIONS_PROMPT_VERSION,
        summary,
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    try:
        result = _normalize_program_recommendations(
            await generate_structured_json(
                schema_name="program_recommendations",
                schema=PROGRAM_RECOMMENDATIONS_SCHEMA,
                instructions=_build_program_recommendations_prompt(),
                input_text=_business_summary_input(summary),
            )
        )
    except ValueError:
        result = _normalize_program_recommendations(
            await generate_structured_json(
                schema_name="program_recommendations_retry",
                schema=PROGRAM_RECOMMENDATIONS_SCHEMA,
                instructions=_build_program_recommendations_prompt(retry=True),
                input_text=_business_summary_input(summary),
            )
        )

    await set_cached_response(
        cache_key,
        result,
        "ai_insight_program_recommendations",
        settings.OPENAI_MODEL,
        PROGRAM_RECOMMENDATIONS_PROMPT_VERSION,
    )
    return result
