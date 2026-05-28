"""Centralized logging configuration for strategy agents.

Provides structured logging with Google Cloud Logging integration for
comprehensive error tracking and monitoring.
"""

import functools
import json
import logging
import traceback
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

try:
    import google.cloud.logging

    HAS_CLOUD_LOGGING = True
except ImportError:
    HAS_CLOUD_LOGGING = False

from shared.token_utils import TokenEstimator

# Configure module logger
logger = logging.getLogger(__name__)


class StrategyAgentLogger:
    """Structured logger for strategy agents with Google Cloud Logging support."""

    def __init__(self, agent_name: str, use_cloud_logging: bool = True):
        """Initialize logger for a specific agent.

        Args:
            agent_name: Name of the agent (e.g., "business_strategist")
            use_cloud_logging: Whether to use Google Cloud Logging (if available)
        """
        self.agent_name = agent_name
        self.execution_id: str | None = None

        # Initialize Cloud Logging if available and requested
        self.cloud_logger = None
        if use_cloud_logging and HAS_CLOUD_LOGGING:
            try:
                client = google.cloud.logging.Client()
                self.cloud_logger = client.logger(f"strategy-agent-{agent_name}")
                logger.info(f"Initialized Cloud Logging for {agent_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Cloud Logging: {e}")

        # Always use local logger as fallback
        self.local_logger = logging.getLogger(f"strategy_agent.{agent_name}")
        self.local_logger.setLevel(logging.INFO)

    def _log_struct(self, data: dict[str, Any], severity: str = "INFO") -> None:
        """Log structured data to both Cloud and local logging.

        Args:
            data: Dictionary of data to log
            severity: Log severity level
        """
        # Add common fields
        data.update(
            {
                "agent": self.agent_name,
                "execution_id": self.execution_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Log to Cloud Logging if available
        if self.cloud_logger:
            try:
                self.cloud_logger.log_struct(data, severity=severity)
            except Exception as e:
                self.local_logger.warning(f"Cloud logging failed: {e}")

        # Always log locally
        log_method = getattr(
            self.local_logger, severity.lower(), self.local_logger.info
        )
        log_method(json.dumps(data, default=str))

    def log_agent_start(
        self, execution_id: str, input_tokens: int, context: dict[str, Any]
    ) -> None:
        """Log the start of agent execution.

        Args:
            execution_id: Unique ID for this execution
            input_tokens: Estimated input token count
            context: Additional context information
        """
        self.execution_id = execution_id

        self._log_struct(
            {
                "event": "agent_start",
                "input_token_count": input_tokens,
                "context_size_bytes": len(str(context)),
                "context_keys": list(context.keys())
                if isinstance(context, dict)
                else None,
            },
            severity="INFO",
        )

    def log_token_usage(
        self,
        phase: str,
        tokens: dict[str, int],
        percentage_of_limit: float | None = None,
    ) -> None:
        """Log token usage at different phases.

        Args:
            phase: Phase name (e.g., "input_assembly", "output_generation")
            tokens: Dictionary with token counts
            percentage_of_limit: Percentage of token limit used
        """
        data = {"event": "token_usage", "phase": phase, "tokens": tokens}

        if percentage_of_limit is not None:
            data["percentage_of_limit"] = percentage_of_limit  # type: ignore
            severity = "WARNING" if percentage_of_limit > 80 else "INFO"
        else:
            severity = "INFO"

        self._log_struct(data, severity=severity)

    def log_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        include_traceback: bool = True,
    ) -> None:
        """Log an error with full context.

        Args:
            error: The exception that occurred
            context: Additional context information
            include_traceback: Whether to include the full traceback
        """
        error_data = {
            "event": "agent_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }

        if include_traceback:
            error_data["error_traceback"] = traceback.format_exc()

        if context:
            # Truncate context to avoid huge logs
            error_data["context"] = str(context)[:2000]

        self._log_struct(error_data, severity="ERROR")

    def log_completion(
        self,
        success: bool,
        output_tokens: int | None = None,
        duration_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log agent completion.

        Args:
            success: Whether the agent completed successfully
            output_tokens: Number of output tokens generated
            duration_seconds: Execution duration
            metadata: Additional metadata
        """
        data = {"event": "agent_complete", "success": success}

        if output_tokens is not None:
            data["output_tokens"] = output_tokens

        if duration_seconds is not None:
            data["duration_seconds"] = duration_seconds

        if metadata:
            data["metadata"] = metadata

        severity = "INFO" if success else "WARNING"
        self._log_struct(data, severity=severity)

    def log_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        response_tokens: int | None = None,
        latency_seconds: float | None = None,
        error: str | None = None,
    ) -> None:
        """Log an LLM API call.

        Args:
            model: Model name/identifier
            prompt_tokens: Number of tokens in prompt
            response_tokens: Number of tokens in response
            latency_seconds: Call latency
            error: Error message if call failed
        """
        data = {
            "event": "llm_call",
            "model": model,
            "prompt_tokens": prompt_tokens,
            "success": error is None,
        }

        if response_tokens is not None:
            data["response_tokens"] = response_tokens
            data["total_tokens"] = prompt_tokens + response_tokens

        if latency_seconds is not None:
            data["latency_seconds"] = latency_seconds

        if error:
            data["error"] = error

        severity = "ERROR" if error else "INFO"
        self._log_struct(data, severity=severity)


def safe_agent_execution(
    agent_name: str | None = None, check_token_limits: bool = True
) -> Callable:
    """Decorator to safely execute agent functions with logging and error handling.

    Args:
        agent_name: Name of the agent (uses function name if not provided)
        check_token_limits: Whether to check token limits before execution
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create logger
            name = agent_name or func.__name__
            agent_logger = StrategyAgentLogger(name)
            execution_id = str(uuid.uuid4())

            # Add logger to kwargs for use within function
            kwargs["_logger"] = agent_logger

            start_time = datetime.now(timezone.utc)

            try:
                # Estimate input tokens if checking limits
                input_tokens = 0
                if check_token_limits:
                    try:
                        input_tokens = TokenEstimator.estimate_tokens(
                            {
                                "args": args,
                                "kwargs": {
                                    k: v for k, v in kwargs.items() if k != "_logger"
                                },
                            }
                        )

                        # Check if within limits
                        result = TokenEstimator.check_input_limit(
                            {"args": args, "kwargs": kwargs}, raise_on_exceed=True
                        )

                        agent_logger.log_token_usage(
                            phase="input_check",
                            tokens={"input": input_tokens},
                            percentage_of_limit=result["percentage"],
                        )
                    except Exception as e:
                        agent_logger.log_error(e, {"phase": "token_estimation"})
                        if "TokenLimitError" in str(type(e).__name__):
                            raise

                # Log execution start
                agent_logger.log_agent_start(
                    execution_id=execution_id,
                    input_tokens=input_tokens,
                    context={
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                # Execute function (remove _logger from kwargs)
                func_kwargs = {k: v for k, v in kwargs.items() if k != "_logger"}
                result = func(*args, **func_kwargs)

                # Calculate duration
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

                # Estimate output tokens
                output_tokens = TokenEstimator.estimate_tokens(result)

                # Log completion
                agent_logger.log_completion(
                    success=True, output_tokens=output_tokens, duration_seconds=duration
                )

                return result

            except Exception as e:
                # Log the error
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

                agent_logger.log_error(
                    error=e,
                    context={"function": func.__name__, "duration_seconds": duration},
                )

                # Log failed completion
                agent_logger.log_completion(
                    success=False, duration_seconds=duration, metadata={"error": str(e)}
                )

                # Re-raise to maintain behavior
                raise

        return wrapper

    return decorator


# Global logger instance for module-level logging
module_logger = StrategyAgentLogger("strategy_agent_module")
