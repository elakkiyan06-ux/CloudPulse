import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import add_log_entry, logger
from app.api.router import api_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    add_log_entry("INFO", "APP_START", f"{settings.PROJECT_NAME} v{settings.VERSION} online in {settings.ENVIRONMENT}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Production-style backend for CloudForge 2026 hackathon (Problem Code: CF-PS-04). "
        "Measures read and write performance for a managed relational database, runs repeatable benchmarks, "
        "applies index optimizations, and visualizes query plans & CloudWatch telemetry."
    ),
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "CloudPulse Backend",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "hackathon_code": settings.HACKATHON_CODE
    }

# Mount static frontend files if directory exists
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend"))
if not os.path.exists(frontend_path):
    frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))

if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Don't intercept API or docs routes
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(frontend_path, full_path)
        if file_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Page not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
