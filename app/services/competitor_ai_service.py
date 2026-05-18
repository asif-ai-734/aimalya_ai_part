import json

from app.services.openai_analysis_client import generate_structured_json


COMPETITIVE_STRATEGY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "where_competitors_excel": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "opportunity": {"type": "string"},
                    "evidence_id": {"type": "string"},
                },
                "required": [
                    "title",
                    "description",
                    "opportunity",
                    "evidence_id",
                ],
            },
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        },
    },
    "required": ["where_competitors_excel", "recommendations"],
}


def _string_value(value) -> str:
    return str(value or "").strip()


def _evidence_by_id(payload: dict) -> dict:
    evidence = payload.get("where_competitors_excel_evidence") or []
    if not isinstance(evidence, list):
        return {}
    return {
        item["evidence_id"]: item
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id")
    }


def _normalize_competitor_excel(result: dict, payload: dict) -> list[dict]:
    evidence_by_id = _evidence_by_id(payload)
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
            "OpenAI response must include at least one data-backed "
            "competitor-excel item."
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


def _normalize_competitive_strategy(result: dict, payload: dict) -> dict:
    return {
        "where_competitors_excel": _normalize_competitor_excel(result, payload),
        "recommendations": _normalize_recommendations(result),
    }


def _build_prompt(retry: bool = False) -> str:
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

Analyze the supplied competitive comparison JSON and return data that matches
the schema exactly.

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
"""


async def generate_competitive_strategy(payload: dict):
    result = await generate_structured_json(
        schema_name="competitive_strategy",
        schema=COMPETITIVE_STRATEGY_SCHEMA,
        instructions=_build_prompt(),
        input_text=f"Competitive comparison JSON:\n{json.dumps(payload, indent=2)}",
    )

    try:
        return _normalize_competitive_strategy(result, payload)
    except ValueError:
        retry_result = await generate_structured_json(
            schema_name="competitive_strategy_retry",
            schema=COMPETITIVE_STRATEGY_SCHEMA,
            instructions=_build_prompt(retry=True),
            input_text=(
                "Competitive comparison JSON:\n"
                f"{json.dumps(payload, indent=2)}"
            ),
        )
        return _normalize_competitive_strategy(retry_result, payload)
