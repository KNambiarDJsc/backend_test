from typing import List, Dict, Any
import structlog
from supabase import Client
import uuid

# Try to import ADK components
try:
    from google.adk.agents import Runner
    from google.adk.sessions import DatabaseSessionService
    from google.genai import types
    from google.adk.events import Event
    ADK_AVAILABLE = True
except ImportError as e:
    print(f"ADK not available: {e}")
    ADK_AVAILABLE = False

from models.api_models import UserProfile
from config.settings import settings

logger = structlog.get_logger(__name__)

class AgentService:
    """Service for handling AI agent interactions using ADK."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.logger = logger.bind(service="agent")
        self.runner = None
        
        if ADK_AVAILABLE:
            self._setup_adk_components()
        else:
            self.logger.warning("ADK not available, using fallback implementation")
    
    def _setup_adk_components(self):
        """Initialize ADK components."""
        try:
            from chat_agent.agent import root_agent
            
            db_url = f"postgresql://{settings.supabase_key}@{settings.supabase_url.replace('https://', '').replace('http://', '')}"
            self.session_service = DatabaseSessionService(db_url=db_url)
            
            self.runner = Runner(
                agent=root_agent,
                app_name=settings.adk_app_name,
                session_service=self.session_service
            )
            self.logger.info("ADK components initialized successfully")
        except Exception as e:
            self.logger.error("Failed to setup ADK components", error=str(e))
            self.runner = None
    
    async def create_session(self, user_profile: UserProfile, metadata: Dict[str, Any] = None) -> str:
        """Create a new chat session, preferring ADK and falling back to manual."""
        if self.runner and ADK_AVAILABLE:
            try:
                session = await self.session_service.create_session(
                    app_name=settings.adk_app_name,
                    user_id=user_profile.id,
                    state=self._create_initial_state(user_profile)
                )
                self.logger.info("ADK session created", session_id=session.id, user_id=user_profile.id)
                return session.id
            except Exception as e:
                self.logger.error(
                    "ADK session creation failed, falling back to manual.",
                    error=str(e), user_id=user_profile.id
                )
        
        # Fallback if ADK is unavailable or its session creation fails
        return await self._create_manual_session(user_profile, metadata)
    
    async def process_user_query(
        self,
        user_profile: UserProfile,
        session_id: str,
        user_message: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Process user query using the appropriate method (ADK or fallback)."""
        # Determine which processing function to use
        processor = self._process_with_adk if self.runner and ADK_AVAILABLE else self._process_with_fallback
        
        try:
            return await processor(user_profile, session_id, user_message)
        except Exception as e:
            self.logger.error("Failed to process user query", error=str(e), processor=processor.__name__)
            return "I apologize, but I'm having trouble processing your message right now. Please try again."

    async def _process_with_adk(self, user_profile: UserProfile, session_id: str, user_message: str) -> str:
        """Process message using ADK Runner."""
        try:
            user_content = types.Content(role="user", parts=[types.Part(text=user_message)])
            
            response_events: List[Event] = []
            async for event in self.runner.run_async(
                user_id=user_profile.id,
                session_id=session_id,
                new_message=user_content
            ):
                response_events.append(event)
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    self.logger.debug("Final response event received", session_id=session_id)
            
            final_response = self._extract_final_response(response_events)
            if not final_response:
                final_response = "I'm here to help. Can you tell me more about what you're experiencing?"
            
            self.logger.info("ADK processing completed", 
                              user_id=user_profile.id, 
                              session_id=session_id,
                              response_length=len(final_response))
            return final_response
        except Exception as e:
            self.logger.error("ADK processing failed", error=str(e))
            raise

    def _extract_final_response(self, events: List[Event]) -> str:
        """Extract the final agent response from ADK events."""
        final_response_text = ""
        for event in reversed(events):
            try:
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    if hasattr(event, 'content') and event.content:
                        parts = getattr(event.content, 'parts', [])
                        text_parts = [part.text for part in parts if hasattr(part, 'text') and part.text]
                        if text_parts:
                            final_response_text = "".join(text_parts)
                            break
            except Exception as e:
                self.logger.debug("Error extracting text from event", error=str(e))
                continue
        return final_response_text.strip() if final_response_text else ""

    def _create_initial_state(self, user_profile: UserProfile) -> Dict[str, Any]:
        """Create initial ADK session state."""
        return {
            "user_profile": {"name": user_profile.email or "User", "grade": "Unknown", "at_risk": False},
            "at_risk": "False",
            "risk_profile": {
                "status": "NO_RISK", "active_category": None, "triggering_statement": "",
                "assessment_history": [], "risk_categories": [], "verdict": "CLEARED"
            }
        }

    # Fallback methods
    async def _create_manual_session(self, user_profile: UserProfile, metadata: Dict[str, Any] = None) -> str:
        """Fallback session creation without ADK."""
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id, "user_id": user_profile.id, "app_name": settings.adk_app_name,
            "metadata": metadata or {}, "created_at": "now()", "updated_at": "now()"
        }
        try:
            self.supabase.table('chat_sessions').insert(session_data).execute()
            self.logger.info("Manual session created", session_id=session_id)
        except Exception as e:
            self.logger.warning("Could not create session in database", error=str(e))
        return session_id

    async def _process_with_fallback(self, user_profile: UserProfile, session_id: str, user_message: str) -> str:
        """Fallback message processing without ADK."""
        message_lower = user_message.lower()
        risk_keywords = ["hurt myself", "harm myself", "suicide", "kill myself"]
        if any(keyword in message_lower for keyword in risk_keywords):
            await self._create_risk_alert(user_profile, session_id, user_message, "Suicidality")
            return ("Thank you for sharing that with me. That sounds like a lot to hold onto, and it's really important. "
                    "I want you to know that you're not alone. Please reach out to a trusted adult or call 988 if you need immediate help.")
        
        if any(greeting in message_lower for greeting in ["hello", "hi", "hey"]):
            return "Hello! I'm here to support you. How are you feeling today?"
        elif any(feeling in message_lower for feeling in ["sad", "down", "upset"]):
            return "I hear that you're feeling down. That must be difficult. Can you tell me more about what's been going on?"
        else:
            return "Thank you for sharing that with me. I'm here to listen and support you. Can you tell me more about how you're feeling?"

    async def _create_risk_alert(self, user_profile: UserProfile, session_id: str, triggering_statement: str, risk_category: str):
        """Create risk alert in database."""
        alert_data = {
            "session_id": session_id, "user_id": user_profile.id, "triggering_statement": triggering_statement,
            "risk_categories": [risk_category], "verdict": "UNCONFIRMED",
            "created_at": "now()", "updated_at": "now()"
        }
        try:
            self.supabase.table('risk_alerts').insert(alert_data).execute()
            self.logger.info("Risk alert created", session_id=session_id, category=risk_category)
        except Exception as e:
            self.logger.error("Failed to create risk alert", error=str(e))

    async def health_check(self) -> Dict[str, Any]:
        """Health check for agent service."""
        health_status = {
            "agent_service": "healthy",
            "adk_available": ADK_AVAILABLE,
            "adk_runner": "initialized" if self.runner else "not_available",
            "supabase": "healthy"
        }
        try:
            self.supabase.table('chat_sessions').select('count').limit(1).execute()
        except Exception as e:
            health_status["supabase"] = f"unhealthy: {str(e)}"
        return health_status