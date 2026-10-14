TEST_CASES = [

    # ============================================================
    # 1. Count artists
    # ============================================================

    {
        "id": 1,
        "question": "How many artists are there?",
        "expected_type": "database",
        "comparison": "scalar",
        "ground_truth_sql": """
            SELECT COUNT(*) AS "value"
            FROM "Artist"
        """
    },

    # ============================================================
    # 2. Count customers
    # ============================================================

    {
        "id": 2,
        "question": "How many customers are there?",
        "expected_type": "database",
        "comparison": "scalar",
        "ground_truth_sql": """
            SELECT COUNT(*) AS "value"
            FROM "Customer"
        """
    },

    # ============================================================
    # 3. Count tracks
    # ============================================================

    {
        "id": 3,
        "question": "How many tracks are there?",
        "expected_type": "database",
        "comparison": "scalar",
        "ground_truth_sql": """
            SELECT COUNT(*) AS "value"
            FROM "Track"
        """
    },

    # ============================================================
    # 4. Albums by AC/DC
    # ============================================================

    {
        "id": 4,
        "question": "Which albums belong to AC/DC?",
        "expected_type": "database",
        "comparison": "rows",

        "expected_columns": [
            "AlbumId",
            "Title"
        ],

        "ground_truth_sql": """
            SELECT
                "Album"."AlbumId",
                "Album"."Title"
            FROM "Album"
            JOIN "Artist"
                ON "Album"."ArtistId" = "Artist"."ArtistId"
            WHERE "Artist"."Name" = 'AC/DC'
            ORDER BY "Album"."AlbumId"
        """
    },

    # ============================================================
    # 5. Customers who purchased AC/DC
    # ============================================================

    {
        "id": 5,
        "question": "Which customers purchased tracks by AC/DC?",
        "expected_type": "database",
        "comparison": "rows",

        "expected_columns": [
            "CustomerId",
            "FirstName",
            "LastName"
        ],

        "ground_truth_sql": """
            SELECT DISTINCT
                "Customer"."CustomerId",
                "Customer"."FirstName",
                "Customer"."LastName"
            FROM "Customer"
            JOIN "Invoice"
                ON "Customer"."CustomerId" = "Invoice"."CustomerId"
            JOIN "InvoiceLine"
                ON "Invoice"."InvoiceId" = "InvoiceLine"."InvoiceId"
            JOIN "Track"
                ON "InvoiceLine"."TrackId" = "Track"."TrackId"
            JOIN "Album"
                ON "Track"."AlbumId" = "Album"."AlbumId"
            JOIN "Artist"
                ON "Album"."ArtistId" = "Artist"."ArtistId"
            WHERE "Artist"."Name" = 'AC/DC'
            ORDER BY "Customer"."CustomerId"
        """
    },

    # ============================================================
    # 6. Customers who purchased Metallica
    # ============================================================

    {
        "id": 6,
        "question": "Which customers bought songs from Metallica?",
        "expected_type": "database",
        "comparison": "rows",

        "expected_columns": [
            "CustomerId",
            "FirstName",
            "LastName"
        ],

        "ground_truth_sql": """
            SELECT DISTINCT
                "Customer"."CustomerId",
                "Customer"."FirstName",
                "Customer"."LastName"
            FROM "Customer"
            JOIN "Invoice"
                ON "Customer"."CustomerId" = "Invoice"."CustomerId"
            JOIN "InvoiceLine"
                ON "Invoice"."InvoiceId" = "InvoiceLine"."InvoiceId"
            JOIN "Track"
                ON "InvoiceLine"."TrackId" = "Track"."TrackId"
            JOIN "Album"
                ON "Track"."AlbumId" = "Album"."AlbumId"
            JOIN "Artist"
                ON "Album"."ArtistId" = "Artist"."ArtistId"
            WHERE "Artist"."Name" = 'Metallica'
            ORDER BY "Customer"."CustomerId"
        """
    },

    # ============================================================
    # 7. Top 5 artists
    # ============================================================

    {
        "id": 7,
        "question": "What are the top 5 artists with the most tracks?",
        "expected_type": "database",
        "comparison": "rows",

        "expected_columns": [
            "Name",
            "TrackCount"
        ],

        "ground_truth_sql": """
            SELECT
                "Artist"."Name",
                COUNT("Track"."TrackId") AS "TrackCount"
            FROM "Artist"
            JOIN "Album"
                ON "Album"."ArtistId" = "Artist"."ArtistId"
            JOIN "Track"
                ON "Track"."AlbumId" = "Album"."AlbumId"
            GROUP BY
                "Artist"."ArtistId",
                "Artist"."Name"
            ORDER BY
                "TrackCount" DESC
            LIMIT 5
        """
    },

    # ============================================================
    # 8. Top 5 customers by total spending
    # ============================================================

    {
        "id": 8,
        "question": "What are the top 5 customers by total spending?",
        "expected_type": "database",
        "comparison": "rows_with_numeric_value",

        "expected_columns": [
            "FirstName",
            "LastName"
        ],

        "ground_truth_sql": """
            SELECT
                "Customer"."FirstName",
                "Customer"."LastName",
                SUM("Invoice"."Total") AS "TotalSpending"
            FROM "Customer"
            JOIN "Invoice"
                ON "Customer"."CustomerId" = "Invoice"."CustomerId"
            GROUP BY
                "Customer"."CustomerId",
                "Customer"."FirstName",
                "Customer"."LastName"
            ORDER BY
                "TotalSpending" DESC
            LIMIT 5
        """
    },

    # ============================================================
    # 9. Arabic count artists
    # ============================================================

    {
        "id": 9,
        "question": "كام artist موجود؟",
        "expected_type": "database",
        "comparison": "scalar",

        "ground_truth_sql": """
            SELECT COUNT(*) AS "value"
            FROM "Artist"
        """
    },

    # ============================================================
    # 10. Mixed count customers
    # ============================================================

    {
        "id": 10,
        "question": "كام customer موجود في database؟",
        "expected_type": "database",
        "comparison": "scalar",

        "ground_truth_sql": """
            SELECT COUNT(*) AS "value"
            FROM "Customer"
        """
    },

    # ============================================================
    # 11. Arabic top 5 artists
    # ============================================================

    {
        "id": 11,
        "question": "مين أكتر 5 artists عندهم tracks؟",
        "expected_type": "database",
        "comparison": "rows",

        "expected_columns": [
            "Name",
            "TrackCount"
        ],

        "ground_truth_sql": """
            SELECT
                "Artist"."Name",
                COUNT("Track"."TrackId") AS "TrackCount"
            FROM "Artist"
            JOIN "Album"
                ON "Artist"."ArtistId" = "Album"."ArtistId"
            JOIN "Track"
                ON "Album"."AlbumId" = "Track"."AlbumId"
            GROUP BY
                "Artist"."ArtistId",
                "Artist"."Name"
            ORDER BY
                "TrackCount" DESC
            LIMIT 5
        """
    },

    # ============================================================
    # 12. Greeting
    # ============================================================

    {
        "id": 12,
        "question": "Hello",
        "expected_type": "greeting",
        "comparison": "type_only"
    },

    # ============================================================
    # 13. Unrelated
    # ============================================================

    {
        "id": 13,
        "question": "What is the weather today?",
        "expected_type": "unrelated",
        "comparison": "type_only"
    }
,

    # ============================================================
    # 14. Discovery (what does the database contain?)
    # ============================================================

    {
        "id": 14,
        "question": "What tables are in the database?",
        "expected_type": "discovery",
        "comparison": "type_only"
    },

    # ============================================================
    # 15. Discovery (Arabic)
    # ============================================================

    {
        "id": 15,
        "question": "الـ Customer فيه أعمدة إيه؟",
        "expected_type": "discovery",
        "comparison": "type_only"
    },

    # ============================================================
    # 16. Genuinely ambiguous request -> one clarification question
    # ============================================================

    {
        "id": 16,
        "question": "Show me the data.",
        "expected_type": "clarification",
        "comparison": "type_only"
    },

    # ============================================================
    # 17. Short request with a sensible default -> answered directly
    #     (AMBIGUOUS was narrowed in Phase 3)
    # ============================================================

    {
        "id": 17,
        "question": "Show me customers.",
        "expected_type": "database",
        "comparison": "type_only"
    }
]
