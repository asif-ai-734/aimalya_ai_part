from google import genai
from app.core.config import get_settings
import json, re 



settings = get_settings()
client= genai.Client(api_key= settings.GEMINI_API_KEY)

def _extract_json(text: str):
    match= re.search (r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group())

def generate_competitive_strategy(playload: dict):
    prompt= f"""
    You are a business strategy consultant.

    Analyze this competitive comparison and return STRICT JSON:

    {{
        "summary": "string",
        "recommendations": ["string"]
    }}

    Data:
    {
        json.dumps(playload, indent=2)
    }
    """

    res = client.models.generate_content(
        model = settings.GEMINI_MODEL,
        contents = prompt
    )

    return _extract_json(res.text)