from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, List
from app.core.config import settings
from app.core.database import test_database_connection
from app.core.logging_config import get_recent_logs, clear_logs
from app.schemas.schemas import (
    ConnectionStatusResponse, DatabaseCheckRequest, SeedRequest, SeedResponse,
    VerifyCountResponse, DatabaseStatisticsResponse, BenchmarkCreateRequest,
    BenchmarkRunResponse, BenchmarkCompareResponse, OptimizationExperimentCreate,
    OptimizationExperimentResponse, QueryPlanRequest, QueryPlanResponse,
    CloudMonitoringResponse, SystemLogEntry, ReportExportRequest
)
from app.services.db_service import (
    verify_record_count, get_database_statistics,
    reset_dataset, cleanup_test_resources, create_schema
)
from app.services.benchmark_engine import (
    start_benchmark_run, cancel_benchmark_run, get_benchmark_status,
    get_all_benchmark_runs
)
from app.services.optimization_service import (
    apply_index, rollback_index, run_optimization_experiment,
    get_all_experiments, ALLOWLISTED_INDEXES
)
from app.services.weather_service import (
    fetch_and_store_live_weather, get_live_weather_observations
)
from app.services.query_plan_service import explain_query, QUERY_TEMPLATES
from app.services.cloudwatch_service import get_cloudwatch_metrics
from app.services.report_generator import generate_performance_audit_report

api_router = APIRouter()

# ==================== Health & System ====================

@api_router.get("/system/status")
def get_system_status():
    db_stat = test_database_connection()
    return {
        "project": settings.PROJECT_NAME,
        "hackathon_code": settings.HACKATHON_CODE,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_stat,
        "data_source": "Open-Meteo Real-Time Weather API",
        "predefined_locations": settings.PREDEFINED_LOCATIONS,
        "cloudwatch_mode": "AWS Live" if (settings.AWS_RDS_INSTANCE_ID and settings.AWS_ACCESS_KEY_ID) else "Simulation"
    }

@api_router.get("/database/status", response_model=ConnectionStatusResponse)
def get_db_status():
    return test_database_connection()

@api_router.post("/database/check", response_model=ConnectionStatusResponse)
def check_db_connection(req: DatabaseCheckRequest):
    return test_database_connection(req.connection_url)

# ==================== Real-Time Weather Pipeline (Open-Meteo -> AWS RDS) ====================

@api_router.post("/weather/fetch")
def fetch_live_weather():
    """
    Fetches real-time weather from Open-Meteo API, validates data,
    inserts into AWS RDS PostgreSQL, and returns latency breakdown.
    """
    return fetch_and_store_live_weather()

@api_router.get("/weather/live")
def get_live_weather(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    location_name: Optional[str] = None
):
    """Retrieves real weather observations from AWS RDS weather_observations."""
    return get_live_weather_observations(page, page_size, location_name)

@api_router.get("/weather/locations")
def get_predefined_locations():
    """Returns the predefined locations configured with precise geographical coordinates."""
    return settings.PREDEFINED_LOCATIONS

# ==================== Database & Dataset ====================

@api_router.get("/database/records")
def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None
):
    return get_live_weather_observations(page, page_size, location_name=region or category or search)

@api_router.get("/database/statistics")
def get_db_statistics():
    return get_database_statistics()

@api_router.post("/database/seed")
def seed_dataset(req: Optional[SeedRequest] = None):
    res = fetch_and_store_live_weather()
    return {
        "records_inserted": res["records_inserted"],
        "total_records": res["total_database_records"],
        "duration_ms": res["total_operation_time_ms"],
        "message": f"Successfully fetched live observations from Open-Meteo into AWS RDS ({res['records_inserted']} inserted, {res['duplicate_count']} existing)."
    }

@api_router.post("/database/verify-count", response_model=VerifyCountResponse)
def verify_dataset_count(expected_count: Optional[int] = None):
    return verify_record_count(expected_count)

@api_router.post("/database/reset")
def reset_db_dataset():
    return reset_dataset()

@api_router.post("/database/cleanup")
def cleanup_test_objects():
    return cleanup_test_resources()

# ==================== Benchmark Studio ====================

@api_router.post("/benchmarks", response_model=BenchmarkRunResponse)
def create_and_start_benchmark(req: BenchmarkCreateRequest):
    return start_benchmark_run(
        run_name=req.run_name,
        workload_type=req.workload_type,
        query_type=req.query_type,
        operation_count=req.operation_count,
        concurrency=req.concurrency,
        repetitions=req.repetitions,
        warm_up_count=req.warm_up_count,
        read_ratio=req.read_ratio,
        notes=req.notes
    )

@api_router.get("/benchmarks", response_model=List[BenchmarkRunResponse])
def list_benchmarks(
    workload_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    return get_all_benchmark_runs(workload_type, status, limit)

@api_router.get("/benchmarks/{run_id}/status")
def benchmark_status(run_id: str):
    return get_benchmark_status(run_id)

@api_router.post("/benchmarks/{run_id}/cancel")
def cancel_benchmark(run_id: str):
    return cancel_benchmark_run(run_id)

@api_router.get("/benchmarks/compare")
def compare_benchmarks(baseline_id: str, optimized_id: str):
    base_run = get_benchmark_status(baseline_id)
    opt_run = get_benchmark_status(optimized_id)
    if "error" in base_run or "error" in opt_run:
        raise HTTPException(status_code=404, detail="One or both benchmark runs could not be found.")

    base_lat = base_run.get("avg_latency_ms", 0.0)
    opt_lat = opt_run.get("avg_latency_ms", 0.0)
    base_thru = base_run.get("throughput_ops_sec", 0.0)
    opt_thru = opt_run.get("throughput_ops_sec", 0.0)

    lat_red_pct = ((base_lat - opt_lat) / base_lat * 100.0) if base_lat > 0 else 0.0
    thru_chg_pct = ((opt_thru - base_thru) / base_thru * 100.0) if base_thru > 0 else 0.0

    analysis = (
        f"Compared {base_run['run_name']} vs {opt_run['run_name']}. "
        f"Average latency shifted by {lat_red_pct:+.1f}%. "
        f"Throughput shifted by {thru_chg_pct:+.1f}%."
    )

    return {
        "baseline_run": base_run,
        "optimized_run": opt_run,
        "latency_reduction_pct": round(lat_red_pct, 2),
        "throughput_change_pct": round(thru_chg_pct, 2),
        "avg_latency_delta_ms": round(base_lat - opt_lat, 3),
        "median_latency_delta_ms": round(base_run.get("median_latency_ms", 0) - opt_run.get("median_latency_ms", 0), 3),
        "p95_latency_delta_ms": round(base_run.get("p95_latency_ms", 0) - opt_run.get("p95_latency_ms", 0), 3),
        "engineering_analysis": analysis
    }

# ==================== Optimization Lab ====================

@api_router.get("/optimization/experiments", response_model=List[OptimizationExperimentResponse])
def list_optimization_experiments():
    return get_all_experiments()

@api_router.post("/optimization/experiments", response_model=OptimizationExperimentResponse)
def trigger_optimization_experiment(req: OptimizationExperimentCreate):
    return run_optimization_experiment(
        experiment_name=req.experiment_name,
        target_column=req.target_column,
        index_name=req.index_name,
        iterations=req.iterations
    )

@api_router.post("/optimization/apply-index")
def apply_optimization_index(index_name: str = "idx_benchmark_category"):
    return apply_index(index_name)

@api_router.post("/optimization/rollback-index")
def rollback_optimization_index(index_name: str = "idx_benchmark_category"):
    return rollback_index(index_name)

@api_router.get("/optimization/supported-indexes")
def list_supported_indexes():
    return ALLOWLISTED_INDEXES

# ==================== Query Plan Explorer ====================

@api_router.post("/query-plans/explain", response_model=QueryPlanResponse)
def run_query_explain(req: QueryPlanRequest):
    return explain_query(req.query_type, req.filter_value, req.analyze)

@api_router.get("/query-plans/templates")
def list_query_templates():
    return QUERY_TEMPLATES

# ==================== Cloud Monitoring ====================

@api_router.get("/cloud/metrics", response_model=CloudMonitoringResponse)
def get_monitoring_metrics():
    return get_cloudwatch_metrics()

# ==================== Reports ====================

@api_router.post("/reports/generate")
def generate_report(req: ReportExportRequest):
    return generate_performance_audit_report(req.format, req.run_ids, req.experiment_id)

@api_router.get("/reports/download")
def download_report(format: str = "markdown"):
    rep = generate_performance_audit_report(format)
    return Response(
        content=rep["content"],
        media_type=rep["content_type"],
        headers={"Content-Disposition": f"attachment; filename={rep['filename']}"}
    )

# ==================== System Logs ====================

@api_router.get("/logs", response_model=List[SystemLogEntry])
def get_logs(
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100
):
    return get_recent_logs(severity, event_type, limit)

@api_router.post("/logs/clear")
def clear_system_logs():
    clear_logs()
    return {"success": True, "message": "Log buffer cleared"}

# ==================== Settings ====================

@api_router.get("/settings")
def get_settings():
    return {
        "project_name": settings.PROJECT_NAME,
        "hackathon_code": settings.HACKATHON_CODE,
        "environment": settings.ENVIRONMENT,
        "database_url_safe": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL,
        "pool_size": settings.DB_POOL_SIZE,
        "aws_region": settings.AWS_REGION,
        "aws_rds_instance_id": settings.AWS_RDS_INSTANCE_ID or "(Not configured - simulated telemetry)",
        "aws_has_credentials": bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY),
        "max_benchmark_ops": settings.MAX_BENCHMARK_OPERATIONS,
        "max_concurrency": settings.MAX_BENCHMARK_CONCURRENCY,
        "default_warmup": settings.DEFAULT_WARMUP_OPS
    }
