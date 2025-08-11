from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Optional, Dict, Any
import structlog
import uuid
import asyncio

from models.api_models import (
    CreateSessionRequest, CreateSessionResponse,
    UserQueryRequest, AgentResponse, UserProfile,
    ErrorResponse
)
from services.agent_service import AgentService
from dependencies import get_current_user, get_agent_service, get_supabase_client
from config.settings import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

# =====================================================
# MAIN POST ENDPOINTS - These are the ones you need!
# =====================================================

@router.post("/sessions/", 
             response_model=CreateSessionResponse, 
             status_code=status.HTTP_201_CREATED,
             summary="Create new chat session",
             description="Creates a new chat session for the authenticated user")
async def create_session(
    request: CreateSessionRequest,
    user: UserProfile = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    POST /api/sessions/
    
    Creates a new chat session for the authenticated user.
    This initializes the agent state and creates all necessary database records.
    
    Headers:
    - Authorization: Bearer <jwt_token>
    
    Request Body:
    {
        "metadata": {}  // Optional session metadata
    }
    
    Response:
    {
        "sessionId": "uuid-string",
        "userId": "user-id",
        "createdAt": "2024-01-01T00:00:00Z",
        "status": "active"
    }
    """
    try:
        session_id = await agent_service.create_session(user, request.metadata)
        
        logger.info("Session created successfully", 
                   session_id=session_id, 
                   user_id=user.id,
                   metadata=request.metadata)
        
        return CreateSessionResponse(
            sessionId=session_id,
            userId=user.id,
            status="active"
        )
        
    except Exception as e:
        logger.error("Session creation failed", 
                    error=str(e), 
                    user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session. Please try again."
        )

@router.post("/sessions/{session_id}", 
             response_model=AgentResponse,
             summary="Send message to agent",
             description="Sends a user message to the AI agent and gets a response")
async def post_user_query(
    session_id: str,
    request: UserQueryRequest,
    user: UserProfile = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    POST /api/sessions/{sessionId}
    
    Sends a user message to the AI agent and returns the agent's response.
    This triggers the full agent pipeline including risk detection, 
    context collection, and persona response.
    
    Headers:
    - Authorization: Bearer <jwt_token>
    
    Path Parameters:
    - session_id: The session ID from create_session
    
    Request Body:
    {
        "userMessage": "Hello, how are you feeling today?"
    }
    
    Response:
    {
        "agentMessage": "Hello! I'm here to support you. How are you feeling?",
        "sessionId": "uuid-string",
        "messageId": "message-uuid",
        "timestamp": "2024-01-01T00:00:00Z",
        "metadata": {
            "riskDetected": false,
            "agentUsed": "PersonaAgent"
        }
    }
    """
    try:
        # Validate session exists and belongs to user
        await _validate_session_access(session_id, user.id, agent_service)
        
        # Process the user message through the agent pipeline
        agent_response = await agent_service.process_user_query(
            user_profile=user,
            session_id=session_id,
            user_message=request.userMessage
        )
        
        # Get additional metadata about the response
        metadata = await _get_response_metadata(session_id, user.id, agent_service)
        
        logger.info("User query processed successfully", 
                   session_id=session_id, 
                   user_id=user.id,
                   message_length=len(request.userMessage),
                   response_length=len(agent_response))
        
        return AgentResponse(
            agentMessage=agent_response,
            sessionId=session_id,
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process user query", 
                    error=str(e), 
                    session_id=session_id,
                    user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your message. Please try again."
        )

# =====================================================
# ADDITIONAL ENDPOINTS FOR TESTING AND MANAGEMENT
# =====================================================

@router.get("/sessions/{session_id}/history",
            summary="Get session chat history",
            description="Retrieves the chat history for a specific session")
async def get_session_history(
    session_id: str,
    limit: int = 50,
    user: UserProfile = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get chat history for a session."""
    try:
        await _validate_session_access(session_id, user.id, None)
        
        result = supabase.table('chat_messages') \
            .select('role, content, created_at, metadata') \
            .eq('session_id', session_id) \
            .eq('user_id', user.id) \
            .order('created_at', desc=False) \
            .limit(limit) \
            .execute()
        
        return {
            "sessionId": session_id,
            "messages": result.data,
            "total": len(result.data)
        }
        
    except Exception as e:
        logger.error("Failed to get session history", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat history"
        )

@router.get("/sessions/{session_id}/state",
            summary="Get session state",
            description="Retrieves the current agent state for a session")
async def get_session_state(
    session_id: str,
    user: UserProfile = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get current session state."""
    try:
        await _validate_session_access(session_id, user.id, None)
        
        result = supabase.table('chat_sessions') \
            .select('state, updated_at') \
            .eq('id', session_id) \
            .eq('user_id', user.id) \
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return {
            "sessionId": session_id,
            "state": result.data[0]['state'],
            "lastUpdated": result.data[0]['updated_at']
        }
        
    except Exception as e:
        logger.error("Failed to get session state", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session state"
        )

@router.delete("/sessions/{session_id}",
               summary="Delete session",
               description="Deletes a session and all associated data")
async def delete_session(
    session_id: str,
    user: UserProfile = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Delete a session and all associated data."""
    try:
        await _validate_session_access(session_id, user.id, agent_service)
        
        # Use agent service to handle deletion
        success = await agent_service.delete_session(user.id, session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete session"
            )
        
        return {"message": "Session deleted successfully", "sessionId": session_id}
        
    except Exception as e:
        logger.error("Failed to delete session", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )

# =====================================================
# TEST ENDPOINTS (NO AUTHENTICATION REQUIRED)
# =====================================================

@router.post("/test/sessions/", 
             response_model=CreateSessionResponse,
             summary="Test endpoint - Create session without auth",
             description="Test endpoint for creating sessions without authentication")
async def test_create_session(
    request: CreateSessionRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    """Test endpoint - creates session without authentication."""
    mock_user = UserProfile(id="test_user_123", email="test@example.com")
    
    try:
        session_id = await agent_service.create_session(mock_user, request.metadata)
        
        return CreateSessionResponse(
            sessionId=session_id,
            userId=mock_user.id,
            status="test_active"
        )
        
    except Exception as e:
        logger.error("Test session creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create test session"
        )

@router.post("/test/sessions/{session_id}", 
             response_model=AgentResponse,
             summary="Test endpoint - Send message without auth",
             description="Test endpoint for sending messages without authentication")
async def test_user_query(
    session_id: str,
    request: UserQueryRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    """Test endpoint - processes query without authentication."""
    mock_user = UserProfile(id="test_user_123", email="test@example.com")
    
    try:
        agent_response = await agent_service.process_user_query(
            user_profile=mock_user,
            session_id=session_id,
            user_message=request.userMessage
        )
        
        return AgentResponse(
            agentMessage=agent_response,
            sessionId=session_id,
            metadata={"testMode": True}
        )
        
    except Exception as e:
        logger.error("Test query processing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process test message"
        )

# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def _validate_session_access(session_id: str, user_id: str, agent_service: Optional[AgentService]):
    """Validate that the session exists and belongs to the user."""
    if agent_service:
        exists = await agent_service.session_exists(user_id, session_id)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied"
            )

async def _get_response_metadata(session_id: str, user_id: str, agent_service: AgentService) -> Dict[str, Any]:
    """Get metadata about the agent response."""
    try:
        # Get current session state to determine what happened
        session_state = await agent_service.get_session_state(user_id, session_id)
        
        if session_state:
            return {
                "riskDetected": session_state.get("at_risk", "False") == "True",
                "riskCategories": session_state.get("risk_profile", {}).get("risk_categories", []),
                "agentUsed": _determine_agent_used(session_state),
                "sessionStatus": session_state.get("session_status", "OPEN")
            }
        
        return {"riskDetected": False, "agentUsed": "PersonaAgent"}
        
    except Exception as e:
        logger.warning("Failed to get response metadata", error=str(e))
        return {"error": "metadata_unavailable"}

def _determine_agent_used(session_state: Dict[str, Any]) -> str:
    """Determine which agent was used based on session state."""
    if session_state.get("at_risk", "False") == "True":
        return "ContextCollectionAgent"
    else:
        return "PersonaAgent"