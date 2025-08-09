from typing import Optional
from fastapi import HTTPException, status
from supabase import Client
import structlog
from models.api_models import UserProfile

logger = structlog.get_logger(__name__)

class AuthService:
    """Service for handling authentication operations."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.logger = logger.bind(service="auth")
    
    async def verify_token(self, token: str) -> UserProfile:
        """
        Verify JWT token and return user profile.
        
        Args:
            token: JWT token from Authorization header
            
        Returns:
            UserProfile: User profile information
            
        Raises:
            HTTPException: If token is invalid or user not found
        """
        try:
            # Validate token with Supabase
            response = self.supabase.auth.get_user(token)
            
            if not response or not response.user:
                self.logger.warning("Invalid token provided")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            user = response.user
            
            # Create UserProfile from Supabase user
            user_profile = UserProfile(
                id=user.id,
                email=getattr(user, 'email', None),
                phone=getattr(user, 'phone', None)
            )
            
            self.logger.info("Token verified successfully", user_id=user.id)
            return user_profile
            
        except HTTPException:
            # Re-raise FastAPI HTTP exceptions
            raise
        except Exception as e:
            self.logger.error("Error verifying token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def extract_token_from_header(self, authorization_header: str) -> str:
        """
        Extract Bearer token from Authorization header.
        
        Args:
            authorization_header: Authorization header value
            
        Returns:
            str: JWT token
            
        Raises:
            HTTPException: If header format is invalid
        """
        if not authorization_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            scheme, token = authorization_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication scheme. Expected 'Bearer'",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return token
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )