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
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]  # column names
        rows = cursor.fetchall()

        for row in rows:
            results.append(dict(zip(columns, row)))

        cursor.close()
    finally:
        conn.close()

    return results

def insert_data(table: str, data: dict):
    """
    Insert a single row into PostgreSQL using an existing Cloud SQL pg8000 connection.

    Args:
        conn: pg8000 connection from get_pg_connection()
        table (str): Table name
        data (dict): Column-value pairs to insert
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            columns = list(data.keys())
            values = list(data.values())

            placeholders = ", ".join(["%s"] * len(columns))
            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({placeholders})
            """

            cur.execute(query, values)
        conn.commit()
        print("✅ Insert successful!")

    except Exception as e:
        conn.rollback()
        print("❌ Error inserting data:", e)