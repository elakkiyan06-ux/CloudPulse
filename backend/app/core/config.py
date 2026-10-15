import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

try:
    from dotenv import load_dotenv
    # Load .env from backend directory or project root
    for p in [Path.cwd() / ".env", Path.cwd().parent / ".env", Path(__file__).resolve().parents[2] / ".env"]:
        if p.is_file():
            load_dotenv(p)
            break
except ImportError:
    pass

class Settings(BaseModel):
    PROJECT_NAME: str = "CloudPulse — Managed Database Performance Intelligence Platform"
    HACKATHON_CODE: str = "CF-PS-04"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api"
    
    # Real-time external data source
    OPEN_METEO_BASE_URL: str = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
    
    # Predefined locations for real-time live observations (No user manual entry)
    PREDEFINED_LOCATIONS: List[Dict[str, Any]] = [
        {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707},
        {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558},
        {"name": "Bengaluru", "latitude": 12.9716, "longitude": 77.5946},
        {"name": "Hyderabad", "latitude": 17.3850, "longitude": 78.4867},
        {"name": "Mumbai", "latitude": 19.0760, "longitude": 72.8777},
        {"name": "Delhi", "latitude": 28.6139, "longitude": 77.2090},
        {"name": "Kolkata", "latitude": 22.5726, "longitude": 88.3639},
        {"name": "Kochi", "latitude": 9.9312, "longitude": 76.2673},
    ]

    # Database Settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./cloudpulse.db")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_TIMEOUT_SECONDS: int = int(os.getenv("DB_TIMEOUT_SECONDS", "10"))
    
    # Environment identification (Distinguish CLOUD AWS RDS vs LOCAL)
    @property
    def ENVIRONMENT(self) -> str:
        url = self.DATABASE_URL.lower()
        if "rds.amazonaws.com" in url or "aws" in url:
            return "AWS RDS PostgreSQL (CLOUD)"
        elif "postgresql" in url:
            return "PostgreSQL (LOCAL)"
        else:
            return "SQLite (LOCAL DEVELOPMENT)"

    @property
    def IS_AWS_RDS(self) -> bool:
        return "rds.amazonaws.com" in self.DATABASE_URL.lower() or "aws" in self.DATABASE_URL.lower()

    # AWS CloudWatch / RDS instance details
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_RDS_INSTANCE_ID: Optional[str] = os.getenv("AWS_RDS_INSTANCE_ID", None)
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID", None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY", None)
    AWS_CLOUDWATCH_NAMESPACE: str = os.getenv("AWS_CLOUDWATCH_NAMESPACE", "AWS/RDS")
    
    # Benchmark safety limits
    MAX_BENCHMARK_OPERATIONS: int = 5000
    MAX_BENCHMARK_CONCURRENCY: int = 20
    DEFAULT_WARMUP_OPS: int = 5

settings = Settings()
