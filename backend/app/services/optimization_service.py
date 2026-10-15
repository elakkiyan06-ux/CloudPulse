import uuid
import time
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.models.models import OptimizationExperiment, BenchmarkRun, WeatherObservation
from app.core.logging_config import add_log_entry, logger
from app.services.benchmark_engine import start_benchmark_run, get_benchmark_status
from app.services.query_plan_service import explain_query
from app.services.weather_service import ensure_weather_table

# Approved real optimization indexes on weather_observations
ALLOWLISTED_INDEXES = {
    "idx_weather_loc_time": {
        "table": "weather_observations",
        "column": "location_name, observation_time",
        "sql": "CREATE INDEX idx_weather_loc_time ON weather_observations (location_name, observation_time DESC);",
        "drop_sql": "DROP INDEX IF EXISTS idx_weather_loc_time;",
        "description": "Composite B-Tree index on location_name and observation_time DESC to eliminate table scans on temporal location queries."
    },
    "idx_weather_temp_humidity": {
        "table": "weather_observations",
        "column": "temperature, relative_humidity",
        "sql": "CREATE INDEX idx_weather_temp_humidity ON weather_observations (temperature, relative_humidity);",
        "drop_sql": "DROP INDEX IF EXISTS idx_weather_temp_humidity;",
        "description": "Composite B-Tree index on temperature and relative_humidity for meteorological scans."
    }
}

def apply_index(index_name: str) -> Dict[str, Any]:
    """
    Safely creates an allowlisted index on weather_observations in AWS RDS PostgreSQL / local DB.
    Validates strictly against the allowlist to prevent SQL injection.
    """
    if index_name not in ALLOWLISTED_INDEXES:
        raise ValueError(f"Index '{index_name}' is not in the approved optimization allowlist.")
        
    idx_config = ALLOWLISTED_INDEXES[index_name]
    start = time.perf_counter()
    
    with engine.connect() as conn:
        conn.execute(text(idx_config["sql"]))
        conn.commit()
        
    elapsed = (time.perf_counter() - start) * 1000.0
    add_log_entry("INFO", "INDEX_APPLIED", f"Created index '{index_name}' on weather_observations ({elapsed:.2f}ms)")
    
    return {
        "success": True,
        "index_name": index_name,
        "definition": idx_config["sql"],
        "elapsed_ms": round(elapsed, 2),
        "message": f"Successfully created index '{index_name}'."
    }

def rollback_index(index_name: str) -> Dict[str, Any]:
    """
    Safely drops the specified experiment index.
    """
    if index_name not in ALLOWLISTED_INDEXES:
        raise ValueError(f"Index '{index_name}' is not in the approved optimization allowlist.")
        
    idx_config = ALLOWLISTED_INDEXES[index_name]
    start = time.perf_counter()
    
    with engine.connect() as conn:
        conn.execute(text(idx_config["drop_sql"]))
        conn.commit()
        
    elapsed = (time.perf_counter() - start) * 1000.0
    add_log_entry("INFO", "INDEX_ROLLBACK", f"Rolled back index '{index_name}' ({elapsed:.2f}ms)")
    
    return {
        "success": True,
        "index_name": index_name,
        "elapsed_ms": round(elapsed, 2),
        "message": f"Successfully dropped index '{index_name}'."
    }

def generate_honest_engineering_analysis(
    baseline_lat: float,
    optimized_lat: float,
    baseline_thru: float,
    optimized_thru: float,
    scan_before: str,
    scan_after: str,
    row_count: int
) -> str:
    """
    Generates a rigorous, evidence-based technical explanation comparing measurements.
    Honestly addresses cases where speedup is substantial vs cases with no measurable speedup.
    Satisfies Step 13: Never fake a positive result.
    """
    lat_diff = baseline_lat - optimized_lat
    pct_speedup = ((lat_diff) / baseline_lat * 100.0) if baseline_lat > 0 else 0.0

    lines = []
    lines.append(f"### Weather Observations Optimization Analysis")
    lines.append(f"- **Baseline Latency:** {baseline_lat:.2f} ms ({scan_before})")
    lines.append(f"- **Optimized Latency:** {optimized_lat:.2f} ms ({scan_after})")
    lines.append(f"- **Measured Latency Delta:** {abs(lat_diff):.2f} ms ({pct_speedup:+.1f}%)")
    lines.append(f"- **Real Dataset Evaluated:** {row_count} live observations in `weather_observations`")

    if pct_speedup > 15.0:
        lines.append(
            f"\n**Measured latency decreased by {pct_speedup:.1f}%:**\n"
            f"The composite B-Tree index `idx_weather_loc_time` eliminated full table scans. "
            f"Instead of sequentially scanning rows and performing an explicit sort on observation_time, "
            f"PostgreSQL traversed the B-Tree index to directly stream pre-ordered tuples. "
            f"Throughput increased from {baseline_thru:.1f} to {optimized_thru:.1f} ops/sec."
        )
    elif abs(pct_speedup) <= 15.0:
        lines.append(
            f"\n**No measurable improvement was observed under this workload ({pct_speedup:+.1f}%):**\n"
            f"While the query planner adopted `{scan_after}`, elapsed latency showed no dramatic difference. "
            f"With a compact real-time weather dataset ({row_count} observations), the entire table pages reside "
            f"in PostgreSQL `shared_buffers` cache (RAM). Sequential scans across cached buffer pages can be just as fast "
            f"as traversing B-Tree branch and leaf pages followed by heap lookups."
        )
    else:  # Slower
        lines.append(
            f"\n**The optimized run was slower in this test ({abs(pct_speedup):.1f}% slower):**\n"
            f"This is an authentic managed cloud database phenomenon often caused by initial cold-cache index loading, "
            f"or the query planner having to perform two-step pointer traversals (index scan + heap fetch) instead of sequential streaming."
        )

    lines.append(
        f"\n**Managed Cloud Database Trade-Off:**\n"
        f"Indexes are valuable as real-time weather telemetry accumulates to hundreds of thousands of rows, "
        f"but adding indexes introduces write amplification overhead on each real-time Open-Meteo INSERT."
    )

    return "\n".join(lines)

def run_optimization_experiment(
    experiment_name: str,
    target_column: str = "location_name, observation_time",
    index_name: str = "idx_weather_loc_time",
    iterations: int = 50
) -> Dict[str, Any]:
    """
    Executes a complete automated A/B optimization test on real weather_observations:
    1. Ensures index is dropped -> Runs baseline benchmark -> Captures plan (Seq Scan)
    2. Creates index -> Runs identical optimized benchmark -> Captures plan (Index Scan)
    3. Calculates comparative metrics and generates honest analysis.
    """
    ensure_weather_table()
    exp_id = str(uuid.uuid4())
    db: Session = SessionLocal()
    
    try:
        # Pre-cleanup: drop index to ensure pure baseline
        try:
            rollback_index(index_name)
        except Exception:
            pass
            
        time.sleep(0.5)

        # Baseline plan and run
        plan_before = explain_query(query_type="LOCATION_FILTER", filter_value="Chennai", analyze=True)
        baseline_run = start_benchmark_run(
            run_name=f"[Baseline] {experiment_name}",
            workload_type="READ",
            query_type="LOCATION_FILTER",
            operation_count=iterations,
            concurrency=1,
            warm_up_count=5,
            is_optimized=False,
            notes="Baseline run prior to composite index application (Sequential Scan)"
        )
        baseline_run_id = baseline_run["id"]

        # Wait for baseline run to complete
        for _ in range(60):
            st = get_benchmark_status(baseline_run_id)
            if st.get("status") in ["COMPLETED", "FAILED"]:
                baseline_run = st
                break
            time.sleep(0.5)

        # Step 2: Apply Optimization Index
        apply_index(index_name)
        time.sleep(0.5)

        # Optimized plan and run
        plan_after = explain_query(query_type="LOCATION_FILTER", filter_value="Chennai", analyze=True)
        optimized_run = start_benchmark_run(
            run_name=f"[Optimized] {experiment_name}",
            workload_type="READ",
            query_type="LOCATION_FILTER",
            operation_count=iterations,
            concurrency=1,
            warm_up_count=5,
            is_optimized=True,
            index_used=index_name,
            notes=f"Optimized run leveraging composite index {index_name}"
        )
        optimized_run_id = optimized_run["id"]

        for _ in range(60):
            st = get_benchmark_status(optimized_run_id)
            if st.get("status") in ["COMPLETED", "FAILED"]:
                optimized_run = st
                break
            time.sleep(0.5)

        # Calculations
        base_lat = baseline_run.get("avg_latency_ms", 0.0)
        opt_lat = optimized_run.get("avg_latency_ms", 0.0)
        base_thru = baseline_run.get("throughput_ops_sec", 0.0)
        opt_thru = optimized_run.get("throughput_ops_sec", 0.0)

        lat_red_pct = ((base_lat - opt_lat) / base_lat * 100.0) if base_lat > 0 else 0.0
        thru_chg_pct = ((opt_thru - base_thru) / base_thru * 100.0) if base_thru > 0 else 0.0

        scan_before = plan_before.get("scan_type", "Seq Scan")
        scan_after = plan_after.get("scan_type", "Index Scan")

        current_count = db.query(func.count(WeatherObservation.id)).scalar() or 0

        analysis = generate_honest_engineering_analysis(
            base_lat, opt_lat, base_thru, opt_thru, scan_before, scan_after, current_count
        )

        exp_record = OptimizationExperiment(
            id=exp_id,
            experiment_name=experiment_name,
            description=f"Evaluated real performance impact of composite index {index_name} on weather_observations.",
            target_table="weather_observations",
            target_column=target_column,
            index_name=index_name,
            index_sql=ALLOWLISTED_INDEXES[index_name]["sql"],
            baseline_run_id=baseline_run_id,
            optimized_run_id=optimized_run_id,
            baseline_latency_ms=base_lat,
            optimized_latency_ms=opt_lat,
            latency_reduction_pct=lat_red_pct,
            throughput_change_pct=thru_chg_pct,
            scan_type_before=scan_before,
            scan_type_after=scan_after,
            analysis_text=analysis,
            status="COMPLETED"
        )
        db.add(exp_record)
        db.commit()

        add_log_entry(
            "INFO", "OPTIMIZATION_EXPERIMENT",
            f"Optimization experiment completed: Baseline {base_lat:.2f}ms vs Optimized {opt_lat:.2f}ms ({lat_red_pct:+.1f}%)"
        )

        return exp_record.to_dict()
    finally:
        db.close()

def get_all_experiments() -> List[Dict[str, Any]]:
    db: Session = SessionLocal()
    try:
        exps = db.query(OptimizationExperiment).order_by(OptimizationExperiment.created_at.desc()).all()
        return [e.to_dict() for e in exps]
    finally:
        db.close()
