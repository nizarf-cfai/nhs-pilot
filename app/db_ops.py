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
