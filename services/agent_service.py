# services/agent_service.py - Updated with Custom Runner Integration
from typing import List, Dict, Any, Optional
import structlog
from supabase import Client
import uuid
import asyncio

# Try to import ADK components with proper error handling
try:
    from google.adk.runners import Runner
    from google.adk.sessions import DatabaseSessionService
    from google.genai import types
    from google.adk.events import Event
    ADK_AVAILABLE = True
except ImportError as e:
    print(f"ADK not available: {e}")
    # Create dummy classes for fallback
    class Event:
        pass
    class Runner:
        pass
    class DatabaseSessionService:
        pass
    ADK_AVAILABLE = False

from models.api_models import UserProfile
from config.settings import settings

logger = structlog.get_logger(__name__)

class AgentService:
    """Service for handling AI agent interactions using ADK with custom runner."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.logger = logger.bind(service="agent")
        self.custom_runner = None
        
        if ADK_AVAILABLE:
            self._setup_custom_runner()
        else:
            self.logger.warning("ADK not available, using fallback implementation")
    
    def _setup_custom_runner(self):
        """Initialize custom runner with Supabase integration."""
        try:
            # Import custom runner
            from runner.custom_runner import CustomAgentRunner
            from chat_agent.agent import root_agent
            
            self.custom_runner = CustomAgentRunner(
                agent=root_agent,
                supabase_client=self.supabase,
                app_name=settings.adk_app_name
            )
            self.logger.info("Custom runner initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to setup custom runner", error=str(e))
            self.custom_runner = None
    
    async def create_session(self, user_profile: UserProfile, metadata: Dict[str, Any] = None) -> str:
        """Create a new chat session using custom runner."""
        session_id = str(uuid.uuid4())
        
        try:
            if self.custom_runner:
                # Use custom runner's session service
                session_id = await self.custom_runner.session_service.create_session(
                    user_id=user_profile.id,
                    session_id=session_id,
                    initial_state=self._create_initial_state(user_profile)
                )
                self.logger.info("Session created with custom runner", 
                               session_id=session_id, 
                               user_id=user_profile.id)
            else:
                # Fallback to manual session creation
                session_id = await self._create_manual_session(user_profile, metadata, session_id)
            
            return session_id
            
        except Exception as e:
            self.logger.error("Session creation failed", error=str(e), user_id=user_profile.id)
            # Return session ID anyway for testing
            return session_id
    
    async def process_user_query(
        self,
        user_profile: UserProfile,
        session_id: str,
        user_message: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Process user query using custom runner or fallback."""
        try:
            if self.custom_runner:
                # Use custom runner for full agent pipeline
                response = await self.custom_runner.run_conversation(
                    user_id=user_profile.id,
                    session_id=session_id,
                    user_message=user_message,
                    message_metadata=metadata
                )
                
                self.logger.info("Message processed with custom runner", 
                               session_id=session_id,
                               user_id=user_profile.id,
                               response_length=len(response))
                return response
            else:
                # Fallback processing
                return await self._process_with_fallback(user_profile, session_id, user_message)
            
        except Exception as e:
            self.logger.error("Failed to process user query", error=str(e))
            return "I apologize, but I'm having trouble processing your message right now. Please try again."

    async def get_session_state(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current session state."""
        try:
            if self.custom_runner:
                return await self.custom_runner.session_service.get_session(user_id, session_id)
            else:
                # Fallback: get from Supabase directly
                result = self.supabase.table('chat_sessions') \
                    .select('state') \
                    .eq('id', session_id) \
                    .eq('user_id', user_id) \
                    .execute()
                
                if result.data:
                    return result.data[0]['state']
                return None
                
        except Exception as e:
            self.logger.error("Failed to get session state", error=str(e))
            return None

    async def session_exists(self, user_id: str, session_id: str) -> bool:
        """Check if session exists and belongs to user."""
        try:
            if self.custom_runner:
                session = await self.custom_runner.session_service.get_session(user_id, session_id)
                return session is not None
            else:
                # Fallback: check Supabase directly
                result = self.supabase.table('chat_sessions') \
                    .select('id') \
                    .eq('id', session_id) \
                    .eq('user_id', user_id) \
                    .execute()
                
                return len(result.data) > 0
                
        except Exception as e:
            self.logger.error("Error checking session existence", error=str(e))
            return False

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete session and all associated data."""
        try:
            if self.custom_runner:
                return await self.custom_runner.session_service.delete_session(user_id, session_id)
            else:
                # Fallback: manual deletion
                return await self._delete_manual_session(user_id, session_id)
                
        except Exception as e:
            self.logger.error("Failed to delete session", error=str(e))
            return False

    async def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all sessions for a user."""
        try:
            result = self.supabase.table('chat_sessions') \
                .select('id, created_at, updated_at, metadata') \
                .eq('user_id', user_id) \
                .eq('app_name', settings.adk_app_name) \
                .order('created_at', desc=True) \
                .limit(limit) \
                .execute()
            
            return result.data
            
        except Exception as e:
            self.logger.error("Error retrieving user sessions", error=str(e))
            return []

    # =====================================================
    # FALLBACK METHODS (when ADK/custom runner unavailable)
    # =====================================================

    async def _create_manual_session(self, user_profile: UserProfile, metadata: Dict[str, Any], session_id: str) -> str:
        """Fallback session creation without custom runner."""
        try:
            session_data = {
                "id": session_id,
                "user_id": user_profile.id,
                "app_name": settings.adk_app_name,
                "metadata": metadata or {},
                "state": self._create_initial_state(user_profile),
                "created_at": "now()",
                "updated_at": "now()"
            }
            
            result = self.supabase.table('chat_sessions').insert(session_data).execute()
            
            if result.data:
                self.logger.info("Manual session created", session_id=session_id)
                return session_id
            else:
                raise Exception("Failed to create session in database")
                
        except Exception as e:
            self.logger.error("Manual session creation failed", error=str(e))
            raise

    async def _process_with_fallback(self, user_profile: UserProfile, session_id: str, user_message: str) -> str:
        """Fallback message processing without custom runner."""
        try:
            # Store user message
            await self._store_message(session_id, user_profile.id, "user", user_message)
            
            # Simple rule-based response
            message_lower = user_message.lower()
            
            # Risk detection
            risk_keywords = ["hurt myself", "harm myself", "suicide", "kill myself", "want to die"]
            if any(keyword in message_lower for keyword in risk_keywords):
                await self._create_risk_alert(user_profile, session_id, user_message, "Suicidality")
                response = ("Thank you for sharing that with me. That sounds like a lot to hold onto, and it's really important. "
                           "I want you to know that you're not alone. Please reach out to a trusted adult or call 988 if you need immediate help.")
            # Basic responses
            elif any(greeting in message_lower for greeting in ["hello", "hi", "hey"]):
                response = "Hello! I'm here to support you. How are you feeling today?"
            elif any(feeling in message_lower for feeling in ["sad", "down", "upset", "depressed"]):
                response = "I hear that you're feeling down. That must be difficult. Can you tell me more about what's been going on?"
            elif any(word in message_lower for word in ["anxious", "worried", "stress"]):
                response = "It sounds like you're feeling anxious or stressed. That can be really overwhelming. What's been on your mind lately?"
            else:
                response = "Thank you for sharing that with me. I'm here to listen and support you. Can you tell me more about how you're feeling?"
            
            # Store agent response
            await self._store_message(session_id, user_profile.id, "assistant", response)
            
            # Update session state
            await self._update_session_state(session_id, user_profile.id, {
                "last_message": response,
                "updated_at": "now()"
            })
            
            return response
            
        except Exception as e:
            self.logger.error("Fallback processing failed", error=str(e))
            return "I'm here to help you. Can you tell me more about what you're experiencing?"

    async def _delete_manual_session(self, user_id: str, session_id: str) -> bool:
        """Manual session deletion."""
        try:
            # Delete related data first
            self.supabase.table('chat_messages') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.supabase.table('session_states') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.supabase.table('transformed_messages') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.supabase.table('risk_alerts') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            # Delete session
            result = self.supabase.table('chat_sessions') \
                .delete() \
                .eq('id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.logger.info("Manual session deleted", session_id=session_id, user_id=user_id)
            return True
            
        except Exception as e:
            self.logger.error("Manual session deletion failed", error=str(e))
            return False

    # =====================================================
    # HELPER METHODS
    # =====================================================

    async def _store_message(self, session_id: str, user_id: str, role: str, content: str):
        """Store message in Supabase."""
        try:
            message_data = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "created_at": "now()"
            }
            
            self.supabase.table('chat_messages').insert(message_data).execute()
            self.logger.debug("Message stored", session_id=session_id, role=role)
            
        except Exception as e:
            self.logger.error("Failed to store message", error=str(e))

    async def _update_session_state(self, session_id: str, user_id: str, updates: Dict[str, Any]):
        """Update session state in Supabase."""
        try:
            self.supabase.table('chat_sessions') \
                .update(updates) \
                .eq('id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.logger.debug("Session state updated", session_id=session_id)
            
        except Exception as e:
            self.logger.error("Failed to update session state", error=str(e))

    async def _create_risk_alert(self, user_profile: UserProfile, session_id: str, triggering_statement: str, risk_category: str):
        """Create risk alert in database."""
        try:
            alert_data = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_profile.id,
                "triggering_statement": triggering_statement,
                "risk_categories": [risk_category],
                "verdict": "UNCONFIRMED",
                "created_at": "now()",
                "updated_at": "now()"
            }
            
            self.supabase.table('risk_alerts').insert(alert_data).execute()
            self.logger.info("Risk alert created", session_id=session_id, category=risk_category)
            
        except Exception as e:
            self.logger.error("Failed to create risk alert", error=str(e))

    def _create_initial_state(self, user_profile: UserProfile) -> Dict[str, Any]:
        """Create initial ADK session state."""
        return {
            "user_profile": {
                "name": user_profile.email or "User",
                "grade": "Unknown",
                "at_risk": False
            },
            "at_risk": "False",
            "risk_profile": {
                "status": "NO_RISK",
                "active_category": None,
                "triggering_statement": "",
                "assessment_history": [],
                "risk_categories": [],
                "verdict": "CLEARED"
            },
            "context_collection": {
                "current_turn": 0,
                "confidence_score": 0.0
            },
            "active_category_risk_factors": {},
            "found_risk_factors": {},
            "session_status": "OPEN",
            "persona_agent_response": "",
            "recent_memory_queue": [],
            "agent_response": ""
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for agent service."""
        health_status = {
            "agent_service": "healthy",
            "adk_available": ADK_AVAILABLE,
            "custom_runner": "initialized" if self.custom_runner else "not_available",
            "supabase": "healthy"
        }
        
        try:
            self.supabase.table('chat_sessions').select('count').limit(1).execute()
        except Exception as e:
            health_status["supabase"] = f"unhealthy: {str(e)}"
            
        return health_status