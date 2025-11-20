"""State machine for managing conversation flow.

DEPRECATED: This module provides backward compatibility.
New code should use state_manager_factory.get_state_manager() for Redis support.
"""
from src.core.memory_state_manager import InMemoryStateManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Backward compatibility alias
ConversationStateManager = InMemoryStateManager

# Global state manager instance (for backward compatibility)
# New code should use get_state_manager() from state_manager_factory
state_manager = InMemoryStateManager()

logger.debug(
    "Using in-memory state manager via deprecated global instance. "
    "For Redis support, use state_manager_factory.get_state_manager()"
)
