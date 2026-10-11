from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# create_all() never adds a column to a table that already exists, so columns
# introduced after the first run are patched in here.
ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "generated_materials": [("template_based", "BOOLEAN DEFAULT 1")],
    "jobs": [
        ("expiry_date", "DATETIME"),
        ("is_active", "BOOLEAN DEFAULT 1"),
    ],
    "search_preferences": [("max_age_days", "INTEGER DEFAULT 30")],
}


def ensure_schema_upgrades(bind=None) -> None:
    bind = bind if bind is not None else engine
    with bind.begin() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())
        for table, columns in ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    have.add(name)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
