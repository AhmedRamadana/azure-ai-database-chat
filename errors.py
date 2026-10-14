"""
errors.py

تحويل أي Exception لرسالة آمنة ومفهومة للمستخدم، وتسجيل التفاصيل الكاملة في
اللوج (على السيرفر بس).

قبل كده التطبيق كان بيعرض نص الـ Exception زي ما هو، وده ممكن يكشف SQL أو
تفاصيل اتصال أو رسائل داخلية. دلوقتي المستخدم بيشوف:

    - رسالة ثابتة حسب نوع المشكلة (بلغته: عربي / إنجليزي)
    - كود مرجعي قصير (Ref) يقدر يبعته لو عايز يبلّغ عن المشكلة

والتفاصيل الكاملة (النوع + الـ traceback) في اللوج مربوطة بنفس الـ Ref.
"""

import logging
import uuid

logger = logging.getLogger("chatdb")


# كود المشكلة -> الرسالة (english / arabic)
MESSAGES = {
    "LLM_TIMEOUT": {
        "english": "The AI service took too long to respond. Please try again.",
        "arabic": "خدمة الذكاء الاصطناعي اتأخرت في الرد. حاول تاني.",
    },
    "LLM_RATE_LIMIT": {
        "english": "The AI service is busy right now. Please wait a moment and try again.",
        "arabic": "خدمة الذكاء الاصطناعي مشغولة دلوقتي. استنى شوية وحاول تاني.",
    },
    "LLM_AUTH": {
        "english": "The AI service rejected the app's credentials. Please contact the administrator.",
        "arabic": "خدمة الذكاء الاصطناعي رفضت بيانات الدخول بتاعة التطبيق. كلّم المسؤول.",
    },
    "LLM_CONNECTION": {
        "english": "Could not reach the AI service. Check the connection and try again.",
        "arabic": "مقدرتش أوصل لخدمة الذكاء الاصطناعي. اتأكد من الاتصال وحاول تاني.",
    },
    "LLM_CONTENT_FILTER": {
        "english": "The AI service blocked this request. Please rephrase your question.",
        "arabic": "خدمة الذكاء الاصطناعي منعت الطلب ده. جرّب تعيد صياغة السؤال.",
    },
    "LLM_UNAVAILABLE": {
        "english": "The AI service is temporarily unavailable. Please try again shortly.",
        "arabic": "خدمة الذكاء الاصطناعي مش متاحة مؤقتًا. حاول تاني بعد شوية.",
    },
    "DB_ERROR": {
        "english": "The database could not complete this request (it may have timed out or lost connection).",
        "arabic": "الداتابيز مقدرتش تنفّذ الطلب ده (ممكن يكون خد وقت طويل أو الاتصال اتقطع).",
    },
    "QUERY_FAILED": {
        "english": "I couldn't turn this into a safe query. Please try rephrasing your question.",
        "arabic": "مقدرتش أحوّل السؤال ده لاستعلام آمن. جرّب تعيد صياغته.",
    },
    "UNKNOWN": {
        "english": "Something went wrong. Please try again.",
        "arabic": "حصلت مشكلة. حاول تاني.",
    },
}


def classify_error(error: BaseException) -> str:
    """
    كود المشكلة حسب نوع الـ Exception (من غير ما نعرض نصه).
    """

    try:
        import openai
    except ImportError:  # pragma: no cover
        openai = None

    if openai is not None:

        if isinstance(error, openai.APITimeoutError):
            return "LLM_TIMEOUT"

        if isinstance(error, openai.RateLimitError):
            return "LLM_RATE_LIMIT"

        if isinstance(
            error,
            (openai.AuthenticationError, openai.PermissionDeniedError)
        ):
            return "LLM_AUTH"

        if isinstance(error, openai.APIConnectionError):
            return "LLM_CONNECTION"

        if isinstance(error, openai.BadRequestError):

            if "content_filter" in str(getattr(error, "code", "")) + str(
                getattr(error, "body", "")
            ):
                return "LLM_CONTENT_FILTER"

            return "LLM_UNAVAILABLE"

        if isinstance(error, openai.APIStatusError):
            return "LLM_UNAVAILABLE"

        if isinstance(error, openai.OpenAIError):
            return "LLM_UNAVAILABLE"

    try:
        from sqlalchemy.exc import SQLAlchemyError
    except ImportError:  # pragma: no cover
        SQLAlchemyError = ()

    if SQLAlchemyError and isinstance(error, SQLAlchemyError):
        return "DB_ERROR"

    # ValueError / RuntimeError جاية من التحقق (validator) أو من استنفاد
    # محاولات تصحيح الـ SQL أو من رد LLM مش بالشكل المتوقع.
    if isinstance(error, (ValueError, RuntimeError)):
        return "QUERY_FAILED"

    return "UNKNOWN"


def handle_error(
    error: BaseException,
    language: str = "english",
    context: dict = None
) -> dict:
    """
    بتسجّل الخطأ كامل في اللوج وبترجّع:

        {"code": ..., "ref": "ab12cd34", "message": "...(Ref: ab12cd34)"}

    context: بيانات للتشخيص (النوع/الـ role/النموذج). مفيهاش نص السؤال.
    """

    code = classify_error(error)

    reference = uuid.uuid4().hex[:8]

    logger.error(
        "request failed ref=%s code=%s error_type=%s context=%s",
        reference,
        code,
        type(error).__name__,
        context or {},
        exc_info=error
    )

    texts = MESSAGES[code]

    text = texts["arabic" if language == "arabic" else "english"]

    return {
        "code": code,
        "ref": reference,
        "message": f"{text} (Ref: {reference})"
    }
