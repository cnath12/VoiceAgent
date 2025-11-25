"""Unit tests for insurance handler."""
import pytest
from unittest.mock import AsyncMock, patch
from src.handlers.insurance_handler import InsuranceHandler
from src.core.models import ConversationState, ConversationPhase, Insurance


@pytest.mark.unit
class TestInsuranceHandler:
    """Test insurance information collection."""

    @pytest.fixture
    def handler(self, test_call_sid):
        """Create an insurance handler."""
        return InsuranceHandler(test_call_sid)

    @pytest.fixture
    async def state(self, test_call_sid):
        """Create a conversation state."""
        state = ConversationState(call_sid=test_call_sid)
        state.phase = ConversationPhase.INSURANCE
        return state

    @pytest.mark.asyncio
    async def test_recognize_common_insurance(self, handler, state):
        """Test recognizing common insurance providers."""
        with patch('src.core.conversation_state.state_manager'):
            response = await handler._handle_payer_name("I have Blue Cross", state)

            assert state.patient_info.insurance is not None
            assert "Blue Cross Blue Shield" in state.patient_info.insurance.payer_name
            assert "member id" in response.lower() or "member id number" in response.lower()

    @pytest.mark.asyncio
    async def test_recognize_insurance_variations(self, handler, state):
        """Test recognizing insurance name variations."""
        with patch('src.core.conversation_state.state_manager'):
            # Test Aetna
            await handler._handle_payer_name("Aetna", state)
            assert state.patient_info.insurance.payer_name == "Aetna"

            # Reset and test United
            state.patient_info.insurance = None
            handler._collection_step = "payer_name"
            await handler._handle_payer_name("United Healthcare", state)
            assert state.patient_info.insurance.payer_name == "United Healthcare"

    @pytest.mark.asyncio
    async def test_extract_member_id(self, handler, state):
        """Test extracting member ID from user input."""
        # Set insurance first
        state.patient_info.insurance = Insurance(
            payer_name="Blue Cross Blue Shield",
            member_id=""
        )

        with patch('src.core.conversation_state.state_manager'):
            response = await handler._handle_member_id("ABC123456", state)

            assert state.patient_info.insurance.member_id == "ABC123456"
            assert "perfect" in response.lower() or "thank you" in response.lower()

    @pytest.mark.asyncio
    async def test_extract_member_id_with_text(self, handler, state):
        """Test extracting member ID from natural language."""
        state.patient_info.insurance = Insurance(
            payer_name="Blue Cross Blue Shield",
            member_id=""
        )

        with patch('src.core.conversation_state.state_manager'):
            response = await handler._handle_member_id(
                "My member ID is ABC 123 456",
                state
            )

            assert state.patient_info.insurance.member_id == "ABC123456"

    @pytest.mark.asyncio
    async def test_retry_logic_payer_name(self, handler, state):
        """Test retry logic for payer name."""
        with patch('src.core.conversation_state.state_manager'):
            # First attempt with unclear response
            handler._retry_count = 0
            response1 = await handler._handle_payer_name("um, I don't know", state)
            assert "insurance provider" in response1.lower() or "insurance" in response1.lower()

            # After max retries, should accept anything
            handler._retry_count = 3
            response2 = await handler._handle_payer_name("SomeInsurance", state)
            assert state.patient_info.insurance is not None
            assert "member id" in response2.lower() or "member id number" in response2.lower()

    @pytest.mark.asyncio
    async def test_complete_insurance_parsing(self, handler, state):
        """Test parsing complete insurance info from one response."""
        with patch('src.core.conversation_state.state_manager'):
            response = await handler._try_parse_complete_insurance(
                "I have Blue Cross insurance and my member ID is ABC123456",
                state
            )

            assert response is not None
            assert state.patient_info.insurance is not None
            assert state.patient_info.insurance.payer_name == "Blue Cross Blue Shield"
            # The member ID might be cleaned (spaces removed)
            assert "ABC" in state.patient_info.insurance.member_id and "123456" in state.patient_info.insurance.member_id

    @pytest.mark.asyncio
    async def test_skip_if_insurance_complete(self, handler, state):
        """Test skipping collection if insurance already complete."""
        # Set complete insurance
        state.patient_info.insurance = Insurance(
            payer_name="Blue Cross Blue Shield",
            member_id="ABC123456"
        )

        with patch('src.core.conversation_state.state_manager'):
            response = await handler.process_input("test", state)

            assert "chief complaint" in response.lower() or "reason" in response.lower()

    @pytest.mark.asyncio
    async def test_llm_fallback(self, handler, state):
        """Test LLM fallback for unrecognized insurance."""
        with patch('src.services.llm_service.LLMService') as MockLLM:
            # Mock LLM response
            mock_llm = MockLLM.return_value
            mock_llm.classify_label = AsyncMock(
                return_value={"payer": "Cigna", "confidence": 0.9}
            )

            with patch('src.core.conversation_state.state_manager'):
                await handler._handle_payer_name("I think it's Cigna", state)

                assert state.patient_info.insurance is not None
                assert state.patient_info.insurance.payer_name == "Cigna"

    @pytest.mark.asyncio
    async def test_reject_meta_comments(self, handler, state):
        """Test rejecting meta comments as insurance provider."""
        with patch('src.core.conversation_state.state_manager'):
            response = await handler._handle_payer_name(
                "why did you stop speaking",
                state
            )

            # Should ask for insurance again, not accept as provider
            assert "insurance provider" in response.lower()
            assert state.patient_info.insurance is None

    @pytest.mark.asyncio
    async def test_member_id_retry_extraction(self, handler, state):
        """Test member ID extraction with retry logic."""
        state.patient_info.insurance = Insurance(
            payer_name="Test Insurance",
            member_id=""
        )

        with patch('src.core.conversation_state.state_manager'):
            # Test extracting from complex input
            response = await handler._handle_member_id(
                "it's in my wallet, let me see, um, ABC 123 456",
                state
            )

            # The member ID should be extracted and cleaned (spaces removed)
            member_id = state.patient_info.insurance.member_id
            assert "ABC" in member_id and "123" in member_id and "456" in member_id
