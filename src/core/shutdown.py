"""Graceful shutdown handler for VoiceAgent.

Ensures clean termination of ongoing calls and proper cleanup of resources
when the application receives shutdown signals (SIGTERM, SIGINT).
"""
import asyncio
import signal
from typing import Set, Optional

from pipecat.pipeline.runner import PipelineRunner

from src.core.conversation_state import state_manager
from src.utils.logger import get_logger
from src.utils.metrics import active_calls

logger = get_logger(__name__)

# Global state for shutdown coordination
_shutdown_event: Optional[asyncio.Event] = None
_active_runners: Set[PipelineRunner] = set()
_shutdown_timeout_seconds = 30  # Maximum time to wait for graceful shutdown


def init_shutdown_handler():
    """Initialize the shutdown event and signal handlers.

    Should be called during application startup (in lifespan context).
    """
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    logger.info("Graceful shutdown handler initialized (SIGTERM, SIGINT)")


def _handle_shutdown_signal(signum, frame):
    """Signal handler for SIGTERM and SIGINT.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    signal_name = signal.Signals(signum).name
    logger.warning(f"Received {signal_name} signal - initiating graceful shutdown")

    if _shutdown_event:
        _shutdown_event.set()


async def shutdown():
    """Perform graceful shutdown of the application.

    Shutdown sequence:
    1. Stop accepting new calls
    2. Wait for active calls to complete (with timeout)
    3. Stop all pipeline runners
    4. Cleanup conversation state
    5. Close external connections

    Returns after shutdown is complete or timeout is reached.
    """
    logger.info("Starting graceful shutdown sequence...")

    # Step 1: Log current active calls
    current_active = active_calls._value._value
    logger.info(f"Active calls at shutdown: {current_active}")

    # Step 2: Wait for active calls to complete (with timeout)
    if current_active > 0:
        logger.info(f"Waiting up to {_shutdown_timeout_seconds}s for {current_active} active calls to complete...")

        wait_start = asyncio.get_event_loop().time()
        while active_calls._value._value > 0:
            elapsed = asyncio.get_event_loop().time() - wait_start
            if elapsed >= _shutdown_timeout_seconds:
                remaining = active_calls._value._value
                logger.warning(f"Shutdown timeout reached - {remaining} calls still active, forcing shutdown")
                break

            # Check every 500ms
            await asyncio.sleep(0.5)
            remaining = active_calls._value._value
            if remaining > 0:
                logger.debug(f"Waiting for {remaining} active calls... ({elapsed:.1f}s elapsed)")

        final_active = active_calls._value._value
        if final_active == 0:
            logger.info("All active calls completed successfully")
        else:
            logger.warning(f"Shutdown proceeding with {final_active} active calls")

    # Step 3: Stop all pipeline runners
    if _active_runners:
        logger.info(f"Stopping {len(_active_runners)} pipeline runners...")
        for runner in list(_active_runners):
            try:
                stop = getattr(runner, "stop", None)
                if callable(stop):
                    await stop()
                logger.debug(f"Pipeline runner stopped: {id(runner)}")
            except Exception as e:
                logger.error(f"Error stopping pipeline runner {id(runner)}: {e}")
        _active_runners.clear()
        logger.info("All pipeline runners stopped")

    # Step 4: Cleanup conversation state
    try:
        # If state manager has cleanup method, call it
        cleanup = getattr(state_manager, "cleanup_all", None)
        if callable(cleanup):
            await cleanup()
            logger.info("Conversation state cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up conversation state: {e}")

    # Step 5: Close external connections (if any)
    # Redis connections, HTTP sessions, etc. will be cleaned up automatically
    # by their respective context managers

    logger.info("Graceful shutdown complete")


def register_runner(runner: PipelineRunner):
    """Register a pipeline runner for shutdown tracking.

    Args:
        runner: PipelineRunner instance to track
    """
    _active_runners.add(runner)
    logger.debug(f"Registered pipeline runner for shutdown: {id(runner)}")


def unregister_runner(runner: PipelineRunner):
    """Unregister a pipeline runner after it completes.

    Args:
        runner: PipelineRunner instance to unregister
    """
    _active_runners.discard(runner)
    logger.debug(f"Unregistered pipeline runner: {id(runner)}")


def is_shutting_down() -> bool:
    """Check if the application is currently shutting down.

    Returns:
        True if shutdown has been initiated, False otherwise
    """
    return _shutdown_event is not None and _shutdown_event.is_set()


async def wait_for_shutdown():
    """Wait for shutdown signal.

    This can be used in background tasks that should run until shutdown.

    Example:
        ```python
        async def background_task():
            while not is_shutting_down():
                # Do work
                await asyncio.sleep(1)
        ```
    """
    if _shutdown_event:
        await _shutdown_event.wait()
