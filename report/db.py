"""Database connection. The connection string comes from the DATABASE_URL
environment variable (or a .env file), so no password is ever written in code.

Example: mysql+pymysql://report_user:secret@localhost:3306/weekly_sales
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


def get_engine(url: str | None = None):
    url = url or os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in your MySQL details."
        )
    return create_engine(url, pool_pre_ping=True)
