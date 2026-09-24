import time

from pipeline import run_pipeline
from database import execute_query

from tests.evaluation.test_cases import TEST_CASES


MODELS = [
    "nano",
    "mini"
]


# ============================================================
# Normalize values
# ============================================================

def normalize_value(value):

    if value is None:
        return None

    if isinstance(value, float):
        return round(value, 2)

    return value


# ============================================================
# Compare scalar results
# ============================================================

def compare_scalar(
    actual_rows,
    expected_rows
):

    if not actual_rows or not expected_rows:
        return False

    actual_value = normalize_value(
        actual_rows[0][0]
    )

    expected_value = normalize_value(
        expected_rows[0][0]
    )

    return actual_value == expected_value


# ============================================================
# Compare exact rows using selected columns
# ============================================================

def compare_rows(
    actual_columns,
    actual_rows,
    expected_columns,
    expected_rows
):

    if not expected_rows:
        return not actual_rows

    if not actual_rows:
        return False

    actual_columns = [
        str(column)
        for column in actual_columns
    ]

    expected_columns = [
        str(column)
        for column in expected_columns
    ]

    indexes = []

    for column in expected_columns:

        if column not in actual_columns:
            return False

        indexes.append(
            actual_columns.index(column)
        )

    projected_actual_rows = []

    for row in actual_rows:

        projected_row = tuple(
            normalize_value(row[index])
            for index in indexes
        )

        projected_actual_rows.append(
            projected_row
        )

    normalized_expected_rows = []

    for row in expected_rows:

        normalized_row = tuple(
            normalize_value(value)
            for value in row
        )

        normalized_expected_rows.append(
            normalized_row
        )

    return (
        projected_actual_rows
        == normalized_expected_rows
    )


# ============================================================
# Compare rows + numeric aggregation value
# ============================================================

def compare_rows_with_numeric_value(
    actual_columns,
    actual_rows,
    expected_columns,
    expected_rows
):

    if not actual_rows or not expected_rows:
        return False

    actual_columns = [
        str(column)
        for column in actual_columns
    ]

    expected_columns = [
        str(column)
        for column in expected_columns
    ]

    # --------------------------------------------------------
    # Find indexes of expected text columns
    # --------------------------------------------------------

    expected_indexes = []

    for column in expected_columns:

        if column not in actual_columns:
            return False

        expected_indexes.append(
            actual_columns.index(column)
        )

    # --------------------------------------------------------
    # Find numeric columns in actual result
    # --------------------------------------------------------

    numeric_indexes = []

    for index in range(
        len(actual_columns)
    ):

        has_numeric_value = False

        for row in actual_rows:

            value = row[index]

            if isinstance(
                value,
                (int, float)
            ):

                has_numeric_value = True

                break

        if has_numeric_value:

            numeric_indexes.append(index)

    if not numeric_indexes:
        return False

    # Use the last numeric column
    value_index = numeric_indexes[-1]

    # --------------------------------------------------------
    # Build normalized actual rows
    # --------------------------------------------------------

    actual_normalized = []

    for row in actual_rows:

        text_values = tuple(
            normalize_value(
                row[index]
            )
            for index in expected_indexes
        )

        numeric_value = normalize_value(
            row[value_index]
        )

        actual_normalized.append(
            text_values + (numeric_value,)
        )

    # --------------------------------------------------------
    # Build expected rows
    #
    # Ground truth contains:
    # FirstName, LastName, TotalSpending
    # --------------------------------------------------------

    expected_normalized = []

    for row in expected_rows:

        text_values = tuple(
            normalize_value(value)
            for value in row[:-1]
        )

        numeric_value = normalize_value(
            row[-1]
        )

        expected_normalized.append(
            text_values + (numeric_value,)
        )

    return (
        actual_normalized
        == expected_normalized
    )


# ============================================================
# Evaluate one test case
# ============================================================

def evaluate_test_case(
    test_case,
    model_name
):

    question = test_case["question"]

    expected_type = test_case["expected_type"]

    comparison = test_case["comparison"]

    start_time = time.perf_counter()

    try:

        # ----------------------------------------------------
        # Run actual pipeline
        # ----------------------------------------------------

        result = run_pipeline(
            user_question=question,
            model_name=model_name
        )

        end_time = time.perf_counter()

        latency = end_time - start_time

        actual_type = result["type"]

        # ----------------------------------------------------
        # Check classification/type
        # ----------------------------------------------------

        if actual_type != expected_type:

            return {
                "passed": False,
                "latency": latency,
                "result": result,
                "error": (
                    f"Expected type "
                    f"'{expected_type}' "
                    f"but got "
                    f"'{actual_type}'"
                )
            }

        # ----------------------------------------------------
        # Type-only tests
        # ----------------------------------------------------

        if comparison == "type_only":

            return {
                "passed": True,
                "latency": latency,
                "result": result,
                "error": None
            }

        # ----------------------------------------------------
        # Execute Ground Truth SQL
        # ----------------------------------------------------

        ground_truth_sql = (
            test_case["ground_truth_sql"]
        )

        expected_columns, expected_rows = (
            execute_query(
                ground_truth_sql
            )
        )

        # ----------------------------------------------------
        # Scalar comparison
        # ----------------------------------------------------

        if comparison == "scalar":

            passed = compare_scalar(
                actual_rows=result["rows"],
                expected_rows=expected_rows
            )

        # ----------------------------------------------------
        # Exact row comparison
        # ----------------------------------------------------

        elif comparison == "rows":

            passed = compare_rows(
                actual_columns=result["columns"],
                actual_rows=result["rows"],
                expected_columns=test_case[
                    "expected_columns"
                ],
                expected_rows=expected_rows
            )

        # ----------------------------------------------------
        # Rows + numeric aggregation
        # ----------------------------------------------------

        elif comparison == "rows_with_numeric_value":

            passed = compare_rows_with_numeric_value(
                actual_columns=result["columns"],
                actual_rows=result["rows"],
                expected_columns=test_case[
                    "expected_columns"
                ],
                expected_rows=expected_rows
            )

        else:

            raise ValueError(
                f"Unknown comparison type: "
                f"{comparison}"
            )

        # ----------------------------------------------------
        # Return result
        # ----------------------------------------------------

        if passed:

            return {
                "passed": True,
                "latency": latency,
                "result": result,
                "error": None
            }

        return {
            "passed": False,
            "latency": latency,
            "result": result,
            "error": (
                "Actual result does not match "
                "the ground truth result."
            )
        }

    except Exception as e:

        end_time = time.perf_counter()

        latency = end_time - start_time

        return {
            "passed": False,
            "latency": latency,
            "result": None,
            "error": str(e)
        }


# ============================================================
# Evaluate model
# ============================================================

def evaluate_model(model_name):

    results = []

    print("\n" + "=" * 80)

    print(
        f"EVALUATING MODEL: "
        f"{model_name.upper()}"
    )

    print("=" * 80)

    for test_case in TEST_CASES:

        print("\n" + "-" * 80)

        print(
            f"TEST {test_case['id']}: "
            f"{test_case['question']}"
        )

        evaluation = evaluate_test_case(
            test_case=test_case,
            model_name=model_name
        )

        results.append(evaluation)

        if evaluation["passed"]:

            print("STATUS: PASS")

        else:

            print("STATUS: FAIL")

            if evaluation["error"]:

                print(
                    "ERROR:",
                    evaluation["error"]
                )

            if evaluation["result"]:

                if "sql" in evaluation["result"]:

                    print("\nGENERATED SQL:")

                    print(
                        evaluation["result"]["sql"]
                    )

        print(
            f"LATENCY: "
            f"{evaluation['latency']:.2f} seconds"
        )

    return results


# ============================================================
# Calculate summary
# ============================================================

def calculate_summary(
    results
):

    total_tests = len(results)

    passed_tests = sum(
        result["passed"]
        for result in results
    )

    failed_tests = (
        total_tests - passed_tests
    )

    total_latency = sum(
        result["latency"]
        for result in results
    )

    average_latency = (
        total_latency / total_tests
        if total_tests > 0
        else 0
    )

    accuracy = (
        passed_tests / total_tests * 100
        if total_tests > 0
        else 0
    )

    return {
        "total": total_tests,
        "passed": passed_tests,
        "failed": failed_tests,
        "accuracy": accuracy,
        "average_latency": average_latency
    }


# ============================================================
# Main
# ============================================================

def main():

    all_results = {}

    for model_name in MODELS:

        results = evaluate_model(
            model_name
        )

        summary = calculate_summary(
            results
        )

        all_results[model_name] = summary

    print("\n\n")

    print("=" * 80)
    print("FINAL MODEL EVALUATION")
    print("=" * 80)

    print(
        f"{'Model':<15}"
        f"{'Passed':<10}"
        f"{'Failed':<10}"
        f"{'Accuracy':<12}"
        f"{'Avg Latency':<15}"
    )

    print("-" * 80)

    for model_name, summary in all_results.items():

        print(
            f"{model_name:<15}"
            f"{summary['passed']:<10}"
            f"{summary['failed']:<10}"
            f"{summary['accuracy']:.1f}%"
            f"{'':<6}"
            f"{summary['average_latency']:.2f}s"
        )


if __name__ == "__main__":

    main()
