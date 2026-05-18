#app.services.monthly_report_ai_service.py
import json

from app.core.config import get_settings
from app.db.cache import make_cache_key, get_cached_response, set_cached_response
from app.services.openai_analysis_client import generate_structured_json


settings = get_settings()
PROMPT_VERSION = "monthly_report_openai_v1"

MONTHLY_REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "executive_summary": {"type": "string"},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "estimated_impact": {"type": "string"},
                },
                "required": ["title", "description", "estimated_impact"],
            },
        },
        "action_plan": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["executive_summary", "recommendations", "action_plan"],
}

MONTHLY_REPORT_INSTRUCTIONS = """
You are a senior business analyst preparing a monthly business performance report.

Analyze the supplied report JSON and return data that matches the schema exactly.
Rules:
- Keep the executive summary concise and business-friendly.
- Recommendations must be practical and tied to the supplied metrics.
- estimated_impact must include a clear business outcome or measurable signal.
- action_plan items must be concrete next steps.
- Use only the supplied report data. Do not invent counts, ratings, dates, or
  percentages that are not present.
"""


async def generate_monthly_ai_summary(report_input: dict):
    cache_key = make_cache_key(
        "monthly_report",
        settings.OPENAI_MODEL,
        PROMPT_VERSION,
        report_input,
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    result = await generate_structured_json(
        schema_name="monthly_report",
        schema=MONTHLY_REPORT_SCHEMA,
        instructions=MONTHLY_REPORT_INSTRUCTIONS,
        input_text=f"Report data JSON:\n{json.dumps(report_input, indent=2)}",
    )

    await set_cached_response(
        cache_key,
        result,
        "monthly_report",
        settings.OPENAI_MODEL,
        PROMPT_VERSION,
    )
    return result
