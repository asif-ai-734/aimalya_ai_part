#app.services.ai_insights_service.py

from app.core.config import get_settings
from google import genai
import json
import re

settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)


def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON in Gemini response")
    return json.loads(match.group())


def generate_ai_insights(summary: dict) -> dict:
    prompt = f"""
You are a senior business consultant.

Analyze the following business summary and provide insights and recommendations.

Rules:
- Be concise, executive-friendly
- Focus on business impact
- Recommendations must be actionable

Return STRICT JSON ONLY:

{{
  "business_health_score": number,
  "quick_insights": {{
    "what_customers_love": "string",
    "what_customers_dislike": "string",
    "emerging_opportunities": "string"
  }},
  "actionable_recommendations": [
    {{
      "title": "string",
      "priority": "High|Medium|Low",
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

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt
    )

    return extract_json(response.text)
