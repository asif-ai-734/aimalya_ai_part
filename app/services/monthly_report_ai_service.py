#app.services.monthly_report_ai_service.py
import asyncio
from google import genai
from app.core.config import get_settings
from app.db.cache import make_cache_key, get_cached_response, set_cached_response
import json
import re

settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)
PROMPT_VERSION = "monthly_report_v2"


def _extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON in Gemini response")
    return json.loads(match.group())


async def generate_monthly_ai_summary(report_input: dict):
    cache_key = make_cache_key(
        "monthly_report",
        settings.GEMINI_MODEL,
        PROMPT_VERSION,
        report_input,
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    prompt = f"""
You are a senior business analyst preparing a business performance report.

Return STRICT JSON ONLY:

{{
  "executive_summary": "string",
  "recommendations": [
    {{
      "title": "string",
      "description": "string",
      "estimated_impact": "string"
    }}
  ],
  "action_plan": ["string"]
}}

Report data:
{json.dumps(report_input, indent=2)}
"""

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    result = _extract_json(response.text)
    await set_cached_response(
        cache_key,
        result,
        "monthly_report",
        settings.GEMINI_MODEL,
        PROMPT_VERSION,
    )
    return result
