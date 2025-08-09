# Auth Service
try:
    from .auth_service import AuthService
    AUTH_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import AuthService: {e}")
    AuthService = None
    AUTH_SERVICE_AVAILABLE = False

# Session Service  
try:
    from .session_service import CustomSessionService
    SESSION_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import CustomSessionService: {e}")
    CustomSessionService = None
    SESSION_SERVICE_AVAILABLE = False

# Agent Service - handle more carefully due to ADK dependencies
try:
    from .agent_service import AgentService
    AGENT_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import AgentService: {e}")
    AgentService = None
    AGENT_SERVICE_AVAILABLE = False
except NameError as e:
    print(f"Warning: NameError in AgentService (likely ADK types): {e}")
    AgentService = None
    AGENT_SERVICE_AVAILABLE = False
except Exception as e:
    print(f"Warning: Unexpected error importing AgentService: {e}")
    AgentService = None
    AGENT_SERVICE_AVAILABLE = False

# Export only successfully imported classes
__all__ = []
if AUTH_SERVICE_AVAILABLE and AuthService:
    __all__.append("AuthService")
if SESSION_SERVICE_AVAILABLE and CustomSessionService:
    __all__.append("CustomSessionService")
if AGENT_SERVICE_AVAILABLE and AgentService:
    __all__.append("AgentService")

print(f"Services successfully loaded: {__all__}")

# If no services loaded, that's a problem
if not __all__:
    print("WARNING: No services were successfully imported!")