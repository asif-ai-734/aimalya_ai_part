from google import genai
import os

client = genai.Client(api_key="AIzaSyC4ZkWQ_5yyfTWzsBETBJB_byWmzj6hfd4")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Say ONLY the word: OK"
)

print("Gemini response:", response.text)
