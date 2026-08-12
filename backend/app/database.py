import os

import psycopg2
from dotenv import load_dotenv


# Load environment variables from backend/.env
load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "ai_travel_planner"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id SERIAL PRIMARY KEY,
            destination VARCHAR(255) NOT NULL,
            country VARCHAR(255) DEFAULT '',
            days INTEGER NOT NULL,
            travelers INTEGER NOT NULL,
            budget NUMERIC NOT NULL,
            travel_style VARCHAR(100) DEFAULT 'balanced',
            interests TEXT,
            plan JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()

    cursor.close()
    connection.close()