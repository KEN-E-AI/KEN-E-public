"""Authentication-related endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import settings
from ..rate_limiter import recaptcha_rate_limiter
from ..recaptcha import recaptcha_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class RecaptchaVerificationRequest(BaseModel):
    """Request model for reCAPTCHA verification."""

    token: str
    action: str | None = None  # For v3


class RecaptchaVerificationResponse(BaseModel):
    """Response model for reCAPTCHA verification."""

    success: bool
    message: str | None = None
    error_codes: list[str] | None = None


class RecaptchaSiteKeyResponse(BaseModel):
    """Response model for reCAPTCHA site key."""

    site_key: str


@router.post("/verify-recaptcha", response_model=RecaptchaVerificationResponse)
async def verify_recaptcha(
    request: Request, verification_request: RecaptchaVerificationRequest
) -> RecaptchaVerificationResponse:
    """
    Verify a reCAPTCHA token.

    This endpoint should be called before proceeding with authentication
    to ensure the user is not a bot.
    """
    # Apply rate limiting
    recaptcha_rate_limiter.check_rate_limit(request)

    # Get client IP address
    client_ip = request.client.host if request.client else None

    # Verify the token
    result = await recaptcha_service.verify_token(
        verification_request.token,
        remote_ip=client_ip,
        expected_action=verification_request.action
    )

    if result.success:
        return RecaptchaVerificationResponse(
            success=True, message="reCAPTCHA verification successful"
        )
    else:
        # Log the failure with more detail for debugging
        logger.error(
            f"reCAPTCHA verification failed from IP {client_ip}: "
            f"error_codes={result.error_codes}, "
            f"score={result.score}, "
            f"action={result.action}, "
            f"expected_action={verification_request.action}"
        )
        return RecaptchaVerificationResponse(
            success=False,
            message="reCAPTCHA verification failed",
            error_codes=result.error_codes,
        )


@router.get("/recaptcha-site-key", response_model=RecaptchaSiteKeyResponse)
async def get_recaptcha_site_key() -> RecaptchaSiteKeyResponse:
    """
    Get the reCAPTCHA site key for the frontend.

    This endpoint provides the public site key needed to render
    the reCAPTCHA widget on the client side.
    """
    if not settings.RECAPTCHA_SITE_KEY:
        raise HTTPException(
            status_code=500, detail="reCAPTCHA site key not configured"
        )

    return RecaptchaSiteKeyResponse(site_key=settings.RECAPTCHA_SITE_KEY)
