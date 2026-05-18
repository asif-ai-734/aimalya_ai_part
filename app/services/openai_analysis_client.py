# app.services.openai_analysis_client.py
import json
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.db.cache import make_cache_key, get_cached_response, set_cached_response


settings = get_settings()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PROMPT_VERSION = "review_openai_v1"

CRITERIA = ["Service", "Quality", "Atmosphere", "Value", "Cleanliness"]

CRITERIA_KEYWORDS = {
    "Service": [
        "service", "staff", "wait", "slow", "fast", "rude", "friendly"
    ],
    "Quality": [
        "quality", "coffee", "food", "taste", "fresh", "excellent", "good"
    ],
    "Atmosphere": [
        "atmosphere", "ambiance", "ambience", "environment", "decor", "music"
    ],
    "Value": [
        "price", "priced", "overpriced", "cheap", "expensive", "value"
    ],
    "Cleanliness": [
        "clean", "dirty", "hygiene", "messy", "neat"
    ],
}

REVIEW_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sentiment": {
            "type": "string",
            "enum": ["Positive", "Neutral", "Negative"],
        },
        "emotions": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "Satisfaction",
                    "Happiness",
                    "Frustration",
                    "Disappointment",
                    "Anger",
                    "Neutral",
                ],
            },
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "sentiment",
        "emotions",
        "strengths",
        "issues",
        "keywords",
    ],
}

REVIEW_ANALYSIS_INSTRUCTIONS = """
You are an expert customer-experience analyst for local businesses.
Analyze exactly one customer review using only the supplied review text.

Return compact data that matches the schema.
Rules:
- Use exact or near-exact phrases from the review for strengths, issues, and keywords.
- Keep every phrase under 12 words.
- Keywords must be meaningful short phrases, not single generic words.
- Choose sentiment as Positive, Neutral, or Negative.
- If sentiment is Positive, fill strengths and keep issues empty.
- If sentiment is Negative, fill issues and keep strengths empty.
- If sentiment is Neutral or mixed, you may fill both strengths and issues.
- Choose emotions only from the schema enum.
- Do not invent names, metrics, facts, or details not present in the review.
"""


async def generate_structured_json(
    *,
    schema_name: str,
    schema: dict[str, Any],
    instructions: str,
    input_text: str,
) -> dict[str, Any]:
    response = await client.responses.create(
        model=settings.OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": instructions.strip(),
            },
            {
                "role": "user",
                "content": input_text.strip(),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
            "verbosity": "low",
        },
    )

    raw_text = (getattr(response, "output_text", "") or "").strip()
    if not raw_text:
        raise ValueError("OpenAI response did not include structured output.")

    return json.loads(raw_text)


def extract_criteria_scores(sentiment: str, keywords: list[str]) -> dict:
    sentiment_score_map = {
        "Positive": 5,
        "Neutral": 3,
        "Negative": 2,
    }

    base_score = sentiment_score_map.get(sentiment, 3)
    keyword_text = " ".join(keywords)
    criteria_scores = {}

    for criteria, triggers in CRITERIA_KEYWORDS.items():
        if any(trigger in keyword_text for trigger in triggers):
            criteria_scores[criteria] = base_score

    return criteria_scores


async def analyze_review_with_openai(review_text: str) -> dict:
    if not (review_text or "").strip():
        return {
            "sentiment": "Neutral",
            "emotions": ["Neutral"],
            "strengths": [],
            "issues": [],
            "keywords": [],
            "criteria_scores": {},
        }

    cache_key = make_cache_key(
        "review_analysis",
        settings.OPENAI_MODEL,
        PROMPT_VERSION,
        {"review_text": review_text},
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    data = await generate_structured_json(
        schema_name="review_analysis",
        schema=REVIEW_ANALYSIS_SCHEMA,
        instructions=REVIEW_ANALYSIS_INSTRUCTIONS,
        input_text=f'Review text:\n"""{review_text}"""',
    )

    sentiment = data["sentiment"].capitalize()
    strengths = [s.strip() for s in data.get("strengths", []) if s.strip()]
    issues = [i.strip() for i in data.get("issues", []) if i.strip()]
    emotions = data.get("emotions", [])
    keywords = data.get("keywords", [])

    criteria_keywords = [
        *[s.lower() for s in strengths],
        *[i.lower() for i in issues],
    ]
    criteria_scores = extract_criteria_scores(sentiment, criteria_keywords)

    result = {
        "sentiment": sentiment,
        "emotions": emotions,
        "strengths": strengths,
        "issues": issues,
        "keywords": keywords,
        "criteria_scores": criteria_scores,
    }
    await set_cached_response(
        cache_key,
        result,
        "review_analysis",
        settings.OPENAI_MODEL,
        PROMPT_VERSION,
    )
    return result
