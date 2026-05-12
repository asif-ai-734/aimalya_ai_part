import asyncio
from google import genai
from app.core.config import get_settings
import json, re 



settings = get_settings()
client= genai.Client(api_key= settings.GEMINI_API_KEY)

def _extract_json(text: str):
    match= re.search (r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group())


def _string_value(value) -> str:
    return str(value or "").strip()


def _evidence_by_id(playload: dict) -> dict:
    evidence = playload.get("where_competitors_excel_evidence") or []
    if not isinstance(evidence, list):
        return {}
    return {
        item["evidence_id"]: item
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id")
    }


def _normalize_competitor_excel(result: dict, playload: dict) -> list[dict]:
    evidence_by_id = _evidence_by_id(playload)
    raw_items = result.get("where_competitors_excel", [])
    if not isinstance(raw_items, list):
        raw_items = []

    normalized = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        evidence_id = _string_value(item.get("evidence_id"))
        evidence = evidence_by_id.get(evidence_id)
        if not evidence:
            continue

        title = _string_value(item.get("title"))
        description = _string_value(item.get("description"))
        opportunity = _string_value(item.get("opportunity"))
        if not title or not description or not opportunity:
            continue

        normalized.append({
            "title": title,
            "description": description,
            "opportunity": opportunity,
            "evidence_id": evidence_id,
            "leader": evidence["leader"],
            "metric": evidence["metric"],
            "competitor_value": evidence["competitor_value"],
            "my_value": evidence["my_value"],
            "gap": evidence["gap"],
            "relationship": evidence["relationship"],
        })

    if evidence_by_id and not normalized:
        raise ValueError(
            "AI response must include at least one data-backed competitor-excel item."
        )

    return normalized[:3]


def _normalize_recommendations(result: dict) -> list[dict]:
    raw_recommendations = result.get("recommendations", [])
    if not isinstance(raw_recommendations, list):
        raw_recommendations = []

    recommendations = []
    for item in raw_recommendations:
        if isinstance(item, dict):
            title = _string_value(item.get("title"))
            description = _string_value(item.get("description"))
        else:
            text = _string_value(item)
            title = text.split(".")[0][:60].strip()
            description = text

        if title and description:
            recommendations.append({
                "title": title,
                "description": description,
            })

    return recommendations[:4]


def _normalize_competitive_strategy(result: dict, playload: dict) -> dict:
    return {
        "where_competitors_excel": _normalize_competitor_excel(result, playload),
        "recommendations": _normalize_recommendations(result),
    }


def _build_prompt(playload: dict, retry: bool = False) -> str:
    retry_instruction = ""
    if retry:
        retry_instruction = """
    Your previous response did not include a valid data-backed
    where_competitors_excel item. Return the same JSON shape again, and make
    sure every where_competitors_excel item uses an evidence_id from
    where_competitors_excel_evidence.
    """

    return f"""
    You are a business strategy consultant.

    Analyze this competitive comparison and return STRICT JSON:

    {{
        "where_competitors_excel": [
            {{
                "title": "short title",
                "description": "short description using the evidence values",
                "opportunity": "short action based on the evidence",
                "evidence_id": "id from where_competitors_excel_evidence"
            }}
        ],
        "recommendations": [
            {{
                "title": "short title",
                "description": "short description"
            }}
        ]
    }}

    Rules:
    - where_competitors_excel is required and must not be empty when
      where_competitors_excel_evidence is not empty.
    - Build where_competitors_excel only from where_competitors_excel_evidence.
    - Do not invent competitor names, metrics, scores, counts, or gaps.
    - Prefer evidence where relationship is competitor_leads.
    - If competitors do not lead your business on any metric, use the strongest
      actual competitor_strength evidence and describe it honestly as strength
      or close competition, not as a false lead.
    - Return 3 to 4 recommendations.
    - Each title must be concise, 3 to 6 words.
    - Each description must be concise, 1 sentence.
    - Focus on competitor gaps, competitive advantages, and business goals.
    - Do not use random examples or predefined fallback content.

    {retry_instruction}

    Data:
    {
        json.dumps(playload, indent=2)
    }
    """


async def generate_competitive_strategy(playload: dict):
    prompt = _build_prompt(playload)

    res = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    try:
        return _normalize_competitive_strategy(_extract_json(res.text), playload)
    except ValueError:
        retry_res = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.GEMINI_MODEL,
            contents=_build_prompt(playload, retry=True),
        )
        return _normalize_competitive_strategy(
            _extract_json(retry_res.text),
            playload,
        )
