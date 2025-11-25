"""Factory for creating appropriate state manager based on configuration."""
from typing import Optional
from redis.asyncio import Redis

from src.config.settings import get_settings
from src.core.state_manager_base import StateManagerBase
from src.core.memory_state_manager import InMemoryStateManager
from src.core.redis_state_manager import RedisStateManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StateManagerFactory:
    """Factory for creating state managers based on configuration."""

    _instance: Optional[StateManagerBase] = None
    _redis_client: Optional[Redis] = None

    @classmethod
    async def create_state_manager(cls) -> StateManagerBase:
        """Create and return a state manager based on configuration.

        Returns:
            StateManagerBase instance (either InMemoryStateManager or RedisStateManager)
        """
        if cls._instance is not None:
            return cls._instance

        settings = get_settings()

        if settings.use_redis:
            logger.info("Initializing Redis-backed state manager")
            cls._instance = await cls._create_redis_manager(settings)
        else:
            logger.info("Initializing in-memory state manager")
            cls._instance = InMemoryStateManager()

        return cls._instance

    @classmethod
    async def _create_redis_manager(cls, settings) -> RedisStateManager:
        """Create Redis state manager with connection.

        Args:
            settings: Application settings

        Returns:
            RedisStateManager instance

        Raises:
            ConnectionError: If Redis connection fails
        """
        try:
            # Use redis_url if provided, otherwise build from components
            if settings.redis_url:
                redis_client = Redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=False  # We handle JSON encoding/decoding
                )
            else:
                redis_password = settings.get_redis_password()
                redis_client = Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=redis_password if redis_password else None,
                    ssl=settings.redis_ssl,
                    encoding="utf-8",
                    decode_responses=False
                )

            # Test connection
            await redis_client.ping()
            logger.info(
                "Redis connection established",
                extra={
                    "host": settings.redis_host,
                    "port": settings.redis_port,
                    "db": settings.redis_db
                }
            )

            cls._redis_client = redis_client
            return RedisStateManager(redis_client)

        except Exception as e:
            logger.error(
                f"Failed to connect to Redis: {e}. Falling back to in-memory state manager.",
                exc_info=True
            )
            # Fallback to in-memory if Redis fails
            return InMemoryStateManager()

    @classmethod
    async def close(cls) -> None:
        """Close Redis connection if open."""
        if cls._redis_client:
            await cls._redis_client.close()
            logger.info("Redis connection closed")
            cls._redis_client = None
        cls._instance = None

    @classmethod
    def get_instance(cls) -> Optional[StateManagerBase]:
        """Get the current state manager instance without creating a new one.

        Returns:
            Current state manager instance or None if not initialized
        """
        return cls._instance


async def get_state_manager() -> StateManagerBase:
    """Get or create the global state manager instance.

    This is the main entry point for accessing the state manager.

    Returns:
        StateManagerBase instance
    """
    return await StateManagerFactory.create_state_manager()
