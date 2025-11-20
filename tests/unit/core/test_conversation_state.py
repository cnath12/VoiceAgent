"""Unit tests for conversation state management."""
import pytest
from src.core.conversation_state import ConversationStateManager
from src.core.models import ConversationPhase, Insurance


@pytest.mark.unit
class TestConversationStateManager:
    """Test conversation state manager."""

    @pytest.mark.asyncio
    async def test_create_state(self, test_call_sid):
        """Test creating a new conversation state."""
        manager = ConversationStateManager()

        state = await manager.create_state(test_call_sid)

        assert state is not None
        assert state.call_sid == test_call_sid
        assert state.phase == ConversationPhase.GREETING
        assert state.error_count == 0

    @pytest.mark.asyncio
    async def test_get_state(self, test_call_sid):
        """Test retrieving a conversation state."""
        manager = ConversationStateManager()

        # Create state first
        await manager.create_state(test_call_sid)

        # Retrieve it
        state = await manager.get_state(test_call_sid)

        assert state is not None
        assert state.call_sid == test_call_sid

    @pytest.mark.asyncio
    async def test_get_nonexistent_state(self):
        """Test retrieving a non-existent state returns None."""
        manager = ConversationStateManager()

        state = await manager.get_state("nonexistent_sid")

        assert state is None

    @pytest.mark.asyncio
    async def test_update_state(self, test_call_sid):
        """Test updating conversation state."""
        manager = ConversationStateManager()

        # Create state
        await manager.create_state(test_call_sid)

        # Update insurance info
        insurance = Insurance(payer_name="Test Insurance", member_id="123456")
        updated = await manager.update_state(test_call_sid, insurance=insurance)

        assert updated is not None
        assert updated.patient_info.insurance == insurance

    @pytest.mark.asyncio
    async def test_transition_phase(self, test_call_sid):
        """Test phase transition."""
        manager = ConversationStateManager()

        # Create state
        await manager.create_state(test_call_sid)

        # Transition to insurance phase
        updated = await manager.transition_phase(
            test_call_sid,
            ConversationPhase.INSURANCE
        )

        assert updated is not None
        assert updated.phase == ConversationPhase.INSURANCE

    @pytest.mark.asyncio
    async def test_cleanup_state(self, test_call_sid):
        """Test cleaning up conversation state."""
        manager = ConversationStateManager()

        # Create state
        await manager.create_state(test_call_sid)
        assert await manager.get_state(test_call_sid) is not None

        # Cleanup
        await manager.cleanup_state(test_call_sid)

        # Should be gone
        assert await manager.get_state(test_call_sid) is None

    @pytest.mark.asyncio
    async def test_get_next_phase(self):
        """Test phase progression logic."""
        manager = ConversationStateManager()

        # Test phase transitions
        assert (
            manager.get_next_phase(ConversationPhase.GREETING)
            == ConversationPhase.INSURANCE
        )
        assert (
            manager.get_next_phase(ConversationPhase.INSURANCE)
            == ConversationPhase.CHIEF_COMPLAINT
        )
        assert (
            manager.get_next_phase(ConversationPhase.CHIEF_COMPLAINT)
            == ConversationPhase.DEMOGRAPHICS
        )
        assert (
            manager.get_next_phase(ConversationPhase.DEMOGRAPHICS)
            == ConversationPhase.CONTACT_INFO
        )
        assert (
            manager.get_next_phase(ConversationPhase.CONTACT_INFO)
            == ConversationPhase.PROVIDER_SELECTION
        )
        assert (
            manager.get_next_phase(ConversationPhase.PROVIDER_SELECTION)
            == ConversationPhase.APPOINTMENT_SCHEDULING
        )
        assert (
            manager.get_next_phase(ConversationPhase.APPOINTMENT_SCHEDULING)
            == ConversationPhase.CONFIRMATION
        )
        assert (
            manager.get_next_phase(ConversationPhase.CONFIRMATION)
            == ConversationPhase.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_concurrent_access(self, test_call_sid):
        """Test thread-safe concurrent access."""
        import asyncio

        manager = ConversationStateManager()
        await manager.create_state(test_call_sid)

        # Simulate concurrent updates
        async def update_error_count(count):
            for _ in range(count):
                state = await manager.get_state(test_call_sid)
                state.error_count += 1
                await manager.update_state(
                    test_call_sid,
                    error_count=state.error_count
                )

        # Run concurrent updates
        await asyncio.gather(
            update_error_count(5),
            update_error_count(5),
            update_error_count(5)
        )

        final_state = await manager.get_state(test_call_sid)
        # Should have 15 total increments
        assert final_state.error_count == 15
