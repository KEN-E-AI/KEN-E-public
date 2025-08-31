"""Progress tracking service for account creation."""

import logging
from typing import List

from ..routers.accounts import AccountCreationProgress, ProgressStep
from .progress_cache import progress_cache

logger = logging.getLogger(__name__)


def update_account_creation_progress(
    account_id: str,
    step: int, 
    message: str,
    steps_status: List[str],
) -> None:
    """
    Update account creation progress and store in cache.
    
    Args:
        account_id: Account ID being created
        step: Current step number (1-7)
        message: Progress message to display  
        steps_status: List of status strings for each step (7 items)
    """
    # Map to the new 7-step process
    percentage = int((step / 7) * 100)
    
    # Handle both old 5-step and new 7-step formats
    if len(steps_status) == 5:
        # Legacy 5-step format - map to new 7-step format
        steps = [
            ProgressStep(name="Setting up database", status=steps_status[0]),
            ProgressStep(name="Researching your business", status=steps_status[1]),
            ProgressStep(name="Researching your competitors", status=steps_status[2]),
            ProgressStep(name="Researching your customers", status="pending"),
            ProgressStep(name="Inferring your marketing strategy", status="pending"),
            ProgressStep(name="Reviewing your brand styles", status=steps_status[3]),
            ProgressStep(name="Finalizing setup", status=steps_status[4]),
        ]
    else:
        # New 7-step format
        steps = [
            ProgressStep(name="Setting up database", status=steps_status[0] if len(steps_status) > 0 else "pending"),
            ProgressStep(name="Researching your business", status=steps_status[1] if len(steps_status) > 1 else "pending"),
            ProgressStep(name="Researching your competitors", status=steps_status[2] if len(steps_status) > 2 else "pending"),
            ProgressStep(name="Researching your customers", status=steps_status[3] if len(steps_status) > 3 else "pending"),
            ProgressStep(name="Inferring your marketing strategy", status=steps_status[4] if len(steps_status) > 4 else "pending"),
            ProgressStep(name="Reviewing your brand styles", status=steps_status[5] if len(steps_status) > 5 else "pending"),
            ProgressStep(name="Finalizing setup", status=steps_status[6] if len(steps_status) > 6 else "pending"),
        ]

    progress = AccountCreationProgress(
        status="processing",
        percentage=percentage,
        current_step=step,
        total_steps=7,
        message=message,
        steps=steps,
    )

    cache_key = f"account_creation:{account_id}"
    progress_data = progress.model_dump()
    
    logger.info(f"[PROGRESS UPDATE] Storing progress for {account_id}: step={step}, percentage={percentage}%, message={message}")
    logger.info(f"[PROGRESS UPDATE] Steps status: {steps_status}")
    
    progress_cache.set(cache_key, progress_data, ttl_seconds=3600)  # 1 hour TTL