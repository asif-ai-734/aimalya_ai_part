from openai import OpenAI

from app.core.config import get_settings


settings = get_settings()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

response = client.responses.create(
    model=settings.OPENAI_MODEL,
    input="Say hello from OpenAI in one short sentence.",
)

print("OpenAI response:", response.output_text)
