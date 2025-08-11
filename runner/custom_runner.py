from typing import Optional, Dict, Any, AsyncGenerator
import structlog
from supabase import Client

try:
    from google.adk.agents import Runner, Agent
    from google.adk.sessions import SessionService, Session
    from google.adk.events import Event
    from google.genai import types
    ADK_AVAILABLE = True
except ImportError:
    # Fallback classes
    class Runner:
        pass
    class SessionService:
        pass
    class Session:
        pass
    class Event:
        pass
    ADK_AVAILABLE = False

from callbacks.supabase_callbacks import SupabaseCallbackManager

logger = structlog.get_logger(__name__)

class CustomSupabaseSessionService:
    """Custom session service that uses Supabase for persistence."""
    
    def __init__(self, supabase_client: Client, app_name: str):
        self.supabase = supabase_client
        self.app_name = app_name
        self.logger = logger.bind(component="custom_session_service")
    
    async def create_session(self, user_id: str, session_id: Optional[str] = None, initial_state: Optional[Dict[str, Any]] = None) -> str:
        """Create a new session in Supabase."""
        import uuid
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            session_data = {
                "id": session_id,
                "user_id": user_id,
                "app_name": self.app_name,
                "state": initial_state or {},
                "created_at": "now()",
                "updated_at": "now()"
            }
            
            result = self.supabase.table('chat_sessions').insert(session_data).execute()
            
            if result.data:
                self.logger.info("Session created", session_id=session_id, user_id=user_id)
                return session_id
            else:
                raise Exception("Failed to create session in database")
                
        except Exception as e:
            self.logger.error("Failed to create session", error=str(e))
            raise
    
    async def get_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from Supabase."""
        try:
            result = self.supabase.table('chat_sessions').select('*').eq('id', session_id).eq('user_id', user_id).eq('app_name', self.app_name).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error("Failed to get session", error=str(e))
            return None
    
    async def update_session_state(self, user_id: str, session_id: str, state: Dict[str, Any]) -> bool:
        """Update session state in Supabase."""
        try:
            result = self.supabase.table('chat_sessions').update({
                "state": state,
                "updated_at": "now()"
            }).eq('id', session_id).eq('user_id', user_id).eq('app_name', self.app_name).execute()
            
            if result.data:
                self.logger.debug("Session state updated", session_id=session_id)
                return True
            return False
            
        except Exception as e:
            self.logger.error("Failed to update session state", error=str(e))
            return False
    
    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete session from Supabase."""
        try:
            # Delete related messages first
            self.supabase.table('chat_messages').delete().eq('session_id', session_id).eq('user_id', user_id).execute()
            
            # Delete session state
            self.supabase.table('session_states').delete().eq('session_id', session_id).eq('user_id', user_id).execute()
            
            # Delete session
            result = self.supabase.table('chat_sessions').delete().eq('id', session_id).eq('user_id', user_id).eq('app_name', self.app_name).execute()
            
            self.logger.info("Session deleted", session_id=session_id, user_id=user_id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to delete session", error=str(e))
            return False

class CustomAgentRunner:
    """Custom runner that integrates with Supabase callbacks."""
    
    def __init__(self, 
                 agent: Any,  # Agent type
                 supabase_client: Client,
                 app_name: str):
        self.agent = agent
        self.supabase = supabase_client
        self.app_name = app_name
        self.session_service = CustomSupabaseSessionService(supabase_client, app_name)
        self.callback_manager = SupabaseCallbackManager(supabase_client)
        self.logger = logger.bind(component="custom_agent_runner")
        
        # Initialize ADK runner if available
        if ADK_AVAILABLE:
            try:
                self.adk_runner = Runner(
                    agent=agent,
                    app_name=app_name,
                    session_service=None  # We'll handle sessions manually
                )
            except Exception as e:
                self.logger.warning("Failed to initialize ADK runner", error=str(e))
                self.adk_runner = None
        else:
            self.adk_runner = None
    
    async def run_conversation(self,
                             user_id: str,
                             session_id: str,
                             user_message: str,
                             message_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Run a conversation turn with full Supabase integration."""
        try:
            # Get or create session
            session_data = await self.session_service.get_session(user_id, session_id)
            if not session_data:
                # Create new session with initial state
                initial_state = self._create_initial_state(user_id)
                await self.session_service.create_session(user_id, session_id, initial_state)
                session_data = await self.session_service.get_session(user_id, session_id)
            
            # Create callback context
            callback_context = self._create_callback_context(user_id, session_id, session_data['state'], user_message)
            
            # Run before agent callback
            await self.callback_manager.before_agent_call(callback_context)
            
            # Process message with agent
            agent_response = await self._process_with_agent(callback_context, user_message)
            
            # Run after agent callback
            await self.callback_manager.after_agent_response(callback_context, agent_response)
            
            # Update session state
            await self.session_service.update_session_state(user_id, session_id, callback_context.state)
            
            return agent_response
            
        except Exception as e:
            self.logger.error("Conversation run failed", error=str(e))
            return "I apologize, but I'm having trouble processing your message right now. Please try again."
    
    async def _process_with_agent(self, callback_context, user_message: str) -> str:
        """Process message with the agent."""
        try:
            if self.adk_runner and ADK_AVAILABLE:
                return await self._process_with_adk(callback_context, user_message)
            else:
                return await self._process_with_fallback(callback_context, user_message)
                
        except Exception as e:
            self.logger.error("Agent processing failed", error=str(e))
            return await self._process_with_fallback(callback_context, user_message)
    
    async def _process_with_adk(self, callback_context, user_message: str) -> str:
        """Process with ADK agent."""
        try:
            user_content = types.Content(role="user", parts=[types.Part(text=user_message)])
            
            # This is a simplified approach - in reality you'd need to properly integrate
            # the ADK runner with your custom session service
            
            # For now, use the agent directly if possible
            if hasattr(self.agent, 'run_async'):
                response_events = []
                async for event in self.agent.run_async(callback_context):
                    response_events.append(event)
                
                return self._extract_final_response(response_events)
            else:
                return await self._process_with_fallback(callback_context, user_message)
                
        except Exception as e:
            self.logger.error("ADK processing failed", error=str(e))
            return await self._process_with_fallback(callback_context, user_message)
    
    async def _process_with_fallback(self, callback_context, user_message: str) -> str:
        """Fallback processing without ADK."""
        message_lower = user_message.lower()
        
        # Risk detection
        risk_keywords = ["hurt myself", "harm myself", "suicide", "kill myself", "want to die"]
        if any(keyword in message_lower for keyword in risk_keywords):
            callback_context.state["at_risk"] = "True"
            callback_context.state["risk_profile"] = {
                "triggering_statement": user_message,
                "risk_categories": ["Suicidality"],
                "verdict": "UNCONFIRMED"
            }
            return ("Thank you for sharing that with me. That sounds like a lot to hold onto, and it's really important. "
                    "I want you to know that you're not alone. Please reach out to a trusted adult or call 988 if you need immediate help.")
        
        # Basic responses
        if any(greeting in message_lower for greeting in ["hello", "hi", "hey"]):
            return "Hello! I'm here to support you. How are you feeling today?"
        elif any(feeling in message_lower for feeling in ["sad", "down", "upset", "depressed"]):
            return "I hear that you're feeling down. That must be difficult. Can you tell me more about what's been going on?"
        elif any(word in message_lower for word in ["anxious", "worried", "stress"]):
            return "It sounds like you're feeling anxious or stressed. That can be really overwhelming. What's been on your mind lately?"
        else:
            return "Thank you for sharing that with me. I'm here to listen and support you. Can you tell me more about how you're feeling?"
    
    def _extract_final_response(self, events) -> str:
        """Extract final response from events."""
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
            except Exception:
                continue
        return final_response_text.strip() if final_response_text else "I'm here to help you."
    
    def _create_callback_context(self, user_id: str, session_id: str, state: Dict[str, Any], user_message: str):
        """Create callback context for agent processing."""
        try:
            if ADK_AVAILABLE:
                from google.adk.agents.callback_context import CallbackContext
                context = CallbackContext()
                context.session_id = session_id
                context.user_id = user_id
                context.state = state
                context.user_content = types.Content(role="user", parts=[types.Part(text=user_message)])
                return context
            else:
                # Fallback context
                class FallbackContext:
                    def __init__(self):
                        self.session_id = session_id
                        self.user_id = user_id
                        self.state = state
                        self.user_content = None
                
                return FallbackContext()
                
        except Exception as e:
            self.logger.error("Failed to create callback context", error=str(e))
            # Return minimal context
            class MinimalContext:
                def __init__(self):
                    self.session_id = session_id
                    self.user_id = user_id
                    self.state = state
                    self.user_content = None
            
            return MinimalContext()
    
    def _create_initial_state(self, user_id: str) -> Dict[str, Any]:
        """Create initial session state."""
        return {
            "user_profile": {
                "name": "User",
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
            "agent_response": None,
            "session_status": "OPEN"
        }