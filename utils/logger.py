import time
import logging
import sys
from typing import Any, Dict
import structlog
from config.settings import settings

def setup_logging():
    """Configure structured logging for the application."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_format == "json" 
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

class RequestLogger:
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self):
        self.logger = get_logger("request")
    
    async def log_request(self, request, call_next):
        """Log incoming request details."""
        start_time = time.time()
        
        # Log request
        self.logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            client_host=request.client.host if request.client else None
        )
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        self.logger.info(
            "Request completed",
            status_code=response.status_code,
            process_time=round(process_time, 4)
        )
        
        return response
