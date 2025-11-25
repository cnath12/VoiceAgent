"""LLM service wrapper for conversation management."""
from typing import List, Dict, Optional
import json

from openai import AsyncOpenAI
from pybreaker import CircuitBreakerError

from src.config.settings import get_settings
from src.config.prompts import SYSTEM_PROMPT, PHASE_PROMPTS, ERROR_PROMPTS
from src.utils.logger import get_logger
from src.utils.circuit_breaker import openai_breaker, with_circuit_breaker

logger = get_logger(__name__)
settings = get_settings()


class LLMService:
    """Wrapper for OpenAI LLM with healthcare-specific prompting.

    Uses circuit breaker pattern to fail fast when OpenAI is unavailable,
    preventing cascading failures and resource exhaustion.
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.get_openai_api_key())
        self.model = "gpt-3.5-turbo"

    async def _call_openai(self, messages: List[Dict], parse_json: bool = False, **kwargs) -> str | Dict:
        """Make an OpenAI API call with circuit breaker protection.

        Args:
            messages: List of message dictionaries for the chat completion
            parse_json: If True, parse the response as JSON and return a dict
            **kwargs: Additional arguments to pass to the API

        Returns:
            The generated text response (str) or parsed JSON (dict)

        Raises:
            CircuitBreakerError: If the circuit is open (OpenAI is failing)
        """
        response = await with_circuit_breaker(
            openai_breaker,
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
            **kwargs
        )
        content = response.choices[0].message.content or ""

        if parse_json:
            return json.loads(content)
        return content
        
    async def generate_response(
        self,
        user_input: str,
        conversation_state: dict,
        phase: str,
        context: Optional[List[Dict]] = None
    ) -> str:
        """Generate contextual response based on conversation state.

        Uses circuit breaker to fail fast if OpenAI is unavailable.
        """
        try:
            # Build system prompt with current context
            system_content = SYSTEM_PROMPT.format(
                phase=phase,
                patient_info=json.dumps(conversation_state, indent=2)
            )

            messages = [{"role": "system", "content": system_content}]

            # Add conversation context if provided
            if context:
                messages.extend(context[-6:])  # Last 3 exchanges

            # Add current user input
            messages.append({"role": "user", "content": user_input})

            # Add phase-specific guidance
            if phase in PHASE_PROMPTS:
                messages.append({
                    "role": "system",
                    "content": f"Guide the conversation towards: {PHASE_PROMPTS[phase]}"
                })

            # Generate response with circuit breaker protection
            return await self._call_openai(
                messages,
                temperature=0.7,
                max_tokens=150,
                presence_penalty=0.3,
                frequency_penalty=0.3
            )

        except CircuitBreakerError:
            logger.warning("OpenAI circuit breaker is open - returning fallback response")
            return ERROR_PROMPTS["system_error"]
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return ERROR_PROMPTS["system_error"]
    
    async def extract_information(
        self,
        user_input: str,
        extraction_type: str
    ) -> Optional[Dict]:
        """Extract structured information from user input.

        Uses circuit breaker to fail fast if OpenAI is unavailable.
        """
        extraction_prompts = {
            "insurance": """Extract insurance information from the user input.
                Return JSON with: {"payer_name": "...", "member_id": "..."}
                If information is missing, use null.""",

            "address": """Extract address components from the user input.
                Return JSON with: {"street": "...", "city": "...", "state": "...", "zip": "..."}
                State should be 2-letter code. If information is missing, use null.""",

            "contact": """Extract contact information from the user input.
                Return JSON with: {"phone": "...", "email": "..."}
                Phone should be 10 digits. If information is missing, use null."""
        }

        if extraction_type not in extraction_prompts:
            return None

        try:
            return await self._call_openai(
                messages=[
                    {"role": "system", "content": extraction_prompts[extraction_type]},
                    {"role": "user", "content": user_input}
                ],
                parse_json=True,
                temperature=0.1,
                max_tokens=100,
                response_format={"type": "json_object"}
            )
        except CircuitBreakerError:
            logger.warning("OpenAI circuit breaker open - extraction failed")
            return None
        except Exception as e:
            logger.error(f"Information extraction error: {e}")
            return None

    async def classify_label(self, user_input: str, labels: List[str]) -> Optional[Dict]:
        """Classify user_input into one of the provided labels.

        Uses circuit breaker to fail fast if OpenAI is unavailable.

        Returns:
            A dict: {"payer": str, "confidence": float} or None on error.
        """
        try:
            if not labels:
                return None
            system = (
                "You are a strict classifier. Given a user input, choose the single best matching label "
                "from the provided list. If none is appropriate, return 'unknown' with low confidence. "
                "Return JSON only with keys: payer (string) and confidence (0.0-1.0)."
            )
            content = (
                "Labels:\n" + "\n".join(f"- {l}" for l in labels) + "\n\n"
                f"User input: {user_input}"
            )
            data = await self._call_openai(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                parse_json=True,
                temperature=0.0,
                max_tokens=60,
                response_format={"type": "json_object"},
            )
            payer = str(data.get("payer", "unknown"))
            try:
                confidence = float(data.get("confidence", 0.0))
            except Exception:
                confidence = 0.0
            return {"payer": payer, "confidence": confidence}
        except CircuitBreakerError:
            logger.warning("OpenAI circuit breaker open - classification failed")
            return None
        except Exception as e:
            logger.error(f"LLM classify error: {e}")
            return None

    async def classify_choice(self, user_input: str, labels: List[str]) -> Optional[Dict]:
        """Generic classifier to pick one label from a provided list.

        Uses circuit breaker to fail fast if OpenAI is unavailable.

        Returns:
            {"label": str, "confidence": float} or None on error.
        """
        try:
            if not labels:
                return None
            system = (
                "You are a strict classifier. Choose the single best matching label from the list. "
                "If none fit, return 'unknown' with confidence 0.0. Respond ONLY in JSON with keys: "
                "label (string) and confidence (0.0-1.0)."
            )
            content = (
                "Labels:\n" + "\n".join(f"- {l}" for l in labels) + "\n\n"
                f"User input: {user_input}"
            )
            data = await self._call_openai(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                parse_json=True,
                temperature=0.0,
                max_tokens=60,
                response_format={"type": "json_object"},
            )
            label = str(data.get("label", "unknown"))
            try:
                confidence = float(data.get("confidence", 0.0))
            except Exception:
                confidence = 0.0
            return {"label": label, "confidence": confidence}
        except CircuitBreakerError:
            logger.warning("OpenAI circuit breaker open - classify_choice failed")
            return None
        except Exception as e:
            logger.error(f"LLM classify_choice error: {e}")
            return None