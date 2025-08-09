# main.py - Entry point and app setup only
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from utils.logger import setup_logging, get_logger
from models.api_models import HealthCheckResponse
from services.agent_service import AgentService
from dependencies import get_supabase_client

# Global variables
app_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_logging()
    logger = get_logger("startup")
    logger.info("Starting FeelWell AI Backend", version=settings.version)
    yield
    logger.info("Shutting down FeelWell AI Backend")

# Initialize FastAPI app
app = FastAPI(
    title="FeelWell AI Backend",
    description="FastAPI backend for FeelWell agentic chat application",
    version=settings.version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Setup middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Import and include routers
from api import auth_router, sessions_router, health_router

app.include_router(health_router.router, tags=["Health"])
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(sessions_router.router, prefix="/api", tags=["Sessions"])

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FeelWell AI Backend",
        "version": settings.version,
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )