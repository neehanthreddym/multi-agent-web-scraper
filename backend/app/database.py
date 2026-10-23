"""Database connections; credentials never need string interpolation into URLs."""

import os

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker


database_url = URL.create(
    "postgresql+psycopg",
    username="catalog",
    password=os.environ.get("POSTGRES_PASSWORD", "catalog-local-only"),
    host="postgres",
    port=5432,
    database="catalog",
)
engine = create_engine(
    database_url, pool_pre_ping=True, pool_size=3, max_overflow=2,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
