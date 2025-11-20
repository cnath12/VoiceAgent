"""Redis-backed implementation of conversation state manager."""
from typing import Optional
import json
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.models import ConversationState, ConversationPhase
from src.core.state_manager_base import StateManagerBase
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RedisStateManager(StateManagerBase):
    """Redis-backed implementation of conversation state manager.

    Provides:
    - Persistent state across restarts
    - Horizontal scaling (multiple instances share state)
    - High availability with Redis clustering
    - Automatic TTL for state cleanup

    State is stored as JSON in Redis with keys: `voiceagent:state:{call_sid}`
    """

    def __init__(
        self,
        redis_client: Redis,
        key_prefix: str = "voiceagent:state",
        ttl_seconds: int = 3600  # 1 hour default TTL
    ):
        """Initialize Redis state manager.

        Args:
            redis_client: Async Redis client instance
            key_prefix: Prefix for Redis keys
            ttl_seconds: Time-to-live for state entries (default: 1 hour)
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds

    def _get_key(self, call_sid: str) -> str:
        """Generate Redis key for a call SID.

        Args:
            call_sid: Twilio call SID

        Returns:
            Redis key string
        """
        return f"{self.key_prefix}:{call_sid}"

    async def create_state(self, call_sid: str) -> ConversationState:
        """Create new conversation state in Redis."""
        try:
            state = ConversationState(call_sid=call_sid)

            # Serialize to JSON
            state_json = state.model_dump_json()

            # Store in Redis with TTL
            key = self._get_key(call_sid)
            await self.redis.setex(
                key,
                self.ttl_seconds,
                state_json
            )

            logger.info(
                "Created conversation state in Redis",
                extra={
                    "call_sid": call_sid,
                    "ttl_seconds": self.ttl_seconds
                }
            )

            return state

        except RedisError as e:
            logger.error(
                f"Redis error creating state for {call_sid}: {e}",
                exc_info=True
            )
            raise

    async def get_state(self, call_sid: str) -> Optional[ConversationState]:
        """Get conversation state from Redis."""
        try:
            key = self._get_key(call_sid)
            state_json = await self.redis.get(key)

            if not state_json:
                return None

            # Deserialize from JSON
            state = ConversationState.model_validate_json(state_json)

            return state

        except RedisError as e:
            logger.error(
                f"Redis error getting state for {call_sid}: {e}",
                exc_info=True
            )
            return None
        except Exception as e:
            logger.error(
                f"Error deserializing state for {call_sid}: {e}",
                exc_info=True
            )
            return None

    async def update_state(
        self,
        call_sid: str,
        **kwargs
    ) -> Optional[ConversationState]:
        """Update conversation state in Redis."""
        try:
            # Get current state
            state = await self.get_state(call_sid)

            if not state:
                logger.warning(f"Cannot update non-existent state for {call_sid}")
                return None

            # Update fields
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
                elif hasattr(state.patient_info, key):
                    setattr(state.patient_info, key, value)

            # Serialize and save back to Redis
            state_json = state.model_dump_json()
            redis_key = self._get_key(call_sid)

            await self.redis.setex(
                redis_key,
                self.ttl_seconds,
                state_json
            )

            logger.info(
                f"Updated state in Redis for {call_sid}",
                extra={"updated_fields": list(kwargs.keys())}
            )

            return state

        except RedisError as e:
            logger.error(
                f"Redis error updating state for {call_sid}: {e}",
                exc_info=True
            )
            return None

    async def transition_phase(
        self,
        call_sid: str,
        new_phase: ConversationPhase
    ) -> Optional[ConversationState]:
        """Transition to new conversation phase in Redis."""
        try:
            state = await self.get_state(call_sid)

            if not state:
                logger.warning(
                    f"Cannot transition phase for non-existent state: {call_sid}"
                )
                return None

            old_phase = state.phase
            state.phase = new_phase

            # Save updated state
            state_json = state.model_dump_json()
            redis_key = self._get_key(call_sid)

            await self.redis.setex(
                redis_key,
                self.ttl_seconds,
                state_json
            )

            logger.info(
                f"Transitioned {call_sid} from {old_phase} to {new_phase}"
            )

            return state

        except RedisError as e:
            logger.error(
                f"Redis error transitioning phase for {call_sid}: {e}",
                exc_info=True
            )
            return None

    async def cleanup_state(self, call_sid: str) -> None:
        """Remove conversation state from Redis."""
        try:
            key = self._get_key(call_sid)
            await self.redis.delete(key)

            logger.info(f"Cleaned up state in Redis for {call_sid}")

        except RedisError as e:
            logger.error(
                f"Redis error cleaning up state for {call_sid}: {e}",
                exc_info=True
            )

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if Redis is reachable and operational, False otherwise
        """
        try:
            await self.redis.ping()
            return True
        except RedisError:
            return False

    async def get_active_calls_count(self) -> int:
        """Get count of active calls in Redis.

        Returns:
            Number of active conversation states
        """
        try:
            pattern = f"{self.key_prefix}:*"
            keys = await self.redis.keys(pattern)
            return len(keys)
        except RedisError as e:
            logger.error(f"Redis error counting active calls: {e}")
            return 0

    async def get_all_call_sids(self) -> list[str]:
        """Get all active call SIDs from Redis.

        Returns:
            List of call SIDs with active states
        """
        try:
            pattern = f"{self.key_prefix}:*"
            keys = await self.redis.keys(pattern)

            # Extract call SIDs from keys
            prefix_len = len(self.key_prefix) + 1
            call_sids = [key.decode('utf-8')[prefix_len:] for key in keys]

            return call_sids

        except RedisError as e:
            logger.error(f"Redis error getting call SIDs: {e}")
            return []
