"""Subscription plans router for managing plan definitions."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import (
    SubscriptionPlanDefinition,
    SubscriptionPlanListResponse,
)

router = APIRouter()

SUBSCRIPTION_PLANS_COLLECTION = "subscription-plans"

# Cache configuration
# In development, disable caching for easier testing
IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "development") == "development"
CACHE_TTL_SECONDS = 0 if IS_DEVELOPMENT else 300  # No cache in dev, 5 minutes in prod
_cache_timestamp: datetime | None = None
_cached_plans: list[dict] | None = None


def _is_cache_valid() -> bool:
    """Check if the cache is still valid."""
    if IS_DEVELOPMENT:  # Always invalid in development
        return False
    if _cache_timestamp is None:
        return False
    return datetime.now(timezone.utc) - _cache_timestamp < timedelta(
        seconds=CACHE_TTL_SECONDS
    )


def _invalidate_cache() -> None:
    """Invalidate the cache."""
    global _cache_timestamp, _cached_plans
    _cache_timestamp = None
    _cached_plans = None


def _get_cached_plans() -> list[dict] | None:
    """Get cached plans if valid."""
    if _is_cache_valid():
        return _cached_plans
    return None


def _set_cached_plans(plans: list[dict]) -> None:
    """Set the cache with plans."""
    global _cache_timestamp, _cached_plans
    _cache_timestamp = datetime.now(timezone.utc)
    _cached_plans = plans.copy()


@router.get("/subscription-plans", response_model=SubscriptionPlanListResponse)
async def list_subscription_plans(
    active_only: bool = True,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SubscriptionPlanListResponse:
    """Get all subscription plans."""

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    try:
        # Check cache first
        cached_plans = _get_cached_plans()
        if cached_plans is not None:
            # Filter cached plans if needed
            plans_data = cached_plans
            if active_only:
                plans_data = [p for p in plans_data if p.get("is_active", True)]
        else:
            # Fetch from Firestore
            plans_data = firestore_service.list_documents(
                collection=SUBSCRIPTION_PLANS_COLLECTION,
                where_filters=[],  # Get all plans for caching
            )

            # Cache all plans
            _set_cached_plans(plans_data)

            # Filter if needed
            if active_only:
                plans_data = [p for p in plans_data if p.get("is_active", True)]

        plans = []
        for plan_dict in plans_data:
            if "id" in plan_dict and "plan_id" not in plan_dict:
                plan_dict["plan_id"] = plan_dict["id"]
            plans.append(SubscriptionPlanDefinition(**plan_dict))

        return SubscriptionPlanListResponse(
            plans=plans,
            total=len(plans),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing plans: {e!s}"
        ) from e


@router.get("/subscription-plans/default", response_model=SubscriptionPlanDefinition)
async def get_default_subscription_plan(
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SubscriptionPlanDefinition:
    """Get the default subscription plan for new organizations."""

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    try:
        # Check cache first
        cached_plans = _get_cached_plans()
        if cached_plans is not None:
            # Find default plan in cache
            default_plans = [
                p
                for p in cached_plans
                if p.get("is_default", False) and p.get("is_active", True)
            ]
            if default_plans:
                plan_dict = default_plans[0]
                if "id" in plan_dict and "plan_id" not in plan_dict:
                    plan_dict["plan_id"] = plan_dict["id"]
                return SubscriptionPlanDefinition(**plan_dict)

        # Not in cache or cache miss, fetch from Firestore
        plans_data = firestore_service.list_documents(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            where_filters=[
                ("is_default", "==", True),
                ("is_active", "==", True),
            ],
        )

        if not plans_data:
            raise HTTPException(status_code=404, detail="No default plan found")

        plan_dict = plans_data[0]
        if "id" in plan_dict and "plan_id" not in plan_dict:
            plan_dict["plan_id"] = plan_dict["id"]

        return SubscriptionPlanDefinition(**plan_dict)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting default plan: {e!s}"
        ) from e


@router.get("/subscription-plans/{plan_id}", response_model=SubscriptionPlanDefinition)
async def get_subscription_plan(
    plan_id: str,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SubscriptionPlanDefinition:
    """Get a specific subscription plan by ID."""

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    try:
        # Check cache first
        cached_plans = _get_cached_plans()
        if cached_plans is not None:
            # Find plan in cache
            for plan_dict in cached_plans:
                if (
                    plan_dict.get("plan_id") == plan_id
                    or plan_dict.get("id") == plan_id
                ):
                    if "id" in plan_dict and "plan_id" not in plan_dict:
                        plan_dict["plan_id"] = plan_dict["id"]
                    return SubscriptionPlanDefinition(**plan_dict)

        # Not in cache, fetch from Firestore
        plan_data = firestore_service.get_document(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            document_id=plan_id,
        )

        if not plan_data:
            raise HTTPException(status_code=404, detail="Plan not found")

        if "id" in plan_data and "plan_id" not in plan_data:
            plan_data["plan_id"] = plan_data["id"]

        return SubscriptionPlanDefinition(**plan_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting plan: {e!s}") from e


@router.post("/subscription-plans", response_model=SubscriptionPlanDefinition)
async def create_subscription_plan(
    plan: SubscriptionPlanDefinition,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SubscriptionPlanDefinition:
    """Create a new subscription plan (admin only)."""

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    try:
        # Check if plan_id already exists
        existing_plan = firestore_service.get_document(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            document_id=plan.plan_id,
        )

        if existing_plan:
            raise HTTPException(status_code=409, detail="Plan ID already exists")

        # If this is marked as default, unset other default plans
        if plan.is_default:
            default_plans = firestore_service.list_documents(
                collection=SUBSCRIPTION_PLANS_COLLECTION,
                where_filters=[("is_default", "==", True)],
            )

            for default_plan in default_plans:
                firestore_service.update_document(
                    collection=SUBSCRIPTION_PLANS_COLLECTION,
                    document_id=default_plan["id"],
                    data={
                        "is_default": False,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

        # Create the plan
        plan_data = plan.model_dump()
        plan_data["created_at"] = datetime.now(timezone.utc).isoformat()
        plan_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        firestore_service.create_document(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            document_id=plan.plan_id,
            data=plan_data,
        )

        # Invalidate cache after creating
        _invalidate_cache()

        return plan
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating plan: {e!s}"
        ) from e


@router.put("/subscription-plans/{plan_id}", response_model=SubscriptionPlanDefinition)
async def update_subscription_plan(
    plan_id: str,
    plan_update: dict[str, Any],
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SubscriptionPlanDefinition:
    """Update an existing subscription plan (admin only)."""

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    try:
        # Get existing plan
        existing_plan = firestore_service.get_document(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            document_id=plan_id,
        )

        if not existing_plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # If setting as default, unset other default plans
        if plan_update.get("is_default", False) and not existing_plan.get(
            "is_default", False
        ):
            default_plans = firestore_service.list_documents(
                collection=SUBSCRIPTION_PLANS_COLLECTION,
                where_filters=[("is_default", "==", True)],
            )

            for default_plan in default_plans:
                firestore_service.update_document(
                    collection=SUBSCRIPTION_PLANS_COLLECTION,
                    document_id=default_plan["id"],
                    data={
                        "is_default": False,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

        # Update the plan
        plan_update["updated_at"] = datetime.now(timezone.utc).isoformat()

        firestore_service.update_document(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            document_id=plan_id,
            data=plan_update,
        )

        # Invalidate cache after updating
        _invalidate_cache()

        # Get updated plan
        updated_plan = firestore_service.get_document(
            collection=SUBSCRIPTION_PLANS_COLLECTION,
            document_id=plan_id,
        )

        if "id" in updated_plan and "plan_id" not in updated_plan:
            updated_plan["plan_id"] = updated_plan["id"]

        return SubscriptionPlanDefinition(**updated_plan)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating plan: {e!s}"
        ) from e
