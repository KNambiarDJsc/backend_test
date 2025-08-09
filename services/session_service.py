from typing import Optional, Dict, Any, List
from uuid import uuid4
import structlog
from supabase import Client
from datetime import datetime

# Try to import ADK components
try:
    from google.adk.sessions import DatabaseSessionService, Session
    ADK_AVAILABLE = True
except ImportError:
    print("ADK sessions not available, using fallback implementation")
    ADK_AVAILABLE = False

from models.api_models import UserProfile
from config.settings import settings

logger = structlog.get_logger(__name__)

class CustomSessionService:
    """Enhanced session service with ADK integration and fallback."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.logger = logger.bind(service="session")
        
        # Try to initialize ADK session service
        if ADK_AVAILABLE:
            self._setup_adk_session_service()
        else:
            self.adk_session_service = None
    
    def _setup_adk_session_service(self):
        """Initialize ADK session service."""
        try:
            # Create database URL from Supabase connection
            # Note: This is a simplified approach - you might need to adjust based on your Supabase setup
            db_url = self._create_database_url()
            
            if db_url:
                self.adk_session_service = DatabaseSessionService(db_url=db_url)
                self.logger.info("ADK DatabaseSessionService initialized")
            else:
                self.logger.warning("Could not create database URL for ADK")
                self.adk_session_service = None
                
        except Exception as e:
            self.logger.error("Failed to initialize ADK session service", error=str(e))
            self.adk_session_service = None
    
    def _create_database_url(self) -> Optional[str]:
        """Create database URL from Supabase settings."""
        try:
            # Extract database connection info from Supabase URL
            # This is a simplified approach - you might need to get actual DB credentials
            # from your Supabase project settings
            
            # For now, return None to use fallback implementation
            # You would need actual PostgreSQL connection details here
            return None
            
        except Exception as e:
            self.logger.error("Error creating database URL", error=str(e))
            return None
    
    async def create_session(
        self, 
        user_profile: UserProfile, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new chat session."""
        try:
            if self.adk_session_service and ADK_AVAILABLE:
                return await self._create_adk_session(user_profile, metadata)
            else:
                return await self._create_manual_session(user_profile, metadata)
                
        except Exception as e:
            self.logger.error("Session creation failed", error=str(e), user_id=user_profile.id)
            # Fallback to manual creation
            return await self._create_manual_session(user_profile, metadata)
    
    async def _create_adk_session(
        self, 
        user_profile: UserProfile, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create session using ADK."""
        try:
            initial_state = self._create_initial_state(user_profile)
            
            session = await self.adk_session_service.create_session(
                app_name=settings.adk_app_name,
                user_id=user_profile.id,
                state=initial_state
            )
            
            self.logger.info("ADK session created", session_id=session.id, user_id=user_profile.id)
            return session.id
            
        except Exception as e:
            self.logger.error("ADK session creation failed", error=str(e))
            raise
    
    async def _create_manual_session(
        self, 
        user_profile: UserProfile, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create session manually without ADK."""
        session_id = str(uuid4())
        
        try:
            # Create session record in Supabase
            session_data = {
                "session_id": session_id,
                "user_id": user_profile.id,
                "app_name": settings.adk_app_name,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table('chat_sessions').insert(session_data).execute()
            
            # Create initial session state
            initial_state = self._create_initial_state(user_profile)
            state_data = {
                "session_id": session_id,
                "user_id": user_profile.id,
                "app_name": settings.adk_app_name,
                "state": initial_state,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table('session_state').insert(state_data).execute()
            
            self.logger.info("Manual session created", session_id=session_id, user_id=user_profile.id)
            return session_id
            
        except Exception as e:
            self.logger.error("Manual session creation failed", error=str(e))
            raise
    
    async def get_session_state(
        self, 
        user_id: str, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve session state."""
        try:
            if self.adk_session_service and ADK_AVAILABLE:
                return await self._get_adk_session_state(user_id, session_id)
            else:
                return await self._get_manual_session_state(user_id, session_id)
                
        except Exception as e:
            self.logger.error("Failed to retrieve session state", error=str(e))
            return None
    
    async def _get_adk_session_state(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state using ADK."""
        try:
            session = await self.adk_session_service.get_session(
                app_name=settings.adk_app_name,
                user_id=user_id,
                session_id=session_id
            )
            return session.state if session else None
            
        except Exception as e:
            self.logger.error("ADK session state retrieval failed", error=str(e))
            return None
    
    async def _get_manual_session_state(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state manually."""
        try:
            response = self.supabase.table('session_state') \
                .select('state') \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .eq('app_name', settings.adk_app_name) \
                .execute()
            
            if response.data:
                return response.data[0]['state']
            return None
            
        except Exception as e:
            self.logger.error("Manual session state retrieval failed", error=str(e))
            return None
    
    async def update_session_state(
        self,
        user_id: str,
        session_id: str,
        state_updates: Dict[str, Any]
    ) -> bool:
        """Update session state."""
        try:
            if self.adk_session_service and ADK_AVAILABLE:
                return await self._update_adk_session_state(user_id, session_id, state_updates)
            else:
                return await self._update_manual_session_state(user_id, session_id, state_updates)
                
        except Exception as e:
            self.logger.error("Failed to update session state", error=str(e))
            return False
    
    async def _update_adk_session_state(
        self, 
        user_id: str, 
        session_id: str, 
        state_updates: Dict[str, Any]
    ) -> bool:
        """Update session state using ADK."""
        try:
            # With ADK, state updates typically happen through events
            # This is a simplified approach
            session = await self.adk_session_service.get_session(
                app_name=settings.adk_app_name,
                user_id=user_id,
                session_id=session_id
            )
            
            if session:
                # Update state (this is simplified - normally done through events)
                session.state.update(state_updates)
                # Note: In real ADK usage, you'd use append_event with state_delta
                self.logger.info("ADK session state updated", session_id=session_id)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error("ADK session state update failed", error=str(e))
            return False
    
    async def _update_manual_session_state(
        self, 
        user_id: str, 
        session_id: str, 
        state_updates: Dict[str, Any]
    ) -> bool:
        """Update session state manually."""
        try:
            # Get current state
            current_state = await self._get_manual_session_state(user_id, session_id)
            if current_state is None:
                current_state = {}
            
            # Merge updates
            current_state.update(state_updates)
            
            # Save updated state
            self.supabase.table('session_state') \
                .update({
                    "state": current_state,
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .eq('app_name', settings.adk_app_name) \
                .execute()
            
            self.logger.info("Manual session state updated", session_id=session_id)
            return True
            
        except Exception as e:
            self.logger.error("Manual session state update failed", error=str(e))
            return False
    
    async def session_exists(self, user_id: str, session_id: str) -> bool:
        """Check if a session exists."""
        try:
            if self.adk_session_service and ADK_AVAILABLE:
                session = await self.adk_session_service.get_session(
                    app_name=settings.adk_app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                return session is not None
            else:
                response = self.supabase.table('chat_sessions') \
                    .select('id') \
                    .eq('session_id', session_id) \
                    .eq('user_id', user_id) \
                    .eq('app_name', settings.adk_app_name) \
                    .execute()
                
                return len(response.data) > 0
                
        except Exception as e:
            self.logger.error("Error checking session existence", error=str(e))
            return False
    
    async def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all sessions for a user."""
        try:
            # For both ADK and manual, we can query the chat_sessions table
            response = self.supabase.table('chat_sessions') \
                .select('session_id, created_at, updated_at, metadata') \
                .eq('user_id', user_id) \
                .eq('app_name', settings.adk_app_name) \
                .order('created_at', desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
            
        except Exception as e:
            self.logger.error("Error retrieving user sessions", error=str(e))
            return []
    
    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a session."""
        try:
            if self.adk_session_service and ADK_AVAILABLE:
                await self.adk_session_service.delete_session(
                    app_name=settings.adk_app_name,
                    user_id=user_id,
                    session_id=session_id
                )
            
            # Also clean up our manual tables
            self.supabase.table('chat_sessions') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.supabase.table('session_state') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.supabase.table('chat_messages') \
                .delete() \
                .eq('session_id', session_id) \
                .eq('user_id', user_id) \
                .execute()
            
            self.logger.info("Session deleted", session_id=session_id, user_id=user_id)
            return True
            
        except Exception as e:
            self.logger.error("Error deleting session", error=str(e))
            return False
    
    def _create_initial_state(self, user_profile: UserProfile) -> Dict[str, Any]:
        """Create initial session state."""
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
            "agent_response": None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for session service."""
        health_status = {
            "session_service": "healthy",
            "adk_available": ADK_AVAILABLE,
            "adk_session_service": "initialized" if self.adk_session_service else "not_available"
        }
        
        # Test Supabase connection
        try:
            self.supabase.table('chat_sessions').select('count').limit(1).execute()
            health_status["supabase"] = "healthy"
        except Exception as e:
            health_status["supabase"] = f"unhealthy: {str(e)}"
        
        return health_status