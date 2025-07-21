"""Google reCAPTCHA verification service."""

import logging

import httpx
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class RecaptchaVerificationResult(BaseModel):
    """Result of reCAPTCHA verification."""

    success: bool
    challenge_ts: str | None = None
    hostname: str | None = None
    error_codes: list[str] | None = None
    score: float | None = None  # For reCAPTCHA v3
    action: str | None = None  # For reCAPTCHA v3


class RecaptchaService:
    """Service for verifying Google reCAPTCHA tokens."""

    def __init__(self):
        self.secret_key = settings.RECAPTCHA_SECRET_KEY
        if not self.secret_key:
            logger.warning("RECAPTCHA_SECRET_KEY not configured")

    def _validate_v3_response(
        self, result: RecaptchaVerificationResult,
        expected_action: str | None,
        min_score: float
    ) -> RecaptchaVerificationResult:
        """
        Validate reCAPTCHA v3 specific requirements (score and action).
        
        Args:
            result: The verification result from Google
            expected_action: Expected action string
            min_score: Minimum acceptable score
            
        Returns:
            Updated verification result
        """
        # Check if score meets minimum threshold
        if result.score < min_score:
            logger.warning(f"reCAPTCHA v3 score too low: {result.score} < {min_score}")
            return RecaptchaVerificationResult(
                success=False,
                score=result.score,
                action=result.action,
                error_codes=["score-too-low"]
            )

        # Check if action matches expected action
        if expected_action and result.action != expected_action:
            logger.warning(f"reCAPTCHA v3 action mismatch: expected {expected_action}, got {result.action}")
            return RecaptchaVerificationResult(
                success=False,
                score=result.score,
                action=result.action,
                error_codes=["action-mismatch"]
            )

        return result

    async def verify_token(
        self, token: str, remote_ip: str | None = None, expected_action: str | None = None,
        min_score: float = 0.5
    ) -> RecaptchaVerificationResult:
        """
        Verify a reCAPTCHA token with Google's API.

        Args:
            token: The reCAPTCHA token from the client
            remote_ip: Optional IP address of the user
            expected_action: Expected action for v3 (e.g., 'signin', 'signup')
            min_score: Minimum score threshold for v3 (0.0 to 1.0)

        Returns:
            RecaptchaVerificationResult with verification status
        """
        if not self.secret_key:
            logger.error("Cannot verify reCAPTCHA: secret key not configured")
            return RecaptchaVerificationResult(
                success=False, error_codes=["missing-secret-key"]
            )

        if not token:
            return RecaptchaVerificationResult(
                success=False, error_codes=["missing-input-response"]
            )

        logger.info(f"Verifying reCAPTCHA token for action: {expected_action}, IP: {remote_ip}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                data = {
                    "secret": self.secret_key,
                    "response": token,
                }
                if remote_ip:
                    data["remoteip"] = remote_ip

                response = await client.post(RECAPTCHA_VERIFY_URL, data=data)
                response.raise_for_status()

                result_data = response.json()
                logger.info(f"reCAPTCHA API response: {result_data}")

                # Convert error-codes to error_codes for Pydantic model
                if "error-codes" in result_data:
                    result_data["error_codes"] = result_data.pop("error-codes")
                result = RecaptchaVerificationResult(**result_data)

                if not result.success:
                    logger.warning(
                        f"reCAPTCHA verification failed: {result.error_codes}"
                    )
                    return result

                # For reCAPTCHA v3, validate score and action
                if result.score is not None:
                    logger.info(f"reCAPTCHA v3 score: {result.score}, action: {result.action}")
                    return self._validate_v3_response(result, expected_action, min_score)

                return result

        except httpx.TimeoutException:
            logger.error("reCAPTCHA verification timeout")
            return RecaptchaVerificationResult(
                success=False, error_codes=["timeout-error"]
            )
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during reCAPTCHA verification: {e}")
            return RecaptchaVerificationResult(
                success=False, error_codes=["http-error"]
            )
        except Exception as e:
            logger.error(f"Unexpected error during reCAPTCHA verification: {e}")
            return RecaptchaVerificationResult(
                success=False, error_codes=["internal-error"]
            )


# Global instance
recaptcha_service = RecaptchaService()
