"""Logging configuration for the application."""
import logging
import sys
from pathlib import Path
from src.config.settings import get_settings

settings = get_settings()

# Create logs directory
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Set level
        logger.setLevel(getattr(logging, settings.log_level))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # File handler only in development
        file_handler = None
        if settings.app_env.lower() == "development":
            file_handler = logging.FileHandler(log_dir / "voice_agent.log")
            file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        if file_handler:
            file_handler.setFormatter(formatter)
        
        # Add handlers
        logger.addHandler(console_handler)
        if file_handler:
            logger.addHandler(file_handler)
    
    return logger