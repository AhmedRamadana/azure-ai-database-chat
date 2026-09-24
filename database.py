import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# -----------------------------------
# Load Environment Variables
# -----------------------------------

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")


# -----------------------------------
# Validate Database URL
# -----------------------------------

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL is missing from .env"
    )


# -----------------------------------
# Create Database Engine
# -----------------------------------

engine = create_engine(DATABASE_URL)


# -----------------------------------
# Execute SQL Query
# -----------------------------------

def execute_query(query: str):

    with engine.connect() as connection:

        result = connection.execute(
            text(query)
        )

        rows = result.fetchall()

        columns = result.keys()

        return columns, rows