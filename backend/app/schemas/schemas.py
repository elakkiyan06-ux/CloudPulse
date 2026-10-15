from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class DatabaseCheckRequest(BaseModel):
    connection_url: Optional[str] = None

class ConnectionStatusResponse(BaseModel):
    status: str
    connected: bool
    engine: str
    version: Optional[str] = None
    latency_ms: float
    has_benchmark_schema: bool
    pool_status: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None
    error: Optional[str] = None

class SeedRequest(BaseModel):
    count: int = Field(default=100, ge=1, le=50000, description="Number of synthetic records to seed")
    batch_size: int = Field(default=100, ge=10, le=1000)

class SeedResponse(BaseModel):
    records_inserted: int
    total_records: int
    duration_ms: float
    message: str

class VerifyCountResponse(BaseModel):
    verified: bool
    starting_row_count: int
    current_row_count: int
    checksum: str
    status: str
    message: str

class TableIndexInfo(BaseModel):
    index_name: str
    columns: List[str]
    unique: bool
    definition: Optional[str] = None

class DatabaseStatisticsResponse(BaseModel):
    table_name: str
    total_rows: int
    table_size_bytes: Optional[int] = None
    table_size_pretty: Optional[str] = "N/A"
    engine: str
    version: str
    indexes: List[TableIndexInfo]
    pool_status: Optional[Dict[str, Any]] = None

class BenchmarkCreateRequest(BaseModel):
    run_name: str = Field(default="Standard Read Benchmark", max_length=100)
    workload_type: str = Field(default="READ", description="READ, WRITE, or MIXED")
    query_type: str = Field(default="CATEGORY_FILTER", description="PK_LOOKUP, CATEGORY_FILTER, REGION_FILTER, RANGE_SCAN, AGGREGATE")
    operation_count: int = Field(default=100, ge=10, le=5000)
    concurrency: int = Field(default=1, ge=1, le=20)
    repetitions: int = Field(default=1, ge=1, le=5)
    warm_up_count: int = Field(default=10, ge=0, le=50)
    read_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    notes: Optional[str] = None

class BenchmarkRunResponse(BaseModel):
    id: str
    run_name: str
    environment: str
    workload_type: str
    query_type: str
    target_dataset_size: int
    operation_count: int
    concurrency: int
    repetitions: int
    warm_up_count: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_elapsed_ms: float
    api_response_time_ms: Optional[float] = 0.0
    db_insert_time_ms: Optional[float] = 0.0
    successful_ops: int
    failed_ops: int
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_ops_sec: float
    error_rate_pct: float
    starting_row_count: int
    final_row_count: int
    is_optimized: bool
    index_used: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[str] = None

class BenchmarkCompareResponse(BaseModel):
    baseline_run: BenchmarkRunResponse
    optimized_run: BenchmarkRunResponse
    latency_reduction_pct: float
    throughput_change_pct: float
    avg_latency_delta_ms: float
    median_latency_delta_ms: float
    p95_latency_delta_ms: float
    engineering_analysis: str

class OptimizationExperimentCreate(BaseModel):
    experiment_name: str = Field(default="Index Optimization: Location Temporal Filter")
    target_column: str = Field(default="location_name, observation_time")
    index_name: str = Field(default="idx_weather_loc_time")
    iterations: int = Field(default=50, ge=10, le=500)

class OptimizationExperimentResponse(BaseModel):
    id: str
    experiment_name: str
    description: Optional[str] = None
    target_table: str
    target_column: str
    index_name: str
    index_sql: str
    baseline_run_id: Optional[str] = None
    optimized_run_id: Optional[str] = None
    baseline_latency_ms: float
    optimized_latency_ms: float
    latency_reduction_pct: float
    throughput_change_pct: float
    scan_type_before: str
    scan_type_after: str
    analysis_text: Optional[str] = None
    status: str
    created_at: Optional[str] = None

class QueryPlanRequest(BaseModel):
    query_type: str = Field(default="LOCATION_FILTER")
    filter_value: Optional[str] = "Chennai"
    analyze: bool = True

class QueryPlanResponse(BaseModel):
    query_sql: str
    plan_text: str
    plan_json: Optional[Dict[str, Any]] = None
    scan_type: str
    estimated_cost: Optional[float] = None
    actual_time_ms: Optional[float] = None
    actual_rows: Optional[int] = None
    explanation: str

class CloudWatchMetricPoint(BaseModel):
    timestamp: str
    value: float

class CloudWatchMetricSeries(BaseModel):
    metric_name: str
    unit: str
    data_points: List[CloudWatchMetricPoint]
    latest_value: float

class CloudMonitoringResponse(BaseModel):
    status: str
    environment: str
    instance_id: Optional[str] = None
    region: str
    is_live_aws: bool
    metrics: Dict[str, CloudWatchMetricSeries]
    alarms: List[Dict[str, Any]]
    last_updated: str

class SystemLogEntry(BaseModel):
    timestamp: str
    severity: str
    event_type: str
    run_id: Optional[str] = None
    message: str
    logger: str

class ReportExportRequest(BaseModel):
    format: str = Field(default="markdown", description="markdown, json, csv, or html")
    run_ids: Optional[List[str]] = None
    experiment_id: Optional[str] = None
