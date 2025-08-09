# config/settings.py
import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseModel):
    # App Configuration
    app_name: str = "FeelWell AI Backend"
    debug: bool = True
    version: str = "1.0.0"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8001
    reload: bool = True
    
    # Supabase Configuration
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_jwt_secret: Optional[str] = None
    
    # ADK Configuration
    adk_app_name: str = "feelwell_chat_agent"
    sample_state_path: str = "chat_agent/profiles/user_empty_default.json"
    
    # Google AI Configuration
    google_api_key: Optional[str] = None
    
    # CORS Configuration
    cors_origins: list[str] = ["*"]
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"

def get_settings() -> Settings:
    """Create settings instance with environment variables."""
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        debug=os.getenv("DEBUG", "true").lower() == "true",
        reload=os.getenv("RELOAD", "true").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        cors_origins=os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
    )

# Create the settings instance
settings = get_settings()