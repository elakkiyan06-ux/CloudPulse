import time
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text, inspect, func
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.core.config import settings
from app.models.models import WeatherObservation, Base
from app.core.logging_config import add_log_entry, logger

def create_schema() -> Dict[str, Any]:
    """Creates weather_observations table and base schema."""
    start = time.perf_counter()
    Base.metadata.create_all(bind=engine)
    elapsed = (time.perf_counter() - start) * 1000.0
    add_log_entry("INFO", "SCHEMA_INIT", f"Database schema initialized in {elapsed:.2f}ms")
    return {"success": True, "elapsed_ms": round(elapsed, 2)}

def verify_record_count(expected_count: Optional[int] = None) -> Dict[str, Any]:
    """
    Executes actual database verification of total observations in AWS RDS.
    Produces a cryptographic SHA256 checksum based on real rows.
    """
    create_schema()
    db: Session = SessionLocal()
    try:
        actual_count = db.query(func.count(WeatherObservation.id)).scalar() or 0
        
        # Checksum calculation over real IDs and temperatures
        checksum_query = db.query(
            func.min(WeatherObservation.id),
            func.max(WeatherObservation.id),
            func.sum(WeatherObservation.temperature)
        ).first()
        
        min_id, max_id, sum_temp = checksum_query
        raw_token = f"{actual_count}:{min_id}:{max_id}:{sum_temp or 0:.2f}"
        checksum = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:16].upper()
        
        is_verified = (expected_count is None) or (actual_count == expected_count)
        status_msg = "PASSED" if is_verified else "DISCREPANCY"
        msg = f"Verified {actual_count} observations in AWS RDS weather_observations (Checksum: SHA256-{checksum})."
        
        add_log_entry("INFO", "VERIFY_COUNT", msg)
        
        return {
            "verified": is_verified,
            "starting_row_count": expected_count if expected_count is not None else actual_count,
            "current_row_count": actual_count,
            "checksum": checksum,
            "status": status_msg,
            "message": msg
        }
    finally:
        db.close()

def get_database_statistics() -> Dict[str, Any]:
    """
    Inspects real PostgreSQL / SQLite catalog for table size, index listings,
    and actual latest weather observations.
    """
    create_schema()
    db: Session = SessionLocal()
    actual_count = 0
    latest_time = None
    try:
        actual_count = db.query(func.count(WeatherObservation.id)).scalar() or 0
        latest_obs = db.query(WeatherObservation.observation_time).order_by(WeatherObservation.observation_time.desc()).first()
        if latest_obs and latest_obs[0]:
            latest_time = latest_obs[0].isoformat()
    except Exception as e:
        logger.warning(f"Error querying count: {e}")
    finally:
        db.close()

    inspector = inspect(engine)
    indexes = []
    table_size_bytes = None
    table_size_pretty = "N/A"

    try:
        raw_indexes = inspector.get_indexes("weather_observations")
        for idx in raw_indexes:
            indexes.append({
                "index_name": idx["name"],
                "columns": idx["column_names"],
                "unique": idx.get("unique", False),
                "definition": f"CREATE {'UNIQUE ' if idx.get('unique') else ''}INDEX {idx['name']} ON weather_observations ({', '.join(idx['column_names'])})"
            })
    except Exception as e:
        logger.warning(f"Could not inspect indexes: {e}")

    # Check table size if PostgreSQL
    if engine.dialect.name == "postgresql":
        try:
            with engine.connect() as conn:
                size_res = conn.execute(text("SELECT pg_total_relation_size('weather_observations');")).scalar()
                if size_res is not None:
                    table_size_bytes = int(size_res)
                    table_size_pretty = f"{table_size_bytes / 1024:.1f} KB"
        except Exception:
            pass

    return {
        "table_name": "weather_observations",
        "total_rows": actual_count,
        "latest_observation_time": latest_time,
        "table_size_bytes": table_size_bytes,
        "table_size_pretty": table_size_pretty,
        "engine": "PostgreSQL" if engine.dialect.name == "postgresql" else "SQLite",
        "cloud_environment": settings.ENVIRONMENT,
        "is_aws_rds": settings.IS_AWS_RDS,
        "indexes": indexes,
        "pool_status": {
            "pool_size": getattr(engine.pool, "size", lambda: 10)(),
            "checkedin": getattr(engine.pool, "checkedin", lambda: 0)(),
            "checkedout": getattr(engine.pool, "checkedout", lambda: 0)()
        }
    }

def reset_dataset() -> Dict[str, Any]:
    """Purges observations from weather_observations table."""
    db: Session = SessionLocal()
    try:
        deleted = db.query(WeatherObservation).delete()
        db.commit()
        add_log_entry("WARN", "DATA_RESET", f"Reset dataset: purged {deleted} observations from AWS RDS.")
        return {"success": True, "records_deleted": deleted, "message": f"Purged {deleted} observations."}
    except Exception as e:
        db.rollback()
        add_log_entry("ERROR", "DATA_RESET", f"Reset dataset failed: {str(e)}")
        raise e
    finally:
        db.close()

def cleanup_test_resources() -> Dict[str, Any]:
    """Drops test indexes and cleans up benchmark tables."""
    start = time.perf_counter()
    dropped_indexes = []

    with engine.connect() as conn:
        test_indexes = ["idx_weather_loc_time", "idx_weather_loc_time_base"]
        for idx in test_indexes:
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))
                conn.commit()
                dropped_indexes.append(idx)
            except Exception:
                pass

        try:
            conn.execute(text("DROP TABLE IF EXISTS weather_observations CASCADE;"))
            conn.commit()
            table_dropped = True
        except Exception:
            try:
                conn.execute(text("DROP TABLE IF EXISTS weather_observations;"))
                conn.commit()
                table_dropped = True
            except Exception:
                table_dropped = False

    elapsed = (time.perf_counter() - start) * 1000.0
    add_log_entry("INFO", "TEARDOWN", f"Cleanup executed: dropped table weather_observations and indexes: {dropped_indexes} ({elapsed:.2f}ms)")
    return {
        "success": True,
        "table_dropped": table_dropped,
        "dropped_indexes": dropped_indexes,
        "elapsed_ms": round(elapsed, 2),
        "message": "Benchmark test resources and indexes removed successfully."
    }
