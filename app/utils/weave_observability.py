"""
Weights & Biases (Weave) observability wrapper for agent tracing and cost tracking.
"""

import os
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
import hashlib

try:
    import weave
    import wandb
    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False
    weave = None
    wandb = None

logger = logging.getLogger(__name__)


def setup_weave_tracing(
    project_name: Optional[str] = None,
    entity: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Initialize Weave with authentication and project configuration.
    
    Args:
        project_name: W&B project name (defaults to WANDB_PROJECT env var or "quickstart_playground")
        entity: W&B entity/team name (defaults to WANDB_ENTITY env var)
        api_key: W&B API key (defaults to WANDB_API_KEY env var)
        
    Returns:
        Project name if initialized successfully, None otherwise
    """
    if not WEAVE_AVAILABLE:
        logger.warning("Weave/W&B not installed. Run: pip install weave wandb")
        return None
    
    # Get configuration from environment if not provided
    api_key = api_key or os.getenv("WANDB_API_KEY")
    if not api_key:
        logger.warning("WANDB_API_KEY not set, W&B tracing disabled")
        return None
    
    # Set API key
    os.environ["WANDB_API_KEY"] = api_key
    
    # Get project and entity
    project = project_name or os.getenv("WANDB_PROJECT", "quickstart_playground")
    entity = entity or os.getenv("WANDB_ENTITY")
    
    try:
        # Initialize Weave
        full_project = f"{entity}/{project}" if entity else project
        weave.init(project_name=full_project)
        
        logger.info(f"Weave tracing initialized for project: {full_project}")
        return full_project
        
    except Exception as e:
        logger.error(f"Failed to initialize Weave: {e}")
        return None


def sanitize_sensitive_data(data: Any, keys_to_sanitize: list = None) -> Any:
    """
    Sanitize sensitive data before logging to W&B.
    
    Args:
        data: Data to sanitize
        keys_to_sanitize: List of keys to sanitize (defaults to common sensitive keys)
        
    Returns:
        Sanitized data
    """
    if keys_to_sanitize is None:
        keys_to_sanitize = [
            "password", "secret", "token", "api_key", "credentials",
            "auth", "authorization", "cookie", "session", "private"
        ]
    
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Check if key contains sensitive terms
            if any(term in key.lower() for term in keys_to_sanitize):
                # Hash the value for tracking without exposing
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
        # Check for common patterns (emails, IPs, etc.)
        if "@" in data and "." in data:  # Likely email
            parts = data.split("@")
            if len(parts) == 2:
                return f"{parts[0][:2]}***@{parts[1]}"
        return data
    else:
        return data


def track_agent_operation(
    agent_name: str,
    operation: str,
    sanitize: bool = True
):
    """
    Decorator to track agent operations with Weave.
    
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
        def wrapper(*args, **kwargs):
            # Sanitize inputs if needed
            if sanitize:
                safe_kwargs = sanitize_sensitive_data(kwargs)
            else:
                safe_kwargs = kwargs
            
            # Log operation start
            weave.log({
                "agent": agent_name,
                "operation": operation,
                "inputs": safe_kwargs
            })
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Sanitize and log result
                if sanitize:
                    safe_result = sanitize_sensitive_data(result)
                else:
                    safe_result = result
                
                weave.log({
                    "agent": agent_name,
                    "operation": operation,
                    "status": "success",
                    "output": safe_result
                })
                
                return result
                
            except Exception as e:
                # Log error
                weave.log({
                    "agent": agent_name,
                    "operation": operation,
                    "status": "error",
                    "error": str(e)
                })
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
    operation: Optional[str] = None
) -> Dict[str, Any]:
    """
    Track token usage and calculate costs.
    
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
    # Model pricing (per 1M tokens)
    pricing = {
        "gemini-2.0-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-flash-latest": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-pro": {"prompt": 3.50, "response": 10.50},
        "gemini-1.5-pro-002": {"prompt": 3.50, "response": 10.50},
        "gemini-2.5-flash": {"prompt": 0.075, "response": 0.30},
    }
    
    # Get pricing for model
    model_pricing = pricing.get(model, pricing["gemini-2.0-flash"])
    
    # Calculate costs (convert from per million to actual tokens)
    prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
    response_cost = (response_tokens / 1_000_000) * model_pricing["response"]
    total_cost = prompt_cost + response_cost
    
    usage_data = {
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
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Log to W&B if available
    if WEAVE_AVAILABLE and weave:
        try:
            weave.log(usage_data)
        except Exception as e:
            logger.error(f"Failed to log token usage to W&B: {e}")
    
    return usage_data


def create_cost_tracker(
    default_model: str = "gemini-2.0-flash"
) -> Callable:
    """
    Create a cost tracking function for an agent.
    
    Args:
        default_model: Default model for cost calculation
        
    Returns:
        Cost tracking function
    """
    def track_costs(
        agent_name: str,
        user_id: str,
        account_id: str,
        usage_metadata: Any
    ) -> Dict[str, Any]:
        """Track costs from usage metadata."""
        if not usage_metadata:
            return {}
        
        # Extract token counts
        prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
        response_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
        
        if prompt_tokens == 0 and response_tokens == 0:
            return {}
        
        # Track usage
        return track_token_usage(
            agent_name=agent_name,
            user_id=user_id,
            account_id=account_id,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            model=default_model
        )
    
    return track_costs


from datetime import datetime  # Add this import at the top