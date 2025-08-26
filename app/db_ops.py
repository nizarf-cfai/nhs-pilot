from google.cloud.sql.connector import Connector
import pg8000  # PostgreSQL driver
import config


# Cloud SQL connector
connector = Connector()


def get_pg_connection():
    return connector.connect(
        config.DB_CONNECTION_NAME,
        "pg8000",
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME
    )


def get_dummy_patients_pool():
    """
    Fetch all rows from dummy_patients table and return as a list of dictionaries.
    """
    query = "SELECT * FROM dummy_patients"
    results = []

    conn = get_pg_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]  # column names
            rows = cursor.fetchall()
            for row in rows:
                results.append(dict(zip(columns, row)))
    finally:
        conn.close()

    return results