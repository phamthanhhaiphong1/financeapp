import base64
import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENV_PATH = os.path.join(APP_DIR, ".env")
PROMPT_PATH = os.path.join(APP_DIR, "prompts", "fire_expense_parser_v2.md")

MODEL_NAME = "gemini-3.5-flash"

load_dotenv(ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_INSTRUCTIONS = f.read()


def _get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")
    return genai.Client(api_key=GEMINI_API_KEY)


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def parse_expense(input_data, is_image=False, mime_type="image/jpeg"):
    client = _get_client()

    if is_image:
        contents = [types.Part.from_bytes(data=base64.b64decode(input_data), mime_type=mime_type)]
    else:
        contents = [input_data]

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTIONS,
            response_mime_type="application/json",
        ),
    )
    return _extract_json(response.text)
