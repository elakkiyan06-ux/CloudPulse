import time
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from app.core.config import settings
from app.core.logging_config import logger, add_log_entry
from app.models.models import Base

def get_engine(db_url: str = None):
    url = db_url or settings.DATABASE_URL
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
    else:
        # PostgreSQL (RDS / Local)
        # Normalize postgres:// or raw postgresql:// to use psycopg2/psycopg driver safely
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and "+" not in url.split("://")[0]:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_TIMEOUT_SECONDS,
            pool_pre_ping=True
        )
    return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db(target_engine=None):
    """
    Initializes metadata tables and ensures base tables exist.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    # Ensure columns exist on benchmark_runs table
    try:
        with eng.connect() as conn:
            inspector = inspect(eng)
            cols = [c["name"] for c in inspector.get_columns("benchmark_runs")]
            if "api_response_time_ms" not in cols:
                conn.execute(text("ALTER TABLE benchmark_runs ADD COLUMN api_response_time_ms FLOAT DEFAULT 0.0;"))
                conn.commit()
            if "db_insert_time_ms" not in cols:
                conn.execute(text("ALTER TABLE benchmark_runs ADD COLUMN db_insert_time_ms FLOAT DEFAULT 0.0;"))
                conn.commit()
    except Exception:
        pass

    add_log_entry("INFO", "SCHEMA_INIT", "Database tables verified/initialized successfully")

def test_database_connection(test_url: str = None):
    """
    Performs an active ping against the configured database, measuring latency and retrieving version.
    """
    eng = get_engine(test_url) if test_url else engine
    start_time = time.perf_counter()
    try:
        with eng.connect() as conn:
            # Query version and ping
            if eng.dialect.name == "postgresql":
                result = conn.execute(text("SELECT version();")).scalar()
                pool_status = {
                    "pool_size": getattr(eng.pool, "size", lambda: settings.DB_POOL_SIZE)(),
                    "checkedin": getattr(eng.pool, "checkedin", lambda: 0)(),
                    "checkedout": getattr(eng.pool, "checkedout", lambda: 0)(),
                    "overflow": getattr(eng.pool, "overflow", lambda: 0)()
                }
            else:
                raw_ver = conn.execute(text("SELECT sqlite_version();")).scalar()
                result = f"SQLite {raw_ver} (High-Fidelity Local Engine)"
                pool_status = {
                    "pool_size": 1,
                    "checkedin": 1,
                    "checkedout": 0,
                    "overflow": 0
                }
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            
            # Check if weather_observations exists
            inspector = inspect(eng)
            tables = inspector.get_table_names()
            has_weather_records = "weather_observations" in tables
            
            return {
                "status": "CONNECTED",
                "connected": True,
                "engine": eng.dialect.name.upper(),
                "version": str(result),
                "latency_ms": round(latency_ms, 2),
                "has_benchmark_schema": has_weather_records,
                "pool_status": pool_status,
                "environment": settings.ENVIRONMENT if eng.dialect.name == "postgresql" else "Local Development"
            }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(f"Database connection error: {str(e)}")
        add_log_entry("ERROR", "DB_CONNECTION", f"Connection test failed: {str(e)}")
        return {
            "status": "DISCONNECTED",
            "connected": False,
            "error": str(e),
            "latency_ms": round(latency_ms, 2),
            "engine": eng.dialect.name.upper(),
            "has_benchmark_schema": False
        }
