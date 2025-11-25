"""Circuit breaker implementation for external services.

Circuit breakers prevent cascading failures when external services are unavailable.
When a service fails repeatedly, the circuit "opens" and fails fast instead of
waiting for timeouts.

States:
- CLOSED: Normal operation, requests flow through
- OPEN: Service failing, immediately return error (fail fast)
- HALF-OPEN: After cooldown, try one request to check if service recovered

Usage:
    from src.utils.circuit_breaker import openai_breaker, deepgram_breaker

    @openai_breaker
    async def call_openai():
        ...

    # Or use the async wrapper:
    result = await with_circuit_breaker(
        openai_breaker,
        async_function,
        arg1, arg2
    )
"""
import asyncio
import functools
from typing import Callable, TypeVar, Any
from pybreaker import CircuitBreaker, CircuitBreakerError

from src.config.constants import CircuitBreakerConfig
from src.utils.logger import get_logger
from src.utils.metrics import (
    circuit_breaker_state,
    circuit_breaker_trips,
)

logger = get_logger(__name__)

T = TypeVar('T')


# Custom listener to log and track circuit breaker events
class CircuitBreakerListener:
    """Listener for circuit breaker state changes and metrics."""

    def __init__(self, name: str):
        self.name = name

    def state_change(self, cb: CircuitBreaker, old_state: str, new_state: str):
        """Called when the circuit breaker changes state."""
        logger.warning(
            f"Circuit breaker '{self.name}' state changed: {old_state} -> {new_state}"
        )
        circuit_breaker_state.labels(service=self.name).set(
            1 if new_state == "open" else 0
        )
        if new_state == "open":
            circuit_breaker_trips.labels(service=self.name).inc()

    def failure(self, cb: CircuitBreaker, exc: Exception):
        """Called when a call fails."""
        logger.debug(
            f"Circuit breaker '{self.name}' recorded failure: {type(exc).__name__}"
        )

    def success(self, cb: CircuitBreaker):
        """Called when a call succeeds."""
        pass  # Don't log successes to avoid noise


# =============================================================================
# Circuit Breakers for External Services
# =============================================================================

# OpenAI - LLM service for classification/extraction
openai_breaker = CircuitBreaker(
    fail_max=CircuitBreakerConfig.FAIL_MAX,
    reset_timeout=CircuitBreakerConfig.RESET_TIMEOUT_SEC,
    listeners=[CircuitBreakerListener("openai")]
)

# Deepgram - STT and TTS service
deepgram_breaker = CircuitBreaker(
    fail_max=CircuitBreakerConfig.FAIL_MAX,
    reset_timeout=CircuitBreakerConfig.RESET_TIMEOUT_SEC,
    listeners=[CircuitBreakerListener("deepgram")]
)

# USPS - Address validation service
usps_breaker = CircuitBreaker(
    fail_max=CircuitBreakerConfig.FAIL_MAX,
    reset_timeout=CircuitBreakerConfig.RESET_TIMEOUT_SEC,
    listeners=[CircuitBreakerListener("usps")]
)

# SMTP - Email service
smtp_breaker = CircuitBreaker(
    fail_max=CircuitBreakerConfig.FAIL_MAX,
    reset_timeout=CircuitBreakerConfig.RESET_TIMEOUT_SEC,
    listeners=[CircuitBreakerListener("smtp")]
)


# =============================================================================
# Async Decorator Wrapper
# =============================================================================

def async_circuit_breaker(breaker: CircuitBreaker):
    """Decorator to wrap async functions with a circuit breaker.

    Uses pybreaker's built-in call_async method which properly handles
    the circuit breaker state machine.

    Args:
        breaker: The CircuitBreaker instance to use

    Returns:
        Decorated async function

    Example:
        @async_circuit_breaker(openai_breaker)
        async def call_openai():
            return await client.chat.completions.create(...)

    Raises:
        CircuitBreakerError: If the circuit is open
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await breaker.call_async(func, *args, **kwargs)
        return wrapper
    return decorator


async def with_circuit_breaker(
    breaker: CircuitBreaker,
    func: Callable[..., T],
    *args,
    **kwargs
) -> T:
    """Execute an async function with circuit breaker protection.

    This is useful when you can't use the decorator pattern.

    Args:
        breaker: The CircuitBreaker instance to use
        func: The async function to call
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        The result of the function call

    Raises:
        CircuitBreakerError: If the circuit is open

    Example:
        result = await with_circuit_breaker(
            openai_breaker,
            client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[...]
        )
    """
    return await breaker.call_async(func, *args, **kwargs)


def is_circuit_open(breaker: CircuitBreaker) -> bool:
    """Check if a circuit breaker is currently open.

    Args:
        breaker: The CircuitBreaker instance to check

    Returns:
        True if the circuit is open (failing fast), False otherwise
    """
    return breaker.current_state == "open"


def get_circuit_status() -> dict:
    """Get the status of all circuit breakers.

    Returns:
        Dictionary with circuit breaker names and their states
    """
    breakers = {
        "openai": openai_breaker,
        "deepgram": deepgram_breaker,
        "usps": usps_breaker,
        "smtp": smtp_breaker,
    }

    return {
        name: {
            "state": breaker.current_state,
            "fail_count": breaker.fail_counter,
        }
        for name, breaker in breakers.items()
    }

