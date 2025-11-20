"""Unit tests for Redis state manager."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from redis.exceptions import RedisError

from src.core.redis_state_manager import RedisStateManager
from src.core.models import ConversationState, ConversationPhase, Insurance


@pytest.mark.unit
class TestRedisStateManager:
    """Test Redis-backed state manager."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.setex = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.keys = AsyncMock(return_value=[])
        return redis_mock

    @pytest.fixture
    def manager(self, mock_redis):
        """Create Redis state manager with mocked Redis."""
        return RedisStateManager(mock_redis, ttl_seconds=600)

    @pytest.mark.asyncio
    async def test_create_state(self, manager, mock_redis, test_call_sid):
        """Test creating state in Redis."""
        state = await manager.create_state(test_call_sid)

        assert state is not None
        assert state.call_sid == test_call_sid
        assert state.phase == ConversationPhase.GREETING

        # Verify Redis setex was called
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert f"voiceagent:state:{test_call_sid}" in call_args[0]
        assert call_args[0][1] == 600  # TTL

    @pytest.mark.asyncio
    async def test_get_state_exists(self, manager, mock_redis, test_call_sid):
        """Test getting existing state from Redis."""
        # Mock Redis to return serialized state
        state = ConversationState(call_sid=test_call_sid)
        mock_redis.get.return_value = state.model_dump_json()

        retrieved = await manager.get_state(test_call_sid)

        assert retrieved is not None
        assert retrieved.call_sid == test_call_sid
        mock_redis.get.assert_called_once_with(f"voiceagent:state:{test_call_sid}")

    @pytest.mark.asyncio
    async def test_get_state_not_exists(self, manager, mock_redis):
        """Test getting non-existent state returns None."""
        mock_redis.get.return_value = None

        state = await manager.get_state("nonexistent")

        assert state is None

    @pytest.mark.asyncio
    async def test_update_state(self, manager, mock_redis, test_call_sid):
        """Test updating state in Redis."""
        # Create initial state
        initial_state = ConversationState(call_sid=test_call_sid)
        mock_redis.get.return_value = initial_state.model_dump_json()

        # Update insurance info
        insurance = Insurance(payer_name="Test Insurance", member_id="123456")
        updated = await manager.update_state(test_call_sid, insurance=insurance)

        assert updated is not None
        assert updated.patient_info.insurance == insurance

        # Verify setex was called to save updated state
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_transition_phase(self, manager, mock_redis, test_call_sid):
        """Test phase transition in Redis."""
        # Create initial state
        initial_state = ConversationState(call_sid=test_call_sid)
        mock_redis.get.return_value = initial_state.model_dump_json()

        # Transition phase
        updated = await manager.transition_phase(
            test_call_sid,
            ConversationPhase.INSURANCE
        )

        assert updated is not None
        assert updated.phase == ConversationPhase.INSURANCE

        # Verify setex was called to save updated state
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_cleanup_state(self, manager, mock_redis, test_call_sid):
        """Test cleaning up state in Redis."""
        await manager.cleanup_state(test_call_sid)

        # Verify delete was called
        mock_redis.delete.assert_called_once_with(f"voiceagent:state:{test_call_sid}")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, manager, mock_redis):
        """Test health check when Redis is healthy."""
        mock_redis.ping.return_value = True

        is_healthy = await manager.health_check()

        assert is_healthy is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, manager, mock_redis):
        """Test health check when Redis is down."""
        mock_redis.ping.side_effect = RedisError("Connection failed")

        is_healthy = await manager.health_check()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_get_active_calls_count(self, manager, mock_redis):
        """Test getting count of active calls."""
        # Mock Redis to return 3 keys
        mock_redis.keys.return_value = [
            b"voiceagent:state:call1",
            b"voiceagent:state:call2",
            b"voiceagent:state:call3"
        ]

        count = await manager.get_active_calls_count()

        assert count == 3
        mock_redis.keys.assert_called_once_with("voiceagent:state:*")

    @pytest.mark.asyncio
    async def test_get_all_call_sids(self, manager, mock_redis):
        """Test getting all active call SIDs."""
        # Mock Redis to return keys
        mock_redis.keys.return_value = [
            b"voiceagent:state:CA123",
            b"voiceagent:state:CA456"
        ]

        call_sids = await manager.get_all_call_sids()

        assert len(call_sids) == 2
        assert "CA123" in call_sids
        assert "CA456" in call_sids

    @pytest.mark.asyncio
    async def test_redis_error_handling(self, manager, mock_redis, test_call_sid):
        """Test error handling when Redis operations fail."""
        # Simulate Redis error
        mock_redis.setex.side_effect = RedisError("Connection lost")

        # Should raise the error
        with pytest.raises(RedisError):
            await manager.create_state(test_call_sid)

    @pytest.mark.asyncio
    async def test_custom_key_prefix(self, mock_redis):
        """Test using custom key prefix."""
        manager = RedisStateManager(
            mock_redis,
            key_prefix="custom:prefix",
            ttl_seconds=300
        )

        await manager.create_state("test_call")

        # Verify custom prefix is used
        call_args = mock_redis.setex.call_args
        assert "custom:prefix:test_call" in call_args[0]

    @pytest.mark.asyncio
    async def test_custom_ttl(self, mock_redis, test_call_sid):
        """Test using custom TTL."""
        manager = RedisStateManager(mock_redis, ttl_seconds=1800)

        await manager.create_state(test_call_sid)

        # Verify custom TTL is used
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 1800

    @pytest.mark.asyncio
    async def test_update_nonexistent_state(self, manager, mock_redis):
        """Test updating non-existent state returns None."""
        mock_redis.get.return_value = None

        result = await manager.update_state("nonexistent", phase=ConversationPhase.INSURANCE)

        assert result is None

    @pytest.mark.asyncio
    async def test_transition_nonexistent_state(self, manager, mock_redis):
        """Test transitioning non-existent state returns None."""
        mock_redis.get.return_value = None

        result = await manager.transition_phase("nonexistent", ConversationPhase.INSURANCE)

        assert result is None
