
#app.services.gemini_client.py
import asyncio
from google import genai
from app.core.config import get_settings
from app.db.cache import make_cache_key, get_cached_response, set_cached_response
import json
import re

# -------------------------------------------------
# Config
# -------------------------------------------------
settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)
PROMPT_VERSION = "review_v2"

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
    ]
}

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def extract_json_from_markdown(text: str) -> dict:
    """
    Extract JSON safely from Gemini responses
    """
    fence_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    json_match = re.search(r"\{.*?\}", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())

    raise ValueError("No valid JSON found in Gemini response")


def extract_criteria_scores(sentiment: str, keywords: list[str]) -> dict:
    """
    Convert sentiment + keywords into criteria scores (NO Gemini call)
    """
    sentiment_score_map = {
        "Positive": 5,
        "Neutral": 3,
        "Negative": 2
    }

    base_score = sentiment_score_map.get(sentiment, 3)
    keyword_text = " ".join(keywords)

    criteria_scores = {}

    for criteria, triggers in CRITERIA_KEYWORDS.items():
        if any(trigger in keyword_text for trigger in triggers):
            criteria_scores[criteria] = base_score

    return criteria_scores


# -------------------------------------------------
# Main Gemini Review Analysis
# -------------------------------------------------
async def analyze_review_with_gemini(review_text: str) -> dict:
    cache_key = make_cache_key(
        "review_analysis",
        settings.GEMINI_MODEL,
        PROMPT_VERSION,
        {"review_text": review_text},
    )
    cached = await get_cached_response(cache_key)
    if cached:
        return cached

    prompt = f"""
You are an AI customer experience analyst.

Analyze the review and extract insights.

Rules:
- Use exact phrases copied from the review text
- Keep phrases under 12 words
- Emotions must be chosen from:
  Satisfaction, Happiness, Frustration, Disappointment, Anger, Neutral
- Keywords must be short meaningful phrases (not single generic words)
- If sentiment is Positive → fill strengths, keep issues empty
- If sentiment is Negative → fill issues, keep strengths empty
- If sentiment is Neutral → you may fill both

Return STRICT JSON ONLY:

{{
  "sentiment": "Positive|Neutral|Negative",
  "emotions": ["Satisfaction"],
  "strengths": ["short phrase"],
  "issues": ["short phrase"],
  "keywords": ["short phrase"]
}}

Review:
\"\"\"{review_text}\"\"\"
"""

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    raw_text = response.text.strip()
    print("GEMINI RAW RESPONSE:\n", raw_text)

    data = extract_json_from_markdown(raw_text)

    # Normalize
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
        "criteria_scores": criteria_scores
    }
    await set_cached_response(
        cache_key,
        result,
        "review_analysis",
        settings.GEMINI_MODEL,
        PROMPT_VERSION,
    )
    return result
