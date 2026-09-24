from sql_executor import execute_sql


query = '''
DROP TABLE "Customer";
'''


columns, rows = execute_sql(query)


print("Columns:")
print(list(columns))

print("\nRows:")

for row in rows:
    print(row)