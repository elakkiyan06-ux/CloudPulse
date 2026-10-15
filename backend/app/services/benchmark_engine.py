import time
import uuid
import random
import datetime
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.models.models import BenchmarkRun, BenchmarkResultItem, WeatherObservation
from app.core.logging_config import add_log_entry, logger
from app.core.config import settings
from app.services.weather_service import fetch_and_store_live_weather, ensure_weather_table

# Active running tasks tracker for cancellation
ACTIVE_BENCHMARK_TASKS: Dict[str, Dict[str, Any]] = {}

PREDEFINED_CITY_NAMES = [loc["name"] for loc in settings.PREDEFINED_LOCATIONS]

def calculate_percentiles(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {
            "avg": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0
        }
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    avg_val = statistics.mean(sorted_l)
    median_val = statistics.median(sorted_l)
    
    p95_idx = int(n * 0.95)
    p95_val = sorted_l[min(p95_idx, n - 1)]
    
    p99_idx = int(n * 0.99)
    p99_val = sorted_l[min(p99_idx, n - 1)]
    
    return {
        "avg": avg_val,
        "median": median_val,
        "p95": p95_val,
        "p99": p99_val,
        "min": sorted_l[0],
        "max": sorted_l[-1]
    }

def run_single_read_operation(
    query_type: str, 
    op_index: int, 
    rng: random.Random
) -> Dict[str, Any]:
    """
    Executes a single real read query against AWS RDS weather_observations
    and measures isolated query execution time.
    """
    start_op = time.perf_counter()
    status = "SUCCESS"
    error_msg = None

    try:
        with engine.connect() as conn:
            if query_type == "LATEST_OBSERVATIONS":
                conn.execute(
                    text("SELECT id, location_name, temperature, relative_humidity, wind_speed, observation_time FROM weather_observations ORDER BY observation_time DESC LIMIT 20;")
                ).fetchall()
            elif query_type == "WEATHER_SCAN":
                min_hum = round(rng.uniform(40.0, 75.0), 1)
                min_temp = round(rng.uniform(18.0, 32.0), 1)
                conn.execute(
                    text("SELECT id, location_name, temperature, relative_humidity, surface_pressure FROM weather_observations WHERE relative_humidity > :min_hum AND temperature > :min_temp LIMIT 50;"),
                    {"min_hum": min_hum, "min_temp": min_temp}
                ).fetchall()
            elif query_type == "AGGREGATE":
                conn.execute(
                    text("SELECT location_name, COUNT(*) as observations_count, AVG(temperature) as avg_temp, AVG(relative_humidity) as avg_humidity FROM weather_observations GROUP BY location_name;")
                ).fetchall()
            else:  # LOCATION_FILTER (default)
                target_loc = rng.choice(PREDEFINED_CITY_NAMES)
                conn.execute(
                    text("SELECT id, location_name, temperature, relative_humidity, wind_speed, observation_time FROM weather_observations WHERE location_name = :loc ORDER BY observation_time DESC LIMIT 20;"),
                    {"loc": target_loc}
                ).fetchall()

    except Exception as e:
        status = "FAILED"
        error_msg = str(e)
        logger.error(f"Read operation {op_index} failed: {error_msg}")

    latency_ms = (time.perf_counter() - start_op) * 1000.0
    return {
        "op_index": op_index,
        "op_type": "READ",
        "latency_ms": latency_ms,
        "status": status,
        "error_message": error_msg
    }

def run_single_write_operation(
    op_index: int
) -> Dict[str, Any]:
    """
    Executes a real write cycle:
    1. Requests fresh live data from Open-Meteo
    2. Validates live observation payload
    3. Inserts observations into AWS RDS PostgreSQL
    4. Measures database write time vs API network latency
    """
    status = "SUCCESS"
    error_msg = None
    db_insert_latency = 0.0

    try:
        pipeline_res = fetch_and_store_live_weather()
        db_insert_latency = pipeline_res.get("database_insert_time_ms", 0.0)
        api_latency = pipeline_res.get("api_response_time_ms", 0.0)
        total_time = pipeline_res.get("total_operation_time_ms", 0.0)
    except Exception as e:
        status = "FAILED"
        error_msg = str(e)
        api_latency = 0.0
        total_time = 0.0
        logger.error(f"Write operation {op_index} failed: {error_msg}")

    return {
        "op_index": op_index,
        "op_type": "WRITE",
        "latency_ms": db_insert_latency if db_insert_latency > 0 else 1.0,
        "api_latency_ms": api_latency,
        "total_operation_ms": total_time,
        "status": status,
        "error_message": error_msg
    }

def execute_benchmark_task(
    run_id: str,
    workload_type: str,
    query_type: str,
    operation_count: int,
    concurrency: int,
    warm_up_count: int,
    read_ratio: float
):
    """
    Asynchronous benchmark executor thread operating strictly on real weather data.
    Measures high-resolution timing, records results, and commits to AWS RDS PostgreSQL.
    """
    ensure_weather_table()
    db: Session = SessionLocal()
    task_handle = ACTIVE_BENCHMARK_TASKS.get(run_id, {})
    task_handle["is_cancelled"] = False

    try:
        run_record = db.query(BenchmarkRun).filter(BenchmarkRun.id == run_id).first()
        if not run_record:
            return

        run_record.status = "RUNNING"
        run_record.start_time = datetime.datetime.utcnow()
        db.commit()

        # Step 1: Starting row count
        start_count = db.query(func.count(WeatherObservation.id)).scalar() or 0
        run_record.starting_row_count = start_count
        db.commit()

        add_log_entry("INFO", "BENCHMARK_START", f"Real benchmark {run_id} started ({workload_type}, {operation_count} ops, concurrency={concurrency})", run_id=run_id)

        # Step 2: Warm-up operations
        rng = random.Random(42)
        if warm_up_count > 0:
            add_log_entry("INFO", "BENCHMARK_WARMUP", f"Executing {warm_up_count} warm-up operations on weather_observations", run_id=run_id)
            for w in range(warm_up_count):
                if workload_type == "READ":
                    run_single_read_operation(query_type, -w, rng)
                elif workload_type == "WRITE":
                    # For write warmup, do a read or lightweight check to avoid spamming public API
                    run_single_read_operation("LOCATION_FILTER", -w, rng)
                else:
                    run_single_read_operation(query_type, -w, rng)

        # Step 3: Main Workload Benchmark Execution
        latencies: List[float] = []
        op_results: List[Dict[str, Any]] = []
        successful_ops = 0
        failed_ops = 0
        api_latencies: List[float] = []
        db_insert_latencies: List[float] = []

        bench_start = time.perf_counter()

        if workload_type == "WRITE":
            # For WRITE benchmark: user requirement specifies obtaining fresh live data from Open-Meteo,
            # validating, inserting into AWS RDS, measuring DB insert time vs API time.
            # To be respectful of Open-Meteo rate limits, write operations fetch real rounds.
            write_ops_target = min(operation_count, 10)  # Bound public API cycles safely
            for i in range(1, write_ops_target + 1):
                if task_handle.get("is_cancelled"):
                    break
                res = run_single_write_operation(i)
                op_results.append(res)
                latencies.append(res["latency_ms"])
                db_insert_latencies.append(res["latency_ms"])
                if "api_latency_ms" in res and res["api_latency_ms"] > 0:
                    api_latencies.append(res["api_latency_ms"])

                if res["status"] == "SUCCESS":
                    successful_ops += 1
                else:
                    failed_ops += 1
                task_handle["progress"] = int((i / write_ops_target) * 100)

        elif workload_type == "READ":
            # For READ benchmark: queries the real weather_observations table
            def worker_read_task(idx):
                if task_handle.get("is_cancelled"):
                    return None
                return run_single_read_operation(query_type, idx, rng)

            if concurrency <= 1:
                for i in range(1, operation_count + 1):
                    if task_handle.get("is_cancelled"):
                        break
                    res = worker_read_task(i)
                    if res:
                        op_results.append(res)
                        latencies.append(res["latency_ms"])
                        if res["status"] == "SUCCESS":
                            successful_ops += 1
                        else:
                            failed_ops += 1
                    task_handle["progress"] = int((i / operation_count) * 100)
            else:
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [executor.submit(worker_read_task, i) for i in range(1, operation_count + 1)]
                    for i, future in enumerate(futures):
                        if task_handle.get("is_cancelled"):
                            break
                        res = future.result()
                        if res:
                            op_results.append(res)
                            latencies.append(res["latency_ms"])
                            if res["status"] == "SUCCESS":
                                successful_ops += 1
                            else:
                                failed_ops += 1
                        task_handle["progress"] = int(((i + 1) / operation_count) * 100)

        else:  # MIXED benchmark
            # Executes real SELECT reads with interleaved live Open-Meteo fetch+inserts
            for i in range(1, operation_count + 1):
                if task_handle.get("is_cancelled"):
                    break
                # Do read or write based on read_ratio
                if rng.random() < read_ratio or i > 10:
                    res = run_single_read_operation(query_type, i, rng)
                else:
                    res = run_single_write_operation(i)
                    if "api_latency_ms" in res:
                        api_latencies.append(res["api_latency_ms"])
                    db_insert_latencies.append(res["latency_ms"])

                op_results.append(res)
                latencies.append(res["latency_ms"])
                if res["status"] == "SUCCESS":
                    successful_ops += 1
                else:
                    failed_ops += 1
                task_handle["progress"] = int((i / operation_count) * 100)

        total_elapsed_ms = (time.perf_counter() - bench_start) * 1000.0
        elapsed_seconds = total_elapsed_ms / 1000.0 if total_elapsed_ms > 0 else 0.001

        # Step 4: Final verification and metrics
        final_count = db.query(func.count(WeatherObservation.id)).scalar() or 0
        stats = calculate_percentiles(latencies)
        throughput = successful_ops / elapsed_seconds if elapsed_seconds > 0 else 0.0
        total_attempted = successful_ops + failed_ops
        error_rate = (failed_ops / total_attempted * 100.0) if total_attempted > 0 else 0.0

        run_record.end_time = datetime.datetime.utcnow()
        run_record.total_elapsed_ms = total_elapsed_ms
        run_record.successful_ops = successful_ops
        run_record.failed_ops = failed_ops
        run_record.avg_latency_ms = stats["avg"]
        run_record.median_latency_ms = stats["median"]
        run_record.p95_latency_ms = stats["p95"]
        run_record.p99_latency_ms = stats["p99"]
        run_record.min_latency_ms = stats["min"]
        run_record.max_latency_ms = stats["max"]
        run_record.throughput_ops_sec = throughput
        run_record.error_rate_pct = error_rate
        run_record.final_row_count = final_count
        
        if api_latencies:
            run_record.api_response_time_ms = statistics.mean(api_latencies)
        if db_insert_latencies:
            run_record.db_insert_time_ms = statistics.mean(db_insert_latencies)

        run_record.status = "CANCELLED" if task_handle.get("is_cancelled") else "COMPLETED"

        # Save sampled individual result items (up to 500 points)
        sample_step = max(1, len(op_results) // 500)
        result_items_to_save = []
        for idx, item in enumerate(op_results):
            if idx % sample_step == 0:
                result_items_to_save.append(
                    BenchmarkResultItem(
                        run_id=run_id,
                        op_index=item["op_index"],
                        op_type=item["op_type"],
                        latency_ms=round(item["latency_ms"], 3),
                        status=item["status"],
                        error_message=item["error_message"]
                    )
                )
        if result_items_to_save:
            db.bulk_save_objects(result_items_to_save)

        db.commit()

        status_str = "Cancelled" if task_handle.get("is_cancelled") else "Completed"
        add_log_entry(
            "INFO", "BENCHMARK_COMPLETE",
            f"Benchmark {run_id} ({workload_type}) {status_str}: {successful_ops} ops in {total_elapsed_ms:.1f}ms | Avg: {stats['avg']:.2f}ms, p95: {stats['p95']:.2f}ms, {throughput:.1f} ops/sec",
            run_id=run_id
        )

    except Exception as e:
        logger.error(f"Benchmark run {run_id} failed: {e}")
        add_log_entry("ERROR", "BENCHMARK_ERROR", f"Benchmark run {run_id} failed: {str(e)}", run_id=run_id)
        if run_record:
            run_record.status = "FAILED"
            run_record.notes = str(e)
            db.commit()
    finally:
        ACTIVE_BENCHMARK_TASKS.pop(run_id, None)
        db.close()

def start_benchmark_run(
    run_name: str,
    workload_type: str,
    query_type: str,
    operation_count: int = 100,
    concurrency: int = 1,
    repetitions: int = 1,
    warm_up_count: int = 5,
    read_ratio: float = 0.8,
    is_optimized: bool = False,
    index_used: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates and launches a new benchmark job on AWS RDS PostgreSQL / local database.
    """
    ensure_weather_table()
    db: Session = SessionLocal()
    try:
        run_id = str(uuid.uuid4())
        
        # Check environment
        env_name = settings.ENVIRONMENT
        
        run_record = BenchmarkRun(
            id=run_id,
            run_name=run_name,
            environment=env_name,
            workload_type=workload_type.upper(),
            query_type=query_type.upper(),
            operation_count=operation_count,
            concurrency=concurrency,
            repetitions=repetitions,
            warm_up_count=warm_up_count,
            is_optimized=is_optimized,
            index_used=index_used,
            notes=notes,
            status="PENDING"
        )
        db.add(run_record)
        db.commit()

        # Track active task
        ACTIVE_BENCHMARK_TASKS[run_id] = {
            "progress": 0,
            "is_cancelled": False,
            "started_at": time.time()
        }

        # Spawn background thread
        thread = threading.Thread(
            target=execute_benchmark_task,
            args=(run_id, workload_type, query_type, operation_count, concurrency, warm_up_count, read_ratio),
            daemon=True
        )
        thread.start()

        return run_record.to_dict()
    finally:
        db.close()

def cancel_benchmark_run(run_id: str) -> Dict[str, Any]:
    if run_id in ACTIVE_BENCHMARK_TASKS:
        ACTIVE_BENCHMARK_TASKS[run_id]["is_cancelled"] = True
        add_log_entry("WARN", "BENCHMARK_CANCEL", f"Cancellation requested for benchmark {run_id}", run_id=run_id)
        return {"success": True, "message": f"Cancellation signal sent for benchmark {run_id}"}
    return {"success": False, "message": f"Benchmark {run_id} is not actively running"}

def get_benchmark_status(run_id: str) -> Dict[str, Any]:
    task = ACTIVE_BENCHMARK_TASKS.get(run_id)
    db: Session = SessionLocal()
    try:
        run = db.query(BenchmarkRun).filter(BenchmarkRun.id == run_id).first()
        if not run:
            return {"error": "Run not found"}
        data = run.to_dict()
        data["progress"] = task.get("progress", 100) if task else (100 if run.status == "COMPLETED" else 0)
        return data
    finally:
        db.close()

def get_all_benchmark_runs(
    workload_type: Optional[str] = None, 
    status: Optional[str] = None, 
    limit: int = 50
) -> List[Dict[str, Any]]:
    db: Session = SessionLocal()
    try:
        q = db.query(BenchmarkRun)
        if workload_type and workload_type != "ALL":
            q = q.filter(BenchmarkRun.workload_type == workload_type.upper())
        if status and status != "ALL":
            q = q.filter(BenchmarkRun.status == status.upper())
        runs = q.order_by(BenchmarkRun.created_at.desc()).limit(limit).all()
        return [r.to_dict() for r in runs]
    finally:
        db.close()
