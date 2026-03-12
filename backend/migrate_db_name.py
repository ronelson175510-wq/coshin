import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

OLD_DB = os.getenv('OLD_DB_NAME', 'zimcom')
NEW_DB = os.getenv('NEW_DB_NAME', 'coshin')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
}


def get_conn(database=None):
    config = dict(DB_CONFIG)
    if database:
        config['database'] = database
    return mysql.connector.connect(**config)


def database_exists(cursor, db_name):
    cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
    return cursor.fetchone() is not None


def list_tables(cursor, db_name):
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
        ORDER BY table_name
        """,
        (db_name,)
    )
    return [row[0] for row in cursor.fetchall()]


def main():
    print(f"Starting DB migration: {OLD_DB} -> {NEW_DB}")

    conn = get_conn()
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        if not database_exists(cursor, OLD_DB):
            print(f"Source database '{OLD_DB}' does not exist. Nothing to migrate.")
            return

        if not database_exists(cursor, NEW_DB):
            print(f"Creating target database '{NEW_DB}'...")
            cursor.execute(
                f"CREATE DATABASE `{NEW_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

        old_tables = list_tables(cursor, OLD_DB)
        new_tables = list_tables(cursor, NEW_DB)

        if not old_tables:
            print(f"Source database '{OLD_DB}' has no tables. Nothing to migrate.")
            return

        if new_tables:
            print(f"Target database '{NEW_DB}' already has tables: {', '.join(new_tables)}")
            print("Skipping migration to avoid overwriting existing data.")
            return

        print(f"Migrating {len(old_tables)} tables...")
        for table in old_tables:
            cursor.execute(f"RENAME TABLE `{OLD_DB}`.`{table}` TO `{NEW_DB}`.`{table}`")
            print(f"  Moved table: {table}")

        print("Migration complete.")
        print("Update backend/.env -> DB_NAME=coshin and restart the backend.")
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
