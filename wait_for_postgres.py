import time
import psycopg2
from psycopg2 import OperationalError
import os

DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', 5432)
DB_NAME = os.getenv('DB_NAME', 'mydb')
DB_USER = os.getenv('DB_USER', 'user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

def wait_for_db():
    while True:
        try:
            print("Waiting for PostgreSQL to be ready...")
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            conn.close()
            print("PostgreSQL is ready!")
            break
        except OperationalError:
            print("PostgreSQL is not ready. Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    wait_for_db()
