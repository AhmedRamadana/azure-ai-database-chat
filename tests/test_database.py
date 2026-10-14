
from tests.helpers import get_demo_db, get_user

columns, rows = get_demo_db().execute(
    'SELECT * FROM "Artist" LIMIT 5'
)


print("Columns:")
print(list(columns))


print("\nRows:")

for row in rows:
    print(row)