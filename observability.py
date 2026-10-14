"""
observability.py

Logging بسيط ومنظّم. القاعدة: **مفيش نص سؤال ولا إجابة ولا قيم داتا في
اللوج** (ممكن تكون حساسة)، بس بيانات تشغيلية: النوع، الـ role، النموذج،
الزمن، عدد الصفوف، أسماء الأعمدة المحجوبة.

    LOG_LEVEL=INFO   (DEBUG / INFO / WARNING / ERROR)
"""

import logging
import os

logger = logging.getLogger("chatdb")

_configured = False


def setup_logging():
    """
    آمنة تتنادى أكتر من مرة (Streamlit بيعيد تشغيل السكربت مع كل تفاعل):
    الـ handler بيتضاف مرة واحدة، والمستوى (LOG_LEVEL) بيتضبط دايمًا.
    """

    global _configured

    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    logger.setLevel(getattr(logging, level_name, logging.INFO))

    if _configured:
        return

    if not logger.handlers:

        handler = logging.StreamHandler()

        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )

        logger.addHandler(handler)

    logger.propagate = False

    _configured = True


def log_request(
    result_type: str,
    model: str,
    role: str,
    dialect: str,
    latency_seconds: float,
    rows: int = 0,
    restricted_fields=None
):

    logger.info(
        "request type=%s model=%s role=%s db=%s latency=%.2fs "
        "rows=%d restricted=%s",
        result_type,
        model,
        role,
        dialect,
        latency_seconds,
        rows,
        list(restricted_fields or [])
    )
