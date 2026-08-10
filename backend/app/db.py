import os
from pathlib import Path

import duckdb
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_duckdb():
    Path(settings.duckdb_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(settings.duckdb_path)
