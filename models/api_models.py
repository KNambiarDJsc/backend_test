from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

class RiskCategory(str, Enum):
    SUICIDALITY = "Suicidality"
    MANIA = "Mania"
    PSYCHOSIS = "Psychosis"
    SUBSTANCE_USE = "Substance use"
    ABUSE_NEGLECT = "Abuse and neglect"

class RiskStatus(str, Enum):
    NO_RISK = "NO_RISK"
    AT_RISK = "AT_RISK"
    IN_RISK = "IN_RISK"
    CLEARED = "CLEARED"
    UNCONFIRMED = "UNCONFIRMED"

# Request Models
class CreateSessionRequest(BaseModel):
    """Request model for creating a new chat session."""
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional session metadata")

class UserQueryRequest(BaseModel):
    """Request model for sending user query to agent."""
    userMessage: str = Field(..., min_length=1, max_length=10000, description="User's message to the agent")
    
    @validator('userMessage')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

# Response Models
class CreateSessionResponse(BaseModel):
    """Response model for session creation."""
    sessionId: str = Field(..., description="Unique session identifier")
    createdAt: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    userId: str = Field(..., description="User identifier")
    status: str = Field(default="active", description="Session status")

class AgentResponse(BaseModel):
    """Response model for agent queries."""
    agentMessage: str = Field(..., description="Agent's response message")
    sessionId: str = Field(..., description="Session identifier")
    messageId: str = Field(default_factory=lambda: str(uuid4()), description="Unique message identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional response metadata")

# Error Models
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(default=None, description="Request identifier for tracking")

class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    error: str = Field(default="validation_error", description="Error type")
    message: str = Field(..., description="Validation error message")
    field_errors: List[Dict[str, Any]] = Field(default_factory=list, description="Field-specific errors")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

# Internal Models
class UserProfile(BaseModel):
    """User profile information."""
    id: str = Field(..., description="User identifier")
    email: Optional[str] = Field(default=None, description="User email")
    phone: Optional[str] = Field(default=None, description="User phone number")
    created_at: Optional[datetime] = Field(default=None, description="User creation date")
    updated_at: Optional[datetime] = Field(default=None, description="User last update date")

class RiskProfile(BaseModel):
    """Risk assessment profile."""
    status: RiskStatus = Field(default=RiskStatus.NO_RISK, description="Risk status")
    active_category: Optional[RiskCategory] = Field(default=None, description="Active risk category")
    triggering_statement: str = Field(default="", description="Statement that triggered risk assessment")
    assessment_history: List[Dict[str, Any]] = Field(default_factory=list, description="Assessment interaction history")
    risk_categories: List[RiskCategory] = Field(default_factory=list, description="Identified risk categories")
    verdict: str = Field(default="CLEARED", description="Assessment verdict")

class SessionState(BaseModel):
    """Session state model."""
    user_profile: Optional[UserProfile] = Field(default=None, description="User profile information")
    at_risk: str = Field(default="False", description="At-risk status as string")
    risk_profile: Optional[RiskProfile] = Field(default=None, description="Risk assessment profile")
    agent_response: Optional[str] = Field(default=None, description="Latest agent response")
    
    @validator('at_risk')
    def validate_at_risk(cls, v):
        if v not in ["True", "False"]:
            raise ValueError("at_risk must be 'True' or 'False'")
        return v

# Health Check Model
class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(..., description="API version")
    uptime: float = Field(..., description="Service uptime in seconds")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependency health status")