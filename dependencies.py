from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from supabase import create_client, Client
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)

# Supabase client
def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    if not settings.supabase_url or not settings.supabase_key:
        raise HTTPException(
            status_code=500, 
            detail="Supabase configuration missing"
        )
    return create_client(settings.supabase_url, settings.supabase_key)

# Services
def get_auth_service(supabase: Annotated[Client, Depends(get_supabase_client)]):
    """Get authentication service instance."""
    from services.auth_service import AuthService
    return AuthService(supabase)

def get_session_service(supabase: Annotated[Client, Depends(get_supabase_client)]):
    """Get session service instance."""
    from services.session_service import CustomSessionService
    return CustomSessionService(supabase)

def get_agent_service(supabase: Annotated[Client, Depends(get_supabase_client)]):
    """Get agent service instance."""
    from services.agent_service import AgentService
    return AgentService(supabase)

# Authentication dependency
async def get_current_user(
    authorization: Annotated[str, Header()],
    supabase: Annotated[Client, Depends(get_supabase_client)]
):
    """Get current authenticated user."""
    try:
        # Extract Bearer token
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = authorization.split(" ")[1]
        
        # Validate with Supabase
        response = supabase.auth.get_user(token)
        
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create UserProfile
        from models.api_models import UserProfile
        return UserProfile(
            id=response.user.id,
            email=getattr(response.user, 'email', None),
            phone=getattr(response.user, 'phone', None)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )