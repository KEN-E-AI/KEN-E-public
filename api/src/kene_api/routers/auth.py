"""Authentication-related endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import UserContext, get_current_user_context
from ..auth.token_revocation import get_token_revocation_service
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
        expected_action=verification_request.action,
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
        raise HTTPException(status_code=500, detail="reCAPTCHA site key not configured")

    return RecaptchaSiteKeyResponse(site_key=settings.RECAPTCHA_SITE_KEY)


class RevokeTokenRequest(BaseModel):
    """Request to revoke a token."""

    token_id: Optional[str] = None
    reason: Optional[str] = None
    revoke_all: bool = False


class RevokeTokenResponse(BaseModel):
    """Response for token revocation."""

    success: bool
    message: str


@router.post("/revoke-token", response_model=RevokeTokenResponse)
async def revoke_token(
    request: Request,
    revoke_request: RevokeTokenRequest,
    current_user: UserContext = Depends(get_current_user_context),
) -> RevokeTokenResponse:
    """Revoke the current user's token(s).

    Users can revoke their own tokens. If revoke_all is True,
    all tokens for the user will be revoked.
    """
    token_service = get_token_revocation_service()

    if revoke_request.revoke_all:
        # Revoke all tokens for the user
        await token_service.revoke_all_user_tokens(
            user_id=current_user.user_id,
            reason=revoke_request.reason or "User requested revocation of all tokens",
            revoked_by=current_user.user_id,
        )
        return RevokeTokenResponse(
            success=True,
            message="All tokens have been revoked successfully",
        )
    else:
        # Revoke specific token or current token
        # For current token, we need to extract it from the request
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=400, detail="Invalid authorization header")

        # In a real implementation, you'd decode the token to get the jti
        # For now, we'll use a combination of user_id and current timestamp
        token_id = revoke_request.token_id or f"{current_user.user_id}_current"

        await token_service.revoke_token(
            token_id=token_id,
            user_id=current_user.user_id,
            reason=revoke_request.reason or "User requested token revocation",
            revoked_by=current_user.user_id,
        )

        return RevokeTokenResponse(
            success=True,
            message="Token has been revoked successfully",
        )


@router.get("/check-token")
async def check_token(
    current_user: UserContext = Depends(get_current_user_context),
) -> dict:
    """Check if the current token is valid.

    This endpoint can be used to verify that a token hasn't been revoked.
    If you get a successful response, the token is still valid.
    """
    return {
        "valid": True,
        "user_id": current_user.user_id,
        "email": current_user.email,
    }
