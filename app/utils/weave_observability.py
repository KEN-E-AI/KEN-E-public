"""Weights & Biases (Weave) observability wrapper for agent tracing and cost tracking."""

import hashlib
import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

try:
    import weave

    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False
    weave = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_WEAVE_INITIALIZED = False
_WEAVE_INIT_LOCK = threading.Lock()


def init_weave_if_needed(*, required: bool = False) -> bool:
    """Initialize W&B Weave if not already initialized and API key is available.

    Idempotent and thread-safe — safe to call multiple times from any thread.

    Args:
        required: When True, raise RuntimeError instead of returning False.
            Use this for agent entry points where Weave observability is
            mandatory.

    Returns:
        True if Weave is initialized and ready, False otherwise.

    Raises:
        RuntimeError: If ``required=True`` and initialization fails.
    """
    global _WEAVE_INITIALIZED
    # Fast path: already initialized — no lock needed
    if _WEAVE_INITIALIZED:
        return WEAVE_AVAILABLE

    with _WEAVE_INIT_LOCK:
        # Double-check after acquiring lock
        if _WEAVE_INITIALIZED:
            return WEAVE_AVAILABLE

        return _init_weave_locked(required=required)


def _init_weave_locked(*, required: bool) -> bool:
    """Inner initialization logic, called while holding ``_WEAVE_INIT_LOCK``."""
    global _WEAVE_INITIALIZED

    if not WEAVE_AVAILABLE:
        _WEAVE_INITIALIZED = True
        msg = "Weave package not installed — tracing cannot be enabled"
        if required:
            raise RuntimeError(msg)
        logger.warning(msg)
        return False

    wandb_api_key: str | None = None
    try:
        from shared.secrets import get_env_or_secret

        wandb_api_key = get_env_or_secret("WANDB_API_KEY")
    except Exception as e:
        logger.warning(f"Failed to retrieve WANDB_API_KEY via secrets: {e}")

    if not wandb_api_key:
        # On Agent Engine, module-level load_dotenv() from ken_e_agent.py
        # doesn't re-execute after deserialization. Load .env here so
        # WANDB_API_KEY is available when called from runtime callbacks.
        try:
            from pathlib import Path

            from dotenv import load_dotenv

            # On Agent Engine: /code/app/utils/weave_observability.py
            # .env lives at /code/.env and /code/agents/.env
            code_root = Path(__file__).resolve().parent.parent.parent
            for candidate in (
                code_root / "agents" / ".env",
                code_root / ".env",
            ):
                if candidate.exists():
                    load_dotenv(candidate, override=False)
                    break
        except ImportError:
            pass
        wandb_api_key = os.getenv("WANDB_API_KEY")

    if not wandb_api_key:
        # Don't mark as permanently initialized — retry on next call
        # in case .env becomes available after a redeploy.
        msg = "WANDB_API_KEY not available — Weave tracing cannot be enabled"
        if required:
            raise RuntimeError(msg)
        logger.warning(msg)
        return False

    os.environ["WANDB_API_KEY"] = wandb_api_key

    try:
        project_name = os.getenv("WEAVE_PROJECT_NAME", "ken-e-dev")
        weave.init(project_name=project_name)
        logger.info(f"Weave initialized (project: {project_name})")
        _WEAVE_INITIALIZED = True
        return True
    except Exception as e:
        msg = f"Failed to initialize Weave: {e}"
        if required:
            raise RuntimeError(msg) from e
        logger.warning(msg)
        return False


def safe_weave_op(
    name: str | None = None,
) -> Callable:
    """Conditional ``@weave.op()`` decorator.

    Returns a no-op decorator when Weave is unavailable so the wrapped
    function can always be called normally.

    Args:
        name: Optional operation name passed to ``weave.op()``.
    """
    if WEAVE_AVAILABLE and weave is not None:
        return weave.op(name=name) if name else weave.op()

    def _identity(fn: Callable) -> Callable:
        return fn

    return _identity


def setup_weave_tracing(
    project_name: str | None = None,
    entity: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """Initialize Weave with authentication and project configuration.

    Args:
        project_name: W&B project name (defaults to WANDB_PROJECT env var)
        entity: W&B entity/team name (defaults to WANDB_ENTITY env var)
        api_key: W&B API key (defaults to WANDB_API_KEY env var)

    Returns:
        Project name if initialized successfully, None otherwise.
    """
    if not WEAVE_AVAILABLE:
        logger.warning("Weave/W&B not installed. Run: pip install weave wandb")
        return None

    api_key = api_key or os.getenv("WANDB_API_KEY")
    if not api_key:
        logger.warning("WANDB_API_KEY not set, W&B tracing disabled")
        return None

    os.environ["WANDB_API_KEY"] = api_key

    project = project_name or os.getenv("WANDB_PROJECT", "quickstart_playground")
    entity = entity or os.getenv("WANDB_ENTITY")

    try:
        full_project = f"{entity}/{project}" if entity else project
        weave.init(project_name=full_project)
        logger.info(f"Weave tracing initialized for project: {full_project}")
        return full_project
    except Exception as e:
        logger.error(f"Failed to initialize Weave: {e}")
        return None


def sanitize_sensitive_data(
    data: Any, keys_to_sanitize: list[str] | None = None
) -> Any:
    """Sanitize sensitive data before logging to W&B.

    Args:
        data: Data to sanitize
        keys_to_sanitize: List of keys to sanitize (defaults to common sensitive keys)

    Returns:
        Sanitized data
    """
    if keys_to_sanitize is None:
        keys_to_sanitize = [
            "password",
            "secret",
            "token",
            "api_key",
            "credentials",
            "auth",
            "authorization",
            "cookie",
            "session",
            "private",
        ]

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if any(term in key.lower() for term in keys_to_sanitize):
                if value:
                    hash_val = hashlib.sha256(str(value).encode()).hexdigest()[:8]
                    sanitized[key] = f"[REDACTED-{hash_val}]"
                else:
                    sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_sensitive_data(value, keys_to_sanitize)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_sensitive_data(item, keys_to_sanitize) for item in data]
    elif isinstance(data, str):
        if "@" in data and "." in data:
            parts = data.split("@")
            if len(parts) == 2:
                return f"{parts[0][:2]}***@{parts[1]}"
        return data
    else:
        return data


def track_agent_operation(
    agent_name: str, operation: str, sanitize: bool = True
) -> Callable:
    """Decorator to track agent operations with Weave.

    Args:
        agent_name: Name of the agent
        operation: Operation being performed
        sanitize: Whether to sanitize sensitive data

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        if not WEAVE_AVAILABLE or not weave:
            return func

        @wraps(func)
        @weave.op()
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if sanitize:
                safe_kwargs = sanitize_sensitive_data(kwargs)
            else:
                safe_kwargs = kwargs

            weave.log(
                {"agent": agent_name, "operation": operation, "inputs": safe_kwargs}
            )

            try:
                result = func(*args, **kwargs)

                if sanitize:
                    safe_result = sanitize_sensitive_data(result)
                else:
                    safe_result = result

                weave.log(
                    {
                        "agent": agent_name,
                        "operation": operation,
                        "status": "success",
                        "output": safe_result,
                    }
                )

                return result

            except Exception as e:
                weave.log(
                    {
                        "agent": agent_name,
                        "operation": operation,
                        "status": "error",
                        "error": str(e),
                    }
                )
                raise

        return wrapper

    return decorator


def track_token_usage(
    agent_name: str,
    user_id: str,
    account_id: str,
    prompt_tokens: int,
    response_tokens: int,
    model: str = "gemini-2.0-flash",
    operation: str | None = None,
) -> dict[str, Any]:
    """Track token usage and calculate costs.

    Args:
        agent_name: Name of the agent
        user_id: User ID for attribution
        account_id: Account ID for billing
        prompt_tokens: Number of prompt tokens
        response_tokens: Number of response tokens
        model: Model used
        operation: Optional operation name

    Returns:
        Usage metrics with cost calculation
    """
    pricing = {
        "gemini-2.0-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-flash-latest": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-pro": {"prompt": 3.50, "response": 10.50},
        "gemini-1.5-pro-002": {"prompt": 3.50, "response": 10.50},
        "gemini-2.5-flash": {"prompt": 0.075, "response": 0.30},
    }

    model_pricing = pricing.get(model, pricing["gemini-2.0-flash"])

    prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
    response_cost = (response_tokens / 1_000_000) * model_pricing["response"]
    total_cost = prompt_cost + response_cost

    usage_data: dict[str, Any] = {
        "agent": agent_name,
        "user_id": user_id,
        "account_id": account_id,
        "model": model,
        "operation": operation,
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "total_tokens": prompt_tokens + response_tokens,
        "prompt_cost": prompt_cost,
        "response_cost": response_cost,
        "total_cost": total_cost,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if WEAVE_AVAILABLE and weave:
        try:
            weave.log(usage_data)
        except Exception as e:
            logger.error(f"Failed to log token usage to W&B: {e}")

    return usage_data


def create_cost_tracker(default_model: str = "gemini-2.0-flash") -> Callable:
    """Create a cost tracking function for an agent.

    Args:
        default_model: Default model for cost calculation

    Returns:
        Cost tracking function
    """

    def track_costs(
        agent_name: str,
        user_id: str,
        account_id: str,
        usage_metadata: Any,
    ) -> dict[str, Any]:
        """Track costs from usage metadata."""
        if not usage_metadata:
            return {}

        prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
        response_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0

        if prompt_tokens == 0 and response_tokens == 0:
            return {}

        return track_token_usage(
            agent_name=agent_name,
            user_id=user_id,
            account_id=account_id,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            model=default_model,
        )

    return track_costs
