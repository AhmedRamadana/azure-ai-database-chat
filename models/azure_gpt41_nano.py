import os

from dotenv import load_dotenv
from openai import OpenAI

from models.llm_settings import (
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SECONDS
)

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY"
)

AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT"
)

AZURE_OPENAI_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT"
)

if not AZURE_OPENAI_API_KEY:
    raise ValueError(
        "AZURE_OPENAI_API_KEY is missing"
    )

if not AZURE_OPENAI_ENDPOINT:
    raise ValueError(
        "AZURE_OPENAI_ENDPOINT is missing"
    )

if not AZURE_OPENAI_DEPLOYMENT:
    raise ValueError(
        "AZURE_OPENAI_DEPLOYMENT is missing"
    )

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=(
        f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}"
        "/openai/v1/"
    ),
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=LLM_MAX_RETRIES
)


def ask_nano(prompt: str) -> str:

    response = client.responses.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        input=prompt,

        # temperature منخفضة = إجابات أكثر ثباتًا (Deterministic)
        # مناسب لمهام دقيقة زي: Classification, SQL generation,
        # Answer generation من بيانات محددة
        # مش 0.0 بالظبط عشان نسيب هامش بسيط لصياغة طبيعية للجملة
        temperature=0.1
    )

    return response.output_text