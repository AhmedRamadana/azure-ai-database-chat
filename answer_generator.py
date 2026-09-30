from prompts.answer_prompt import build_answer_prompt
from models.model_manager import get_model
from language_utils import detect_language


# ============================================================
# Configuration
# ============================================================

# أقصى عدد صف نبعته فعليًا للـ LLM لو النتيجة الحقيقية كبيرة —
# رقم أصغر بكتير من الـ Display Cap (200) لأن هدفه توفير التكلفة
# والـ Latency، مش عرض بصري
LLM_SAMPLE_SIZE = 15


def generate_answer(
    user_question: str,
    sql_query: str,
    columns,
    rows,
    real_total: int,
    model_name: str = "nano"
):

    language = detect_language(
        user_question
    )

    # --------------------------------------------------------
    # لو العدد الحقيقي أكبر من حجم العيّنة، نبعت عيّنة بس للـ
    # LLM (مش كل الصفوف) — العدد الحقيقي (real_total) بيتبعت
    # منفصل عشان الـ LLM يقدر يقول "فيه X نتيجة" بدقة، حتى لو
    # مشافش غير عيّنة صغيرة منهم
    # --------------------------------------------------------

    if real_total > LLM_SAMPLE_SIZE:

        rows_for_llm = rows[:LLM_SAMPLE_SIZE]

    else:

        rows_for_llm = rows

    prompt = build_answer_prompt(
        user_question=user_question,
        sql_query=sql_query,
        columns=columns,
        rows=rows_for_llm,
        real_total=real_total,
        language=language
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()