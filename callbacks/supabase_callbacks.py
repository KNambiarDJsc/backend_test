from typing import Dict, Any, Optional
import structlog
from supabase import Client
import uuid
from datetime import datetime

try:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.events import Event
    ADK_AVAILABLE = True
except ImportError:
    # Fallback classes for when ADK is not available
    class CallbackContext:
        def __init__(self):
            self.state = {}
            self.user_content = None
            self.session_id = None
            self.user_id = None
    ADK_AVAILABLE = False

logger = structlog.get_logger(__name__)

class SupabaseStateCallback:
    """Callback for storing session state into Supabase."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.logger = logger.bind(component="supabase_state_callback")
    
    async def store_state(self, callback_context: CallbackContext):
        """Store session state into Supabase."""
        try:
            session_id = getattr(callback_context, 'session_id', None)
            user_id = getattr(callback_context, 'user_id', None)
            
            if not session_id or not user_id:
                self.logger.warning("Missing session_id or user_id in callback context")
                return
            
            state_data = {
                "session_id": session_id,
                "user_id": user_id,
                "state": dict(callback_context.state),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Upsert state (update if exists, insert if not)
            result = self.supabase.table('session_states').upsert(
                state_data,
                on_conflict="session_id,user_id"
            ).execute()
            
            if result.data:
                self.logger.info("State stored successfully", session_id=session_id)
            else:
                self.logger.warning("No data returned from state storage", session_id=session_id)
                
        except Exception as e:
            self.logger.error("Failed to store state", error=str(e))

class SupabaseMessageCallback:
    """Callback for storing transformed messages into Supabase."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.logger = logger.bind(component="supabase_message_callback")
    
    async def store_transformed_message(self, 
                                      session_id: str,
                                      user_id: str,
                                      original_message: str,
                                      transformed_message: str,
                                      transformation_type: str = "agent_response",
                                      metadata: Optional[Dict[str, Any]] = None):
        """Store transformed messages into Supabase."""
        try:
            message_data = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "original_content": original_message,
                "transformed_content": transformed_message,
                "transformation_type": transformation_type,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table('transformed_messages').insert(message_data).execute()
            
            if result.data:
                self.logger.info("Transformed message stored successfully", 
                               session_id=session_id, 
                               transformation_type=transformation_type)
            else:
                self.logger.warning("No data returned from message storage", session_id=session_id)
                
        except Exception as e:
            self.logger.error("Failed to store transformed message", error=str(e))
    
    async def store_conversation_turn(self,
                                    callback_context: CallbackContext,
                                    agent_response: str):
        """Store a complete conversation turn (user + agent response)."""
        try:
            session_id = getattr(callback_context, 'session_id', None)
            user_id = getattr(callback_context, 'user_id', None)
            
            if not session_id or not user_id:
                self.logger.warning("Missing session_id or user_id in callback context")
                return
            
            # Extract user message
            user_message = ""
            if hasattr(callback_context, 'user_content') and callback_context.user_content:
                if hasattr(callback_context.user_content, 'parts'):
                    user_message = " ".join([
                        part.text for part in callback_context.user_content.parts 
                        if hasattr(part, 'text')
                    ])
            
            # Store user message
            await self._store_single_message(session_id, user_id, "user", user_message)
            
            # Store agent response
            await self._store_single_message(session_id, user_id, "assistant", agent_response)
            
            # Store the transformation
            await self.store_transformed_message(
                session_id=session_id,
                user_id=user_id,
                original_message=user_message,
                transformed_message=agent_response,
                transformation_type="conversation_turn",
                metadata={
                    "risk_status": callback_context.state.get("at_risk", "False"),
                    "user_profile": callback_context.state.get("user_profile", {})
                }
            )
            
        except Exception as e:
            self.logger.error("Failed to store conversation turn", error=str(e))
    
    async def _store_single_message(self, session_id: str, user_id: str, role: str, content: str):
        """Store a single message in the chat_messages table."""
        try:
            message_data = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table('chat_messages').insert(message_data).execute()
            
        except Exception as e:
            self.logger.error("Failed to store single message", error=str(e))

class SupabaseCallbackManager:
    """Manager for all Supabase callbacks."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.state_callback = SupabaseStateCallback(supabase_client)
        self.message_callback = SupabaseMessageCallback(supabase_client)
        self.logger = logger.bind(component="supabase_callback_manager")
    
    async def after_agent_response(self, callback_context: CallbackContext, agent_response: str):
        """Combined callback that runs after agent response."""
        try:
            # Store state
            await self.state_callback.store_state(callback_context)
            
            # Store conversation turn
            await self.message_callback.store_conversation_turn(callback_context, agent_response)
            
            self.logger.info("All callbacks completed successfully")
            
        except Exception as e:
            self.logger.error("Error in combined callback", error=str(e))
    
    async def before_agent_call(self, callback_context: CallbackContext):
        """Callback that runs before agent call."""
        try:
            # Load any necessary state or perform pre-processing
            session_id = getattr(callback_context, 'session_id', None)
            user_id = getattr(callback_context, 'user_id', None)
            
            if session_id and user_id:
                # Load existing state from Supabase
                existing_state = await self._load_existing_state(session_id, user_id)
                if existing_state:
                    callback_context.state.update(existing_state)
                    self.logger.info("Loaded existing state", session_id=session_id)
            
        except Exception as e:
            self.logger.error("Error in before_agent_call callback", error=str(e))
    
    async def _load_existing_state(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Load existing state from Supabase."""
        try:
            result = self.supabase.table('session_states').select('state').eq('session_id', session_id).eq('user_id', user_id).execute()
            
            if result.data:
                return result.data[0]['state']
            return None
            
        except Exception as e:
            self.logger.error("Failed to load existing state", error=str(e))
            return None