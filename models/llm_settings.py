"""
llm_settings.py

إعدادات مشتركة لاستدعاءات Azure OpenAI.

الـ OpenAI client الافتراضي مستني لحد 10 دقايق قبل ما يعتبر الطلب فشل،
وده كان بيخلّي التطبيق يبان معلّق. بنحدد timeout أقصر، وعدد محاولات
بسيط بيتعامل مع الأخطاء المؤقتة (429 / 5xx / انقطاع الشبكة).

    LLM_TIMEOUT_SECONDS   الافتراضي 45
    LLM_MAX_RETRIES       الافتراضي 2
"""

import os


def _read_number(name, default, cast):

    try:
        return cast(os.getenv(name, default))
    except (TypeError, ValueError):
        return cast(default)


LLM_TIMEOUT_SECONDS = max(_read_number("LLM_TIMEOUT_SECONDS", 45, float), 1.0)

LLM_MAX_RETRIES = max(_read_number("LLM_MAX_RETRIES", 2, int), 0)
