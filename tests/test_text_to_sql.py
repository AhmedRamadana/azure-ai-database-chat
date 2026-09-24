from text_to_sql import generate_sql


question = (
    "Which artist has the most tracks?"
)


response = generate_sql(
    question,
    model_name="nano"
)


print("\nModel Response:")
print(response)