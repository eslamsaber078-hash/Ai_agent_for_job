import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

if _IS_SQLITE:
    # The API runs sync endpoints on a 40-thread pool, so the connection pool has to
    # cover all of them; anything smaller made simultaneous visitors queue for a
    # connection while the database itself was idle.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 15},
        pool_size=20, max_overflow=20, pool_timeout=10,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        # WAL lets readers keep working while an import writes; NORMAL drops the
        # per-commit fsync of the rollback journal, which is what a read-mostly app
        # pays for and never needs. busy_timeout replaces an instant "database is
        # locked" error with a short wait.
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA cache_size=-8192")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=268435456")
        finally:
            cursor.close()
else:
    # Neon drops idle connections; without a ping the first request after a quiet
    # spell fails on a dead socket. The TCP probes do the same job one layer lower:
    # a NAT or load balancer between the host and the database forgets a quiet
    # socket before either end does, which is what a "lost connection" mid-session
    # actually is.
    engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20,
                           pool_timeout=20, pool_pre_ping=True, pool_recycle=300,
                           connect_args={
                               "connect_timeout": 10,
                               "keepalives": 1,
                               "keepalives_idle": 30,
                               "keepalives_interval": 10,
                               "keepalives_count": 5,
                           })

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def warm_pool(bind=None) -> None:
    """Open every pool slot once, at startup.

    Connections are otherwise created lazily, inside whatever request first needs
    one. A traffic spike on a freshly started process therefore creates them all at
    the same instant, and the SQLite WAL lock serializes those creations into stalls
    long enough to trip pool_timeout. Paying that cost once during boot keeps the
    first burst as fast as every later one.

    A hosting database that is still waking up must not turn a nicety into a failed
    boot: whatever could not be opened is simply opened on first use, as before.
    """
    bind = bind if bind is not None else engine
    held = []
    try:
        for _ in range(bind.pool.size()):
            conn = bind.connect()
            conn.exec_driver_sql("SELECT 1")
            held.append(conn)
    except Exception:  # noqa: BLE001
        logging.getLogger("jobhunter").warning("Pool warm-up stopped early", exc_info=True)
    finally:
        for conn in held:
            conn.close()


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
    # Every list query reads one owner's live postings newest-first; the single-column
    # indexes above made the database walk both and intersect them.
    ("jobs", "CREATE INDEX IF NOT EXISTS ix_jobs_owner_active_posted "
             "ON jobs (profile_id, is_active, posted_date)"),
    ("automation_runs", "CREATE INDEX IF NOT EXISTS ix_automation_runs_profile_id ON automation_runs (profile_id)"),
    ("auth_sessions", "CREATE INDEX IF NOT EXISTS ix_auth_sessions_account ON auth_sessions (account_id)"),
    # Every job card, desk row and PDF read asks "which documents belong to this posting
    # / this application". A foreign key alone does not give Postgres an index to use,
    # so those lookups were sequential scans over the whole materials table.
    ("generated_materials", "CREATE INDEX IF NOT EXISTS ix_materials_job "
                             "ON generated_materials (job_id, kind)"),
    ("generated_materials", "CREATE INDEX IF NOT EXISTS ix_materials_application "
                             "ON generated_materials (application_id)"),
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
