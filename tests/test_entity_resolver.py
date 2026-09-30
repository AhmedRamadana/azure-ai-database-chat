from entity_resolver import (
    resolve_entities
)


test_cases = [

    {
        "question": "Show me albums by AC DC",
        "expected": "AC/DC"
    },

    {
        "question": "Show me Metallica tracks",
        "expected": "Metallica"
    },

    {
        "question": "Show me customers from Brazill",
        "expected": "Brazil"
    },

    {
        "question": "Show me customers from Canada",
        "expected": "Canada"
    }

]


for index, test in enumerate(
    test_cases,
    start=1
):

    print(
        f"\n========== TEST {index} =========="
    )

    result = resolve_entities(
        user_question=test["question"],
        model_name="mini"
    )

    print(
        "Original:"
    )

    print(
        test["question"]
    )

    print(
        "\nResolved:"
    )

    print(
        result
    )

    print(
        "\nExpected Entity:"
    )

    print(
        test["expected"]
    )