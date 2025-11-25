"""Health check endpoints with dependency verification."""
import asyncio
from typing import Dict, Any
from datetime import datetime

import aiohttp
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.config.settings import get_settings
from src.config.constants import HealthCheckConfig, APITimeouts
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


async def check_openai_health() -> Dict[str, Any]:
    """Check OpenAI API connectivity."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.get_openai_api_key(),
            timeout=HealthCheckConfig.DEPENDENCY_CHECK_TIMEOUT_SEC
        )

        # Simple models list call to verify connectivity
        await client.models.list()

        return {
            "status": "healthy",
            "message": "OpenAI API accessible",
            "response_time_ms": 0  # Could measure this
        }
    except Exception as e:
        logger.error(f"OpenAI health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"OpenAI API error: {str(e)}",
            "error": type(e).__name__
        }


async def check_deepgram_health() -> Dict[str, Any]:
    """Check Deepgram API connectivity."""
    try:
        # Simple HTTP check to Deepgram API
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=HealthCheckConfig.DEPENDENCY_CHECK_TIMEOUT_SEC
            )
        ) as session:
            headers = {"Authorization": f"Token {settings.get_deepgram_api_key()}"}
            async with session.get(
                "https://api.deepgram.com/v1/projects",
                headers=headers
            ) as response:
                if response.status == 200:
                    return {
                        "status": "healthy",
                        "message": "Deepgram API accessible"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": f"Deepgram API returned {response.status}"
                    }
    except Exception as e:
        logger.error(f"Deepgram health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Deepgram API error: {str(e)}",
            "error": type(e).__name__
        }


async def check_twilio_health() -> Dict[str, Any]:
    """Check Twilio API connectivity."""
    try:
        from twilio.rest import Client

        client = Client(
            settings.twilio_account_sid,
            settings.get_twilio_auth_token()
        )

        # Verify account is accessible
        account = client.api.accounts(settings.twilio_account_sid).fetch()

        return {
            "status": "healthy",
            "message": "Twilio API accessible",
            "account_status": account.status
        }
    except Exception as e:
        logger.error(f"Twilio health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Twilio API error: {str(e)}",
            "error": type(e).__name__
        }


async def check_smtp_health() -> Dict[str, Any]:
    """Check SMTP server connectivity."""
    if not settings.smtp_email or not settings.get_smtp_password():
        return {
            "status": "skipped",
            "message": "SMTP not configured"
        }

    try:
        import smtplib

        # Quick connection test (don't send email)
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=HealthCheckConfig.DEPENDENCY_CHECK_TIMEOUT_SEC
        ) as server:
            server.starttls()
            # Don't login to avoid rate limits, just verify connection

        return {
            "status": "healthy",
            "message": "SMTP server accessible"
        }
    except Exception as e:
        logger.error(f"SMTP health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"SMTP error: {str(e)}",
            "error": type(e).__name__
        }


async def check_usps_health() -> Dict[str, Any]:
    """Check USPS API connectivity."""
    if not settings.usps_user_id:
        return {
            "status": "skipped",
            "message": "USPS API not configured"
        }

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=HealthCheckConfig.DEPENDENCY_CHECK_TIMEOUT_SEC
            )
        ) as session:
            # Simple GET to verify USPS API is reachable
            async with session.get("https://secure.shippingapis.com/ShippingAPI.dll") as response:
                if response.status in [200, 400]:  # 400 is ok, means API is up
                    return {
                        "status": "healthy",
                        "message": "USPS API accessible"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": f"USPS API returned {response.status}"
                    }
    except Exception as e:
        logger.error(f"USPS health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"USPS API error: {str(e)}",
            "error": type(e).__name__
        }


@router.get("/health")
async def health_check():
    """Basic health check - returns 200 if service is running."""
    return {
        "status": "healthy",
        "service": "healthcare-voice-agent",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with dependency verification.

    Returns 200 if all critical dependencies are healthy, 503 otherwise.
    """
    logger.info("Running detailed health check")

    # Run all health checks concurrently
    checks_coros = {
        "openai": check_openai_health(),
        "deepgram": check_deepgram_health(),
        "twilio": check_twilio_health(),
        "smtp": check_smtp_health(),
        "usps": check_usps_health(),
    }

    # Execute all checks with timeout
    try:
        checks = {}
        results = await asyncio.gather(
            *checks_coros.values(),
            return_exceptions=True
        )

        for (name, _), result in zip(checks_coros.items(), results):
            if isinstance(result, Exception):
                checks[name] = {
                    "status": "error",
                    "message": str(result),
                    "error": type(result).__name__
                }
            else:
                checks[name] = result
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    # Determine overall health
    # Critical dependencies: OpenAI, Deepgram, Twilio
    critical_deps = ["openai", "deepgram", "twilio"]
    critical_healthy = all(
        checks.get(dep, {}).get("status") == "healthy"
        for dep in critical_deps
    )

    # Optional dependencies: SMTP, USPS (skipped is ok)
    optional_deps = ["smtp", "usps"]
    optional_healthy = all(
        checks.get(dep, {}).get("status") in ["healthy", "skipped"]
        for dep in optional_deps
    )

    all_healthy = critical_healthy and optional_healthy
    status_code = 200 if all_healthy else 503

    # Get circuit breaker status
    from src.utils.circuit_breaker import get_circuit_status
    circuit_breakers = get_circuit_status()

    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "circuit_breakers": circuit_breakers,
        "summary": {
            "critical_healthy": critical_healthy,
            "optional_healthy": optional_healthy,
            "total_checks": len(checks),
            "healthy_count": sum(1 for c in checks.values() if c.get("status") == "healthy"),
            "unhealthy_count": sum(1 for c in checks.values() if c.get("status") == "unhealthy"),
            "skipped_count": sum(1 for c in checks.values() if c.get("status") == "skipped"),
            "circuit_breakers_open": sum(1 for cb in circuit_breakers.values() if cb.get("state") == "open")
        }
    }

    return JSONResponse(content=response, status_code=status_code)


@router.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe - checks if service is running."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe - checks if service can handle traffic."""
    # Could add more sophisticated checks here
    # For now, just verify critical settings are loaded
    try:
        assert settings.get_openai_api_key(), "OpenAI API key not configured"
        assert settings.get_deepgram_api_key(), "Deepgram API key not configured"
        assert settings.twilio_account_sid, "Twilio account SID not configured"

        return {"status": "ready"}
    except AssertionError as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )
