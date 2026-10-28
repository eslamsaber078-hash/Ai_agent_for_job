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
        ("profile_id", "INTEGER NOT NULL DEFAULT 1"),
    ],
    "automation_runs": [("profile_id", "INTEGER NOT NULL DEFAULT 1")],
    "search_preferences": [
        ("max_age_days", "INTEGER DEFAULT 30"),
        ("extra_terms", "TEXT DEFAULT '[]'"),
    ],
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
        if "jobs" in existing_tables:
            _upgrade_job_ownership(conn)
        ensure_indexes(conn, existing_tables)


def _upgrade_job_ownership(conn) -> None:
    constraints = inspect(conn).get_unique_constraints("jobs")
    if not any(set(c["column_names"]) == {"source", "external_id"} for c in constraints):
        return
    if conn.dialect.name != "sqlite":
        conn.execute(text("ALTER TABLE jobs DROP CONSTRAINT uq_job_source_external"))
        conn.execute(text("ALTER TABLE jobs ADD CONSTRAINT uq_job_profile_source_external "
                          "UNIQUE (profile_id, source, external_id)"))
        return
    from sqlalchemy.schema import CreateTable
    from .models import Job

    # Preserve ids so existing saved jobs, applications and documents stay attached.
    ddl = str(CreateTable(Job.__table__).compile(dialect=conn.dialect))
    conn.exec_driver_sql(ddl.replace("CREATE TABLE jobs", "CREATE TABLE jobs_account_upgrade", 1))
    columns = ", ".join(f'"{column.name}"' for column in Job.__table__.columns)
    count = conn.exec_driver_sql("SELECT COUNT(*) FROM jobs").scalar_one()
    conn.exec_driver_sql(f"INSERT INTO jobs_account_upgrade ({columns}) SELECT {columns} FROM jobs")
    if conn.exec_driver_sql("SELECT COUNT(*) FROM jobs_account_upgrade").scalar_one() != count:
        raise RuntimeError("Job ownership migration did not preserve all rows")
    conn.exec_driver_sql("DROP TABLE jobs")
    conn.exec_driver_sql("ALTER TABLE jobs_account_upgrade RENAME TO jobs")


# Every list and dashboard query filters jobs by is_active + posted_date, and
# every import looks rows up by (source, external_id); on a grown table those
# are full scans without an index. create_all() never adds indexes to an
# existing table, so they are created here, idempotently.
INDEXES = [
    ("jobs", "CREATE INDEX IF NOT EXISTS ix_jobs_active_posted ON jobs (is_active, posted_date)"),
    ("jobs", "CREATE INDEX IF NOT EXISTS ix_jobs_source ON jobs (source)"),
    ("jobs", "CREATE INDEX IF NOT EXISTS ix_jobs_source_ext ON jobs (source, external_id)"),
    ("jobs", "CREATE INDEX IF NOT EXISTS ix_jobs_profile_id ON jobs (profile_id)"),
    ("automation_runs", "CREATE INDEX IF NOT EXISTS ix_automation_runs_profile_id ON automation_runs (profile_id)"),
]


def ensure_indexes(conn, existing_tables: set[str]) -> None:
    for table, ddl in INDEXES:
        if table in existing_tables:
            conn.execute(text(ddl))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
