import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL مش موجود في .env — تأكد إنك حطيته صح"
    )

file_list = [
    "Album.csv",
    "Artist.csv",
    "Customer.csv",
    "Employee.csv",
    "Genre.csv",
    "Invoice.csv",
    "InvoiceLine.csv",
    "MediaType.csv",
    "Playlist.csv",
    "PlaylistTrack.csv",
    "Track.csv"
]

engine = create_engine(DATABASE_URL)

for file in file_list:
    try:
        temp_df = pd.read_csv(
            os.path.join("data", file)
        )

        table_name = file.split(".")[0]

        temp_df.to_sql(
            table_name,
            engine,
            if_exists="replace",
            index=False
        )

        print(
            f"Successfully uploaded {file} "
            f"to table '{table_name}'"
        )

    except Exception as e:
        print(f"Error uploading {file}: {e}")


print("\n--- Verifying table 'Artist' ---")

with engine.connect() as conn:
    try:
        result = conn.execute(
            text('SELECT * FROM "Artist" LIMIT 5;')
        )

        for row in result:
            print(row)

    except Exception as e:
        print(f"Could not verify: {e}")