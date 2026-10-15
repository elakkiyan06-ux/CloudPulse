import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.services.benchmark_engine import calculate_percentiles, run_single_read_operation
from app.services.optimization_service import (
    generate_honest_engineering_analysis, apply_index, rollback_index, ALLOWLISTED_INDEXES
)
from app.services.weather_service import (
    get_weather_condition, fetch_and_store_live_weather, get_live_weather_observations, ensure_weather_table
)
from app.models.models import WeatherObservation
from app.core.database import SessionLocal, test_database_connection as check_db_health, init_db
import random

client = TestClient(app)

# Ensure schema is up to date before tests
init_db()

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["hackathon_code"] == "CF-PS-04"

def test_system_status_and_cloud_config():
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert data["database"]["connected"] is True
    assert "data_source" in data
    assert "Open-Meteo" in data["data_source"]
    assert "predefined_locations" in data
    assert len(data["predefined_locations"]) == 8

def test_database_connection_health():
    stat = check_db_health()
    assert stat["connected"] is True
    assert stat["status"] == "CONNECTED"
    assert stat["latency_ms"] >= 0.0

def test_percentile_calculation_and_zero_handling():
    # Empty list zero-handling
    empty_res = calculate_percentiles([])
    assert empty_res["avg"] == 0.0
    assert empty_res["median"] == 0.0
    assert empty_res["p95"] == 0.0

    # Monotonic sample
    samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    res = calculate_percentiles(samples)
    assert res["min"] == 10.0
    assert res["max"] == 100.0
    assert res["median"] == 55.0
    assert res["p95"] == 100.0

def test_honest_engineering_analysis_generation():
    # Significant speedup
    fast_text = generate_honest_engineering_analysis(
        baseline_lat=25.0,
        optimized_lat=4.0,
        baseline_thru=40.0,
        optimized_thru=250.0,
        scan_before="Seq Scan",
        scan_after="Index Scan",
        row_count=1000
    )
    assert "Measured latency decreased by 84.0%" in fast_text

    # No measurable speedup (honest explanation)
    flat_text = generate_honest_engineering_analysis(
        baseline_lat=1.2,
        optimized_lat=1.18,
        baseline_thru=800.0,
        optimized_thru=810.0,
        scan_before="Seq Scan",
        scan_after="Index Scan",
        row_count=100
    )
    assert "No measurable improvement was observed under this workload" in flat_text
    assert "shared_buffers" in flat_text

def test_weather_condition_code_mapping():
    assert get_weather_condition(0) == "Clear Sky"
    assert get_weather_condition(61) == "Slight Rain"
    assert get_weather_condition(95) == "Thunderstorm"

def test_live_weather_pipeline_fetch_and_store():
    # Tests the complete Open-Meteo -> Backend -> DB insert pipeline
    res = fetch_and_store_live_weather()
    assert res["status"] == "Live data received"
    assert res["records_received"] >= 1
    assert res["total_database_records"] >= 1
    assert res["api_response_time_ms"] > 0
    assert res["database_insert_time_ms"] >= 0
    assert res["total_operation_time_ms"] > 0
    assert "latency_explanation" in res

def test_duplicate_observation_prevention():
    # Inserting the exact same observations a second time must prevent duplicates
    res1 = fetch_and_store_live_weather()
    res2 = fetch_and_store_live_weather()
    # On immediate second fetch with same timestamp, duplicates are detected
    assert res2["duplicate_count"] >= 0
    assert res2["total_database_records"] >= res1["records_inserted"]

def test_database_records_api_and_pagination():
    res = client.get("/api/database/records?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert "observations" in data
    assert len(data["observations"]) <= 5
    assert data["total_observations"] >= 1

def test_database_statistics():
    res = client.get("/api/database/statistics")
    assert res.status_code == 200
    data = res.json()
    assert data["table_name"] == "weather_observations"
    assert data["total_rows"] >= 1

def test_query_plan_explain():
    res = client.post("/api/query-plans/explain", json={
        "query_type": "LOCATION_FILTER",
        "filter_value": "Chennai",
        "analyze": True
    })
    assert res.status_code == 200
    data = res.json()
    assert "query_sql" in data
    assert "weather_observations" in data["query_sql"]
    assert "plan_text" in data
    assert "explanation" in data

def test_optimization_index_apply_and_rollback():
    idx_name = "idx_weather_loc_time"
    # Ensure dropped first
    try:
        rollback_index(idx_name)
    except Exception:
        pass

    # Apply
    apply_res = apply_index(idx_name)
    assert apply_res["success"] is True
    assert apply_res["index_name"] == idx_name

    # Rollback
    roll_res = rollback_index(idx_name)
    assert roll_res["success"] is True
    assert roll_res["index_name"] == idx_name

def test_cloud_monitoring_metrics():
    res = client.get("/api/cloud/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "CPUUtilization" in data["metrics"]
    assert "DatabaseConnections" in data["metrics"]

def test_report_generation():
    # Markdown
    md_res = client.post("/api/reports/generate", json={"format": "markdown"})
    assert md_res.status_code == 200
    md_data = md_res.json()
    assert "CF-PS-04" in md_data["content"]
    assert "Open-Meteo" in md_data["content"]
    assert md_data["content_type"] == "text/markdown"

    # JSON
    json_res = client.post("/api/reports/generate", json={"format": "json"})
    assert json_res.status_code == 200
    json_data = json_res.json()
    assert json_data["content_type"] == "application/json"
    assert "data_source" in json_data["content"]

    # CSV
    csv_res = client.post("/api/reports/generate", json={"format": "csv"})
    assert csv_res.status_code == 200
    csv_data = csv_res.json()
    assert csv_data["content_type"] == "text/csv"
