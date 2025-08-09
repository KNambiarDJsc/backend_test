from fastapi import APIRouter, Depends, HTTPException, status
from models.api_models import (
    CreateSessionRequest, CreateSessionResponse,
    UserQueryRequest, AgentResponse, UserProfile
)
from services.agent_service import AgentService
from dependencies import get_current_user, get_agent_service

router = APIRouter()

@router.post("/sessions/", 
             response_model=CreateSessionResponse, 
             status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    user: UserProfile = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Create a new chat session for the authenticated user."""
    try:
        session_id = await agent_service.create_session(user, request.metadata)
        
        return CreateSessionResponse(
            sessionId=session_id,
            userId=user.id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

@router.post("/sessions/{session_id}", response_model=AgentResponse)
async def post_user_query(
    session_id: str,
    request: UserQueryRequest,
    user: UserProfile = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Send a user message to the AI agent and get a response."""
    try:
        agent_response = await agent_service.process_user_query(
            user_profile=user,
            session_id=session_id,
            user_message=request.userMessage
        )
        
        return AgentResponse(
            agentMessage=agent_response,
            sessionId=session_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your message. Please try again."
        )

# Test endpoints
@router.post("/test/sessions/", response_model=CreateSessionResponse)
async def test_create_session(
    request: CreateSessionRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    """Test endpoint - creates session without authentication."""
    from models.api_models import UserProfile
    mock_user = UserProfile(id="test_user_123", email="test@example.com")
    
    session_id = await agent_service.create_session(mock_user, request.metadata)
    
    return CreateSessionResponse(
        sessionId=session_id,
        userId=mock_user.id
    )

@router.post("/test/sessions/{session_id}", response_model=AgentResponse)
async def test_user_query(
    session_id: str,
    request: UserQueryRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    """Test endpoint - processes query without authentication."""
    from models.api_models import UserProfile
    mock_user = UserProfile(id="test_user_123", email="test@example.com")
    
    agent_response = await agent_service.process_user_query(
        user_profile=mock_user,
        session_id=session_id,
        user_message=request.userMessage
    )
    
    return AgentResponse(
        agentMessage=agent_response,
        sessionId=session_id
    )