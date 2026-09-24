from database import execute_query


columns, rows = execute_query(
    'SELECT * FROM "Artist" LIMIT 5'
)


print("Columns:")
print(list(columns))


print("\nRows:")

for row in rows:
    print(row)