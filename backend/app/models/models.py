import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean, Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class WeatherObservation(Base):
    """
    Real-time meteorological observations automatically retrieved from Open-Meteo API
    and persisted in AWS RDS PostgreSQL / local PostgreSQL.
    Zero synthetic, zero mock, zero user-entered data.
    """
    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_name = Column(String(50), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    relative_humidity = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    weather_code = Column(Integer, nullable=False)
    surface_pressure = Column(Float, nullable=False)
    precipitation = Column(Float, nullable=False)
    cloud_cover = Column(Float, nullable=False)
    observation_time = Column(DateTime, nullable=False, index=True)
    api_fetched_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    database_inserted_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_weather_loc_time_base", "location_name", "observation_time"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "location_name": self.location_name,
            "latitude": round(self.latitude, 4),
            "longitude": round(self.longitude, 4),
            "temperature": round(self.temperature, 2),
            "relative_humidity": round(self.relative_humidity, 1),
            "wind_speed": round(self.wind_speed, 2),
            "weather_code": self.weather_code,
            "surface_pressure": round(self.surface_pressure, 1),
            "precipitation": round(self.precipitation, 2),
            "cloud_cover": round(self.cloud_cover, 1),
            "observation_time": self.observation_time.isoformat() if self.observation_time else None,
            "api_fetched_at": self.api_fetched_at.isoformat() if self.api_fetched_at else None,
            "database_inserted_at": self.database_inserted_at.isoformat() if self.database_inserted_at else None
        }


class BenchmarkRun(Base):
    """
    Persisted record of an actual read/write benchmark run against AWS RDS PostgreSQL.
    """
    __tablename__ = "benchmark_runs"

    id = Column(String(36), primary_key=True)
    run_name = Column(String(100), nullable=False)
    environment = Column(String(50), nullable=False, default="Local")
    workload_type = Column(String(20), nullable=False)  # READ, WRITE, MIXED
    query_type = Column(String(50), nullable=False)     # LATEST_OBSERVATION, LOCATION_FILTER, WEATHER_SCAN, AGGREGATE
    target_dataset_size = Column(Integer, default=0)
    operation_count = Column(Integer, nullable=False)
    concurrency = Column(Integer, default=1)
    repetitions = Column(Integer, default=1)
    warm_up_count = Column(Integer, default=5)
    
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_elapsed_ms = Column(Float, default=0.0)
    
    api_response_time_ms = Column(Float, default=0.0)
    db_insert_time_ms = Column(Float, default=0.0)
    
    successful_ops = Column(Integer, default=0)
    failed_ops = Column(Integer, default=0)
    
    avg_latency_ms = Column(Float, default=0.0)
    median_latency_ms = Column(Float, default=0.0)
    p95_latency_ms = Column(Float, default=0.0)
    p99_latency_ms = Column(Float, default=0.0)
    min_latency_ms = Column(Float, default=0.0)
    max_latency_ms = Column(Float, default=0.0)
    
    throughput_ops_sec = Column(Float, default=0.0)
    error_rate_pct = Column(Float, default=0.0)
    
    starting_row_count = Column(Integer, default=0)
    final_row_count = Column(Integer, default=0)
    
    is_optimized = Column(Boolean, default=False)
    index_used = Column(String(100), nullable=True)
    
    query_plan_json = Column(Text, nullable=True)
    query_plan_text = Column(Text, nullable=True)
    
    status = Column(String(20), default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "run_name": self.run_name,
            "environment": self.environment,
            "workload_type": self.workload_type,
            "query_type": self.query_type,
            "target_dataset_size": self.target_dataset_size,
            "operation_count": self.operation_count,
            "concurrency": self.concurrency,
            "repetitions": self.repetitions,
            "warm_up_count": self.warm_up_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
            "api_response_time_ms": round(self.api_response_time_ms, 2),
            "db_insert_time_ms": round(self.db_insert_time_ms, 2),
            "successful_ops": self.successful_ops,
            "failed_ops": self.failed_ops,
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "median_latency_ms": round(self.median_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "p99_latency_ms": round(self.p99_latency_ms, 3),
            "min_latency_ms": round(self.min_latency_ms, 3),
            "max_latency_ms": round(self.max_latency_ms, 3),
            "throughput_ops_sec": round(self.throughput_ops_sec, 2),
            "error_rate_pct": round(self.error_rate_pct, 2),
            "starting_row_count": self.starting_row_count,
            "final_row_count": self.final_row_count,
            "is_optimized": self.is_optimized,
            "index_used": self.index_used,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class BenchmarkResultItem(Base):
    """
    Per-operation latency timing sample for detailed distributions and histograms.
    """
    __tablename__ = "benchmark_result_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), index=True, nullable=False)
    op_index = Column(Integer, nullable=False)
    op_type = Column(String(20), nullable=False)
    latency_ms = Column(Float, nullable=False)
    status = Column(String(20), default="SUCCESS")
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class OptimizationExperiment(Base):
    """
    A/B optimization experiment record on weather_observations table.
    """
    __tablename__ = "optimization_experiments"

    id = Column(String(36), primary_key=True)
    experiment_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    target_table = Column(String(50), default="weather_observations")
    target_column = Column(String(50), nullable=False)
    index_name = Column(String(100), nullable=False)
    index_sql = Column(Text, nullable=False)
    
    baseline_run_id = Column(String(36), nullable=True)
    optimized_run_id = Column(String(36), nullable=True)
    
    baseline_latency_ms = Column(Float, default=0.0)
    optimized_latency_ms = Column(Float, default=0.0)
    latency_reduction_pct = Column(Float, default=0.0)
    throughput_change_pct = Column(Float, default=0.0)
    
    scan_type_before = Column(String(50), default="Seq Scan")
    scan_type_after = Column(String(50), default="Index Scan")
    
    analysis_text = Column(Text, nullable=True)
    status = Column(String(30), default="CREATED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "experiment_name": self.experiment_name,
            "description": self.description,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "index_name": self.index_name,
            "index_sql": self.index_sql,
            "baseline_run_id": self.baseline_run_id,
            "optimized_run_id": self.optimized_run_id,
            "baseline_latency_ms": round(self.baseline_latency_ms, 3),
            "optimized_latency_ms": round(self.optimized_latency_ms, 3),
            "latency_reduction_pct": round(self.latency_reduction_pct, 2),
            "throughput_change_pct": round(self.throughput_change_pct, 2),
            "scan_type_before": self.scan_type_before,
            "scan_type_after": self.scan_type_after,
            "analysis_text": self.analysis_text,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AuditLog(Base):
    """
    Database persisted audit trail for live API ingest, database writes, and benchmarks.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    severity = Column(String(20), default="INFO")
    event_type = Column(String(50), nullable=False)
    run_id = Column(String(36), nullable=True)
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
