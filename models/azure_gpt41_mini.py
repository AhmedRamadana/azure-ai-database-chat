import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY"
)

AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT"
)

AZURE_OPENAI_MINI_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_MINI_DEPLOYMENT"
)

if not AZURE_OPENAI_API_KEY:
    raise ValueError(
        "AZURE_OPENAI_API_KEY is missing"
    )

if not AZURE_OPENAI_ENDPOINT:
    raise ValueError(
        "AZURE_OPENAI_ENDPOINT is missing"
    )

if not AZURE_OPENAI_MINI_DEPLOYMENT:
    raise ValueError(
        "AZURE_OPENAI_MINI_DEPLOYMENT is missing"
    )

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=(
        f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}"
        "/openai/v1/"
    )
)


def ask_mini(prompt: str) -> str:

    response = client.responses.create(
        model=AZURE_OPENAI_MINI_DEPLOYMENT,
        input=prompt,

        # نفس القيمة بالظبط اللي في azure_gpt41_nano.py
        # عشان المقارنة بين الموديلين تكون عادلة (Fair Comparison) —
        # أي فرق في النتائج بعد كده يبقى مصدره قدرة الـ Model
        # نفسه، مش اختلاف في الإعدادات
        temperature=0.1
    )

    return response.output_text