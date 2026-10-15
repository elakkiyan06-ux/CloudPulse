# CloudPulse — Managed Database Performance Intelligence Platform
**Hackathon:** CloudForge 2026 | **Problem Code:** CF-PS-04 — Managed Database Performance  
**Target Managed Database:** AWS RDS PostgreSQL  
**Live Data Ingestion Pipeline:** Open-Meteo Real-Time Weather Telemetry API  

---

## 1. Executive Summary & Problem Statement

Modern cloud architectures frequently suffer from misplaced optimization efforts when external API latency, network transport, and database query latency are conflated. **CloudPulse** solves this challenge by implementing an automated, high-precision performance monitoring and benchmarking platform designed specifically for **AWS RDS PostgreSQL**.

### Core Guarantees:
- **Zero Mock / Synthetic Data:** CloudPulse operates entirely on live meteorological observations streamed directly from Open-Meteo's API across 8 predefined Indian metropolises (Chennai, Coimbatore, Bengaluru, Hyderabad, Mumbai, Delhi, Kolkata, Kochi).
- **Multi-Stage Latency Decomposition:** Measures and separates API HTTP retrieval time, backend JSON/pydantic validation time, database transactional write time, and analytical query execution time.
- **Real Query Plan Analysis:** Direct PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` execution showing planning time, execution time, scan methods (Sequential Scan vs. B-Tree Index Scan), and buffer hit ratios.
- **Honest Engineering Analysis:** Never fabricates artificial speedups. Explicitly differentiates between small cached in-memory tables where sequential scan beats index traversal, and large disk-bound datasets where B-Tree indexing yields substantial reductions.

---

## 2. Real-Time Data Pipeline Architecture

```
                                    CLOUDPULSE DATA ARCHITECTURE
                                    
  [ Open-Meteo Weather API ]  ── (HTTPS / REST) ──>  [ FastAPI Backend Service ]
       • Chennai (13.08, 80.27)                             • High-res perf_counter
       • Coimbatore (11.01, 76.95)                          • Pydantic V2 Validation
       • Bengaluru (12.97, 77.59)                           • Multi-stage Timing Engine
       • Hyderabad (17.38, 78.48)                                    │
       • Mumbai (19.07, 72.87)                                       ▼
       • Delhi (28.61, 77.20)                           [ Managed Database Layer ]
       • Kolkata (22.57, 88.36)                                  AWS RDS PostgreSQL
       • Kochi (9.93, 76.26)                               (Fallback: Local PostgreSQL)
                                                                     │
                                                                     ▼
                                                   [ `weather_observations` Table ]
                                                                     │
                         ┌───────────────────────────────────────────┴────────────────────────────┐
                         ▼                                                                        ▼
            [ Benchmark Execution Engine ]                                           [ Optimization Proving Ground ]
              • Real Read Query Workloads                                              • Baseline (Seq Scan) vs Indexed
              • Live Write Ingest Rounds                                               • B-Tree Composite Index
              • Latency Percentiles (p50/p95)                                          • EXPLAIN ANALYZE Comparison
                         │                                                                        │
                         └─────────────────────────────┬──────────────────────────────────────────┘
                                                       ▼
                                      [ CloudPulse Dashboard & Reports ]
                                        • Live Telemetry Explorer
                                        • Latency Decomposition Waterfall
                                        • Automated Compliance Reports (MD/CSV/JSON)
```

---

## 3. Database Schema (`weather_observations`)

The primary data entity is the `weather_observations` table in PostgreSQL:

| Column Name | PostgreSQL Type | Description |
|:---|:---|:---|
| `id` | `VARCHAR(36)` | Primary Key (UUID v4) |
| `location_name` | `VARCHAR(100)` | City name (e.g., Chennai, Coimbatore, Bengaluru) |
| `latitude` | `FLOAT` | Geographical latitude |
| `longitude` | `FLOAT` | Geographical longitude |
| `temperature` | `FLOAT` | Ambient temperature in °C |
| `relative_humidity` | `FLOAT` | Relative humidity percentage (%) |
| `wind_speed` | `FLOAT` | Wind speed at 10m in km/h |
| `weather_code` | `INTEGER` | WMO standard weather code |
| `surface_pressure` | `FLOAT` | Atmospheric pressure at surface in hPa |
| `precipitation` | `FLOAT` | Current precipitation in mm |
| `cloud_cover` | `FLOAT` | Cloud cover percentage (%) |
| `observation_time` | `TIMESTAMP` | Meteorological observation timestamp from API |
| `api_fetched_at` | `TIMESTAMP` | Backend ingestion start timestamp |
| `database_inserted_at` | `TIMESTAMP` | Database commit completion timestamp |

### Composite Optimization Index:
```sql
CREATE INDEX idx_weather_loc_time ON weather_observations (location_name, observation_time DESC);
```

---

## 4. Multi-Stage Latency Breakdown

When live data is fetched, CloudPulse measures and records each pipeline boundary with sub-millisecond precision:
1. **API Response Time ($T_{\text{api}}$):** Time elapsed waiting for Open-Meteo's HTTPS response.
2. **Backend Processing Time ($T_{\text{proc}}$):** Time taken to parse payload, validate schema, normalize weather codes, and construct model instances.
3. **Database Write Time ($T_{\text{db}}$):** Time consumed by PostgreSQL transaction begin, bulk insert statement execution, constraint verification, and commit.
4. **Total Request Time ($T_{\text{total}}$):** Complete wall-clock turnaround time.

---

## 5. Quickstart & Local Execution

### Prerequisites:
- Python 3.11+
- Node.js 18+ (for frontend assets, optional; vanilla JS frontend served directly)
- Docker & Docker Compose (for local PostgreSQL testing)

### Step 1: Clone and Configure Environment
```bash
cp .env.example .env
```
Edit `.env` to configure your database target:
```ini
# For AWS RDS PostgreSQL:
DATABASE_URL=postgresql+psycopg2://<USER>:<PASS>@<RDS_ENDPOINT>:5432/<DBNAME>

# For Local PostgreSQL via Docker:
# DATABASE_URL=postgresql+psycopg2://postgres:postgrespassword@localhost:5432/cloudpulse_local

# For Local Development Fallback:
DATABASE_URL=sqlite:///./cloudpulse.db
```

### Step 2: Start Local PostgreSQL (Docker)
```bash
docker compose up -d db
```

### Step 3: Launch CloudPulse Backend
```bash
cd backend
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

### Step 4: Access CloudPulse
Open your web browser and navigate to:
```
http://127.0.0.1:8080/
```

---

## 6. Running Automated Tests

CloudPulse includes a 14-point test suite covering API ingestion, schema validation, duplicate deduplication, query planning, benchmark calculations, index application/rollback, and report generation:

```bash
cd backend
pytest -v
```

All 14 tests run synchronously and do not require external cloud credentials:
```
tests/test_api.py::test_health_check PASSED
tests/test_api.py::test_system_status_and_cloud_config PASSED
tests/test_api.py::test_database_connection_health PASSED
tests/test_api.py::test_percentile_calculation_and_zero_handling PASSED
tests/test_api.py::test_honest_engineering_analysis_generation PASSED
tests/test_api.py::test_weather_condition_code_mapping PASSED
tests/test_api.py::test_live_weather_pipeline_fetch_and_store PASSED
tests/test_api.py::test_duplicate_observation_prevention PASSED
tests/test_api.py::test_database_records_api_and_pagination PASSED
tests/test_api.py::test_database_statistics PASSED
tests/test_api.py::test_query_plan_explain PASSED
tests/test_api.py::test_optimization_index_apply_and_rollback PASSED
tests/test_api.py::test_cloud_monitoring_metrics PASSED
tests/test_api.py::test_report_generation PASSED
```

---

## 7. Judge Demonstration Flow (Step-by-Step)

1. **Verify Cloud Database Health:**
   - Check the top header badge: Displays `AWS RDS PostgreSQL (CLOUD)` when connected to AWS, or `LOCAL DEVELOPMENT` with `CONNECTED` status.
2. **Fetch Live Meteorological Telemetry:**
   - Navigate to **Database Explorer** tab.
   - Click **`⚡ FETCH LIVE DATA`**.
   - Observe the live latency banner decompose the timings:
     - `Open-Meteo API:` ~150–350 ms
     - `Backend Validation:` < 1 ms
     - `Database Insert:` ~5–25 ms
     - `Total Pipeline Latency:` Measured wall-clock time.
   - Note the real weather observations populated across Chennai, Coimbatore, Bengaluru, etc.
3. **Run Real Read Benchmark:**
   - Navigate to **Benchmark Studio** tab.
   - Select **Read Benchmark** (`weather_observations`).
   - Click **`RUN BENCHMARK SUITE`**.
   - Review high-precision execution metrics: Avg Latency, P95, Median, Min, Max, and Throughput (ops/sec).
4. **Run Live Write Benchmark:**
   - Select **Write Benchmark** (`LIVE_INGEST`).
   - CloudPulse fetches live data rounds from Open-Meteo, executes real database insertions, and measures isolated database write latency vs API transport.
5. **Execute Optimization A/B Experiment:**
   - Navigate to **Optimization Lab** tab.
   - Select `idx_weather_loc_time on weather_observations`.
   - Click **`EXECUTE A/B BENCHMARK`**.
   - CloudPulse drops the index, captures the baseline execution plan via `EXPLAIN ANALYZE`, creates the composite index, captures the optimized plan, and renders a side-by-side comparison with honest engineering conclusions.
6. **Generate Compliance Audit Report:**
   - Navigate to **Reports & Exports** tab.
   - Click **`GENERATE COMPLIANCE REPORT`**.
   - Download or view the full markdown audit report containing environment telemetry, real database counts, and benchmark evidence.

---

## 8. Security & Best Practices

- **Zero Hardcoded Credentials:** All credentials passed strictly via environment variables (`DATABASE_URL`, `AWS_REGION`).
- **Connection Pooling & Timeouts:** SQLAlchemy connection pool with 10s database timeouts and 10s API HTTP client timeouts.
- **SQL Injection Prevention:** 100% parameterized queries via SQLAlchemy ORM and allowlisted index names for DDL operations.
- **Protected DDL Operations:** Browser interface restricts optimization actions exclusively to predefined, allowlisted indexes (`idx_weather_loc_time`). Arbitrary `DROP`, `TRUNCATE`, or `ALTER` statements are strictly blocked.
