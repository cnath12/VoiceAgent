"""HTTP client utilities with connection pooling support.

This module provides utilities for making HTTP requests with optional
connection pooling. When running inside a FastAPI request context,
the shared session from app.state can be used for better performance.

For standalone usage (e.g., health checks, tests), a new session
is created automatically.
"""
import aiohttp
from typing import Optional
from contextlib import asynccontextmanager

from src.config.constants import APITimeouts
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Module-level session for fallback (when not in request context)
# This is created lazily and reused across standalone calls
_fallback_session: Optional[aiohttp.ClientSession] = None


async def get_fallback_session() -> aiohttp.ClientSession:
    """Get or create a fallback session for standalone usage.

    This session is used when there's no FastAPI app context available
    (e.g., in health checks, tests, or background tasks).

    Returns:
        A shared aiohttp.ClientSession instance
    """
    global _fallback_session
    if _fallback_session is None or _fallback_session.closed:
        connector = aiohttp.TCPConnector(
            limit=20,              # Smaller pool for fallback
            limit_per_host=10,
            ttl_dns_cache=300,
        )
        _fallback_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=APITimeouts.DEFAULT_TIMEOUT_SEC)
        )
        logger.debug("Created fallback HTTP session")
    return _fallback_session


async def close_fallback_session():
    """Close the fallback session. Call during application shutdown."""
    global _fallback_session
    if _fallback_session and not _fallback_session.closed:
        await _fallback_session.close()
        _fallback_session = None
        logger.debug("Closed fallback HTTP session")


@asynccontextmanager
async def http_request_session(app_state=None) -> aiohttp.ClientSession:
    """Get an HTTP session for making requests.

    If app_state is provided and has an http_session, that shared session is used.
    Otherwise, falls back to the module-level session.

    Args:
        app_state: Optional FastAPI app.state object with http_session attribute

    Yields:
        An aiohttp.ClientSession instance

    Example:
        # With app context (inside a route handler)
        async with http_request_session(request.app.state) as session:
            async with session.get(url) as response:
                data = await response.json()

        # Without app context (standalone)
        async with http_request_session() as session:
            async with session.get(url) as response:
                data = await response.json()
    """
    if app_state and hasattr(app_state, "http_session"):
        # Use the shared session from app.state
        yield app_state.http_session
    else:
        # Use the fallback session
        session = await get_fallback_session()
        yield session

