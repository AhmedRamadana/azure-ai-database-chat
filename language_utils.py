def detect_language(text: str) -> str:
    """
    Detect whether the user question is primarily
    Arabic, English, or Mixed.
    """

    arabic_chars = 0
    english_chars = 0

    for char in text:

        if "\u0600" <= char <= "\u06FF":
            arabic_chars += 1

        elif char.isascii() and char.isalpha():
            english_chars += 1

    total_chars = arabic_chars + english_chars

    if total_chars == 0:
        return "english"

    arabic_ratio = arabic_chars / total_chars
    english_ratio = english_chars / total_chars

    # Mostly Arabic
    if arabic_ratio >= 0.6:
        return "arabic"

    # Mostly English
    if english_ratio >= 0.8:
        return "english"

    # Both languages are significantly present
    return "mixed"