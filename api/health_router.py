import time
from fastapi import APIRouter, Depends, HTTPException, status
from models.api_models import HealthCheckResponse
from services.agent_service import AgentService
from dependencies import get_agent_service

router = APIRouter()

# Global variable for tracking uptime
app_start_time = time.time()

@router.get("/health", response_model=HealthCheckResponse)
async def health_check(agent_service: AgentService = Depends(get_agent_service)):
    """Health check endpoint."""
    try:
        uptime = time.time() - app_start_time
        dependencies = await agent_service.health_check()
        
        return HealthCheckResponse(
            uptime=uptime,
            dependencies=dependencies
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check failed"
        )