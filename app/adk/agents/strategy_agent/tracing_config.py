"""Weights & Biases Weave tracing configuration for strategy agents.

Provides comprehensive tracing, token tracking, and performance monitoring
using W&B Weave for better observability.
"""

import functools
import logging
import os

# Set up SSL and network configuration for W&B
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Configure OpenTelemetry to handle large Pydantic field descriptions
# Set high limits to support detailed model schemas with extensive documentation
# This prevents serialization errors when capturing complex Pydantic models in traces
os.environ["OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT"] = "50000"  # 50KB per attribute
os.environ["OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT"] = "50000"

# Ensure WANDB environment variables are loaded
if "WANDB_API_KEY" not in os.environ:
    # Try to load from .env file
    env_path = os.path.join(os.path.dirname(__file__), "../../.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("WANDB_API_KEY="):
                    os.environ["WANDB_API_KEY"] = line.split("=", 1)[1].strip()
                elif line.startswith("WANDB_PROJECT="):
                    os.environ["WANDB_PROJECT"] = line.split("=", 1)[1].strip()

try:
    import weave

    HAS_WEAVE = True
except ImportError:
    HAS_WEAVE = False

    # Create dummy decorator if weave is not available
    class DummyWeave:
        @staticmethod
        def op(**kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                return func

            return decorator

        @staticmethod
        def init(*args: Any, **kwargs: Any) -> None:
            pass

        @staticmethod
        def get_current_call() -> Any:
            return type("obj", (object,), {"summary": {}})()

    weave = DummyWeave()

from shared.token_utils import TokenEstimator, TokenLimitError

from .logging_config import StrategyAgentLogger

logger = logging.getLogger(__name__)


class WeaveTracer:
    """Manager for Weave tracing configuration and initialization."""

    initialized = False

    @classmethod
    def init_tracing(
        cls, project_name: str = "strategy-agents", auto_patch_llms: bool = True
    ) -> None:
        """Initialize Weave tracing with comprehensive settings.

        Args:
            project_name: W&B project name
            auto_patch_llms: Whether to auto-patch LLM libraries
        """
        if not HAS_WEAVE:
            logger.warning("Weave not available, tracing disabled")
            return

        if cls.initialized:
            logger.info("Weave already initialized")
            return

        try:
            # Use project from environment if available
            project_name = os.environ.get("WANDB_PROJECT", project_name)

            # Ensure API key is set
            if "WANDB_API_KEY" not in os.environ:
                logger.warning("WANDB_API_KEY not set, Weave tracing disabled")
                return

            # Initialize Weave with retry logic for network issues
            max_retries = 3
            retry_delay = 1

            for attempt in range(max_retries):
                try:
                    # Initialize Weave
                    settings = {}

                    if auto_patch_llms:
                        settings["autopatch_settings"] = {
                            "openai": {"log_input": True, "log_output": True},
                            "anthropic": {"log_input": True, "log_output": True},
                            "google.generativeai": {
                                "log_input": True,
                                "log_output": True,
                            },
                        }

                    weave.init(project_name, **settings)
                    cls.initialized = True
                    logger.info(
                        f"Initialized Weave tracing for project: {project_name}"
                    )
                    break

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Weave init attempt {attempt + 1} failed: {e}, retrying..."
                        )
                        time.sleep(retry_delay * (attempt + 1))
                    else:
                        logger.warning(
                            f"Failed to initialize Weave after {max_retries} attempts: {e}"
                        )

        except Exception as e:
            logger.warning(f"Failed to initialize Weave: {e}")


def sanitize_for_logging(data: Any, max_length: int = 1000) -> Any:
    """Sanitize data for logging to avoid huge payloads.

    Args:
        data: Data to sanitize
        max_length: Maximum string length

    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        return data[:max_length] + "..." if len(data) > max_length else data
    elif isinstance(data, dict):
        return {k: sanitize_for_logging(v, max_length) for k, v in data.items()}
    elif isinstance(data, list):
        return [
            sanitize_for_logging(item, max_length) for item in data[:10]
        ]  # Limit lists
    else:
        return str(data)[:max_length]


@weave.op(name="strategy_agent_execution")
def traced_agent_execution(
    agent_name: str, state: dict[str, Any], **kwargs: Any
) -> dict[str, Any]:
    """Traced wrapper for strategy agent execution.

    Args:
        agent_name: Name of the agent being executed
        state: Current state dictionary
        **kwargs: Additional arguments

    Returns:
        Agent execution result
    """
    call = (
        weave.get_current_call()
        if HAS_WEAVE
        else type("obj", (object,), {"summary": {}})()
    )

    # Track input metrics
    input_tokens = TokenEstimator.estimate_tokens(state)
    call.summary["input_tokens"] = input_tokens
    call.summary["agent_name"] = agent_name
    call.summary["input_keys"] = list(state.keys()) if isinstance(state, dict) else []

    # Check token limits
    try:
        token_check = TokenEstimator.check_input_limit(state, raise_on_exceed=True)
        call.summary["token_percentage"] = token_check["percentage"]
    except TokenLimitError as e:
        call.summary["error"] = "Token limit exceeded"
        call.summary["error_message"] = str(e)
        raise

    # This would be replaced with actual agent execution
    call.summary["success"] = True
    return state


@weave.op(name="llm_call_with_retry")
def safe_llm_call(model: Any, prompt: str, max_retries: int = 3, **kwargs: Any) -> str:
    """Safely call LLM with comprehensive error tracking and retry logic.

    Args:
        model: LLM model instance
        prompt: Prompt to send to model
        max_retries: Maximum number of retries
        **kwargs: Additional arguments for the model

    Returns:
        Model response

    Raises:
        Exception: If all retries fail
    """
    call = (
        weave.get_current_call()
        if HAS_WEAVE
        else type("obj", (object,), {"summary": {}})()
    )
    agent_logger = StrategyAgentLogger("llm_call")

    # Pre-call checks
    prompt_tokens = TokenEstimator.estimate_tokens(prompt)
    call.summary["prompt_tokens"] = prompt_tokens
    call.summary["model"] = str(model)

    # Check if prompt is within limits
    try:
        token_check = TokenEstimator.check_input_limit(prompt, raise_on_exceed=True)
        call.summary["prompt_token_percentage"] = token_check["percentage"]
    except TokenLimitError as e:
        call.summary["error"] = "Prompt exceeds token limit"
        agent_logger.log_llm_call(
            model=str(model), prompt_tokens=prompt_tokens, error=str(e)
        )
        raise

    retry_count = 0

    while retry_count < max_retries:
        try:
            start_time = time.time()

            # Make LLM call (this would be the actual call in production)
            # For now, we'll simulate it
            response = f"Response to: {prompt[:50]}..."  # Simulated response

            latency = time.time() - start_time
            response_tokens = TokenEstimator.estimate_tokens(response)

            # Track success metrics
            call.summary["response_tokens"] = response_tokens
            call.summary["total_tokens"] = prompt_tokens + response_tokens
            call.summary["retry_count"] = retry_count
            call.summary["latency_seconds"] = latency
            call.summary["success"] = True

            # Log the successful call
            agent_logger.log_llm_call(
                model=str(model),
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                latency_seconds=latency,
            )

            return response

        except Exception as e:
            retry_count += 1

            # Log error details
            error_key = f"error_attempt_{retry_count}"
            call.summary[error_key] = {
                "type": type(e).__name__,
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            agent_logger.log_error(e, {"retry_attempt": retry_count})

            if retry_count >= max_retries:
                call.summary["success"] = False
                call.summary["final_error"] = str(e)

                agent_logger.log_llm_call(
                    model=str(model),
                    prompt_tokens=prompt_tokens,
                    error=f"Failed after {max_retries} retries: {e}",
                )
                raise

            # Exponential backoff
            wait_time = 2**retry_count
            logger.info(f"Retry {retry_count}/{max_retries} after {wait_time}s wait")
            time.sleep(wait_time)

    # This should never be reached but mypy needs it
    raise Exception("Failed to execute LLM call")


@weave.op(name="document_processing")
def trace_document_processing(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Trace document processing with token tracking.

    Args:
        documents: List of documents to process

    Returns:
        Processing results with metrics
    """
    call = (
        weave.get_current_call()
        if HAS_WEAVE
        else type("obj", (object,), {"summary": {}})()
    )

    call.summary["document_count"] = len(documents)

    total_tokens = 0
    processed_docs = []

    for i, doc in enumerate(documents):
        doc_tokens = TokenEstimator.estimate_tokens(doc)
        total_tokens += doc_tokens

        # Track individual document
        call.summary[f"doc_{i}_tokens"] = doc_tokens
        call.summary[f"doc_{i}_name"] = doc.get("name", f"doc_{i}")

        processed_docs.append(
            {"name": doc.get("name"), "tokens": doc_tokens, "size_bytes": len(str(doc))}
        )

    call.summary["total_document_tokens"] = total_tokens

    # Check if documents are within reasonable limits
    if total_tokens > TokenEstimator.MAX_INPUT_TOKENS * 0.5:
        call.summary["warning"] = "Documents using >50% of token limit"

    return {
        "processed_count": len(processed_docs),
        "total_tokens": total_tokens,
        "documents": processed_docs,
    }


@weave.op(name="token_budget_check")
def check_token_budget(
    current_tokens: int, max_tokens: int, operation: str, warn_threshold: float = 0.8
) -> bool:
    """Check if operation is within token budget.

    Args:
        current_tokens: Current token count
        max_tokens: Maximum allowed tokens
        operation: Name of the operation
        warn_threshold: Warning threshold (0.8 = 80%)

    Returns:
        True if within budget, False otherwise
    """
    percentage = (current_tokens / max_tokens) * 100 if max_tokens > 0 else 0

    # Only try to log to Weave if available and initialized
    if HAS_WEAVE:
        try:
            call = weave.get_current_call()
            if call and hasattr(call, "summary"):
                call.summary["operation"] = operation
                call.summary["current_tokens"] = current_tokens
                call.summary["max_tokens"] = max_tokens
                call.summary["percentage"] = percentage
        except Exception:
            pass  # Silently continue if Weave isn't properly initialized

    if percentage > warn_threshold * 100:
        if HAS_WEAVE:
            try:
                call = weave.get_current_call()
                if call and hasattr(call, "summary"):
                    call.summary["warning"] = f"Token usage at {percentage:.1f}%"
            except Exception:
                pass
        logger.warning(f"[{operation}] Token usage at {percentage:.1f}% of limit")

    if percentage > 100:
        if HAS_WEAVE:
            try:
                call = weave.get_current_call()
                if call and hasattr(call, "summary"):
                    call.summary["error"] = "Token limit exceeded"
            except Exception:
                pass
        logger.error(
            f"[{operation}] Token limit exceeded: {current_tokens} > {max_tokens}"
        )
        return False

    if HAS_WEAVE:
        try:
            call = weave.get_current_call()
            if call and hasattr(call, "summary"):
                call.summary["within_budget"] = True
        except Exception:
            pass
    return True


def weave_traced(
    name: str | None = None, track_tokens: bool = True, track_time: bool = True
) -> Callable:
    """Decorator to add Weave tracing to any function.

    Args:
        name: Custom name for the operation
        track_tokens: Whether to track token usage
        track_time: Whether to track execution time
    """

    def decorator(func: Callable) -> Callable:
        op_name = name or func.__name__

        @weave.op(name=op_name)
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            call = (
                weave.get_current_call()
                if HAS_WEAVE
                else type("obj", (object,), {"summary": {}})()
            )

            start_time = time.time() if track_time else None

            # Track input tokens if requested
            if track_tokens:
                input_tokens = TokenEstimator.estimate_tokens(
                    {"args": args, "kwargs": kwargs}
                )
                call.summary["input_tokens"] = input_tokens

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Track output tokens if requested
                if track_tokens:
                    output_tokens = TokenEstimator.estimate_tokens(result)
                    call.summary["output_tokens"] = output_tokens
                    call.summary["total_tokens"] = input_tokens + output_tokens

                # Track execution time if requested
                if track_time and start_time:
                    call.summary["duration_seconds"] = time.time() - start_time

                call.summary["success"] = True
                return result

            except Exception as e:
                call.summary["error"] = type(e).__name__
                call.summary["error_message"] = str(e)
                call.summary["success"] = False

                if track_time and start_time:
                    call.summary["duration_seconds"] = time.time() - start_time

                raise

        return wrapper

    return decorator
