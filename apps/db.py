import mysql.connector
from flask import current_app

class DBCursor:
    """Wrapper around a mysql.connector cursor that supports the context manager protocol."""
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def close(self):
        return self._cursor.close()


class DBConnection:
    """Wrapper around a mysql.connector connection with context manager support."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        return DBCursor(self._conn.cursor(*args, **kwargs))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
        finally:
            try:
                self._conn.close()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        return self._conn.close()


def get_db_connection(db_name=None):
    """
    Get a connection to a specific MySQL database.
    - If db_name is provided, it connects to that database.
    - If db_name is None, it defaults to the main MYSQL_DATABASE in config.
    """
    # Logic to select the database name
    target_db = db_name if db_name else current_app.config['MYSQL_DATABASE']

    connection = mysql.connector.connect(
        host=current_app.config['MYSQL_HOST'],
        user=current_app.config['MYSQL_USER'],
        password=current_app.config['MYSQL_PASSWORD'],
        database=target_db
    )
    return DBConnection(connection)