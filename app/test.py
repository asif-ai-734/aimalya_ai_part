from google import genai
from app.core.config import get_settings

settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)

response = client.models.generate_content(
    model=settings.GEMINI_MODEL,
    contents="Say ONLY the word: OK"
)

print("Gemini response:", response.text)
