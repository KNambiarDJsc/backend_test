from fastapi import APIRouter, Depends
from models.api_models import UserProfile
from dependencies import get_current_user

router = APIRouter()

@router.get("/me", response_model=UserProfile)
async def get_current_user_info(user: UserProfile = Depends(get_current_user)):
    """Get current user information."""
    return user