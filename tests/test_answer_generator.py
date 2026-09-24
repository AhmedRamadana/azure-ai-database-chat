from answer_generator import generate_answer


question = "How many customers are there?"

sql_query = '''
SELECT COUNT(*) AS customer_count
FROM "Customer";
'''


columns = ["customer_count"]

rows = [
    (59,)
]


answer = generate_answer(
    user_question=question,
    sql_query=sql_query,
    columns=columns,
    rows=rows,
    model_name="mini"
)


print("\nFinal Answer:")
print(answer)