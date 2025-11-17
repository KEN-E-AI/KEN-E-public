"""Marketing strategy node endpoints.

CRUD endpoints for 6 marketing strategy node types:
- CustomerProfile, ProblemAwarenessStrategy, BrandAwarenessStrategy
- ConsiderationStrategy, ConversionStrategy, LoyaltyStrategy
"""

import logging

from fastapi import APIRouter, Depends, Query

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...models.graph_models import (
    BrandAwarenessStrategyCreate,
    BrandAwarenessStrategyListResponse,
    BrandAwarenessStrategyResponse,
    BrandAwarenessStrategyUpdate,
    ConsiderationStrategyCreate,
    ConsiderationStrategyListResponse,
    ConsiderationStrategyResponse,
    ConsiderationStrategyUpdate,
    ConversionStrategyCreate,
    ConversionStrategyListResponse,
    ConversionStrategyResponse,
    ConversionStrategyUpdate,
    CustomerProfileCreate,
    CustomerProfileListResponse,
    CustomerProfileResponse,
    CustomerProfileUpdate,
    DeleteResponse,
    LoyaltyStrategyCreate,
    LoyaltyStrategyListResponse,
    LoyaltyStrategyResponse,
    LoyaltyStrategyUpdate,
    ProblemAwarenessStrategyCreate,
    ProblemAwarenessStrategyListResponse,
    ProblemAwarenessStrategyResponse,
    ProblemAwarenessStrategyUpdate,
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import CRUDEndpoints

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== CUSTOMER PROFILE ENDPOINTS ====================


@router.post("/{account_id}/customer-profiles", response_model=CustomerProfileResponse)
async def create_customer_profile(
    account_id: str,
    customer_profile: CustomerProfileCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CustomerProfileResponse:
    """Create a new customer profile.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="CustomerProfile",
        create_data=customer_profile,
        response_model_class=CustomerProfileResponse,
        service_method=service.create_customer_profile,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/customer-profiles", response_model=CustomerProfileListResponse
)
async def list_customer_profiles(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CustomerProfileListResponse:
    """List all customer profiles with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="CustomerProfile",
        response_model_class=CustomerProfileResponse,
        list_response_class=CustomerProfileListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/customer-profiles/{node_id}",
    response_model=CustomerProfileResponse,
)
async def get_customer_profile(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CustomerProfileResponse:
    """Get a specific customer profile by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CustomerProfile",
        response_model_class=CustomerProfileResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/customer-profiles/{node_id}",
    response_model=CustomerProfileResponse,
)
async def update_customer_profile(
    account_id: str,
    node_id: str,
    updates: CustomerProfileUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CustomerProfileResponse:
    """Update a customer profile."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CustomerProfile",
        update_data=updates,
        response_model_class=CustomerProfileResponse,
        service_method=service.update_customer_profile,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/customer-profiles/{node_id}", response_model=DeleteResponse
)
async def delete_customer_profile(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a customer profile."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CustomerProfile",
        service_method=service.delete_customer_profile,
        service=service,
        user=user,
    )


# ==================== PROBLEM AWARENESS STRATEGY ENDPOINTS ====================


@router.post(
    "/{account_id}/problem-awareness-strategies",
    response_model=ProblemAwarenessStrategyResponse,
)
async def create_problem_awareness_strategy(
    account_id: str,
    problem_awareness_strategy: ProblemAwarenessStrategyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProblemAwarenessStrategyResponse:
    """Create a new problem awareness strategy.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ProblemAwarenessStrategy",
        create_data=problem_awareness_strategy,
        response_model_class=ProblemAwarenessStrategyResponse,
        service_method=service.create_problem_awareness_strategy,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/problem-awareness-strategies",
    response_model=ProblemAwarenessStrategyListResponse,
)
async def list_problem_awareness_strategies(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProblemAwarenessStrategyListResponse:
    """List all problem awareness strategies with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ProblemAwarenessStrategy",
        response_model_class=ProblemAwarenessStrategyResponse,
        list_response_class=ProblemAwarenessStrategyListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/problem-awareness-strategies/{node_id}",
    response_model=ProblemAwarenessStrategyResponse,
)
async def get_problem_awareness_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProblemAwarenessStrategyResponse:
    """Get a specific problem awareness strategy by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProblemAwarenessStrategy",
        response_model_class=ProblemAwarenessStrategyResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/problem-awareness-strategies/{node_id}",
    response_model=ProblemAwarenessStrategyResponse,
)
async def update_problem_awareness_strategy(
    account_id: str,
    node_id: str,
    updates: ProblemAwarenessStrategyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProblemAwarenessStrategyResponse:
    """Update a problem awareness strategy."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProblemAwarenessStrategy",
        update_data=updates,
        response_model_class=ProblemAwarenessStrategyResponse,
        service_method=service.update_problem_awareness_strategy,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/problem-awareness-strategies/{node_id}",
    response_model=DeleteResponse,
)
async def delete_problem_awareness_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a problem awareness strategy."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProblemAwarenessStrategy",
        service_method=service.delete_problem_awareness_strategy,
        service=service,
        user=user,
    )


# ==================== BRAND AWARENESS STRATEGY ENDPOINTS ====================


@router.post(
    "/{account_id}/brand-awareness-strategies",
    response_model=BrandAwarenessStrategyResponse,
)
async def create_brand_awareness_strategy(
    account_id: str,
    brand_awareness_strategy: BrandAwarenessStrategyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandAwarenessStrategyResponse:
    """Create a new brand awareness strategy.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="BrandAwarenessStrategy",
        create_data=brand_awareness_strategy,
        response_model_class=BrandAwarenessStrategyResponse,
        service_method=service.create_brand_awareness_strategy,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/brand-awareness-strategies",
    response_model=BrandAwarenessStrategyListResponse,
)
async def list_brand_awareness_strategies(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandAwarenessStrategyListResponse:
    """List all brand awareness strategies with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="BrandAwarenessStrategy",
        response_model_class=BrandAwarenessStrategyResponse,
        list_response_class=BrandAwarenessStrategyListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/brand-awareness-strategies/{node_id}",
    response_model=BrandAwarenessStrategyResponse,
)
async def get_brand_awareness_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandAwarenessStrategyResponse:
    """Get a specific brand awareness strategy by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="BrandAwarenessStrategy",
        response_model_class=BrandAwarenessStrategyResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/brand-awareness-strategies/{node_id}",
    response_model=BrandAwarenessStrategyResponse,
)
async def update_brand_awareness_strategy(
    account_id: str,
    node_id: str,
    updates: BrandAwarenessStrategyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandAwarenessStrategyResponse:
    """Update a brand awareness strategy."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="BrandAwarenessStrategy",
        update_data=updates,
        response_model_class=BrandAwarenessStrategyResponse,
        service_method=service.update_brand_awareness_strategy,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/brand-awareness-strategies/{node_id}", response_model=DeleteResponse
)
async def delete_brand_awareness_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a brand awareness strategy."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="BrandAwarenessStrategy",
        service_method=service.delete_brand_awareness_strategy,
        service=service,
        user=user,
    )


# ==================== CONSIDERATION STRATEGY ENDPOINTS ====================


@router.post(
    "/{account_id}/consideration-strategies",
    response_model=ConsiderationStrategyResponse,
)
async def create_consideration_strategy(
    account_id: str,
    consideration_strategy: ConsiderationStrategyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConsiderationStrategyResponse:
    """Create a new consideration strategy.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ConsiderationStrategy",
        create_data=consideration_strategy,
        response_model_class=ConsiderationStrategyResponse,
        service_method=service.create_consideration_strategy,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/consideration-strategies",
    response_model=ConsiderationStrategyListResponse,
)
async def list_consideration_strategies(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConsiderationStrategyListResponse:
    """List all consideration strategies with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ConsiderationStrategy",
        response_model_class=ConsiderationStrategyResponse,
        list_response_class=ConsiderationStrategyListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/consideration-strategies/{node_id}",
    response_model=ConsiderationStrategyResponse,
)
async def get_consideration_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConsiderationStrategyResponse:
    """Get a specific consideration strategy by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ConsiderationStrategy",
        response_model_class=ConsiderationStrategyResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/consideration-strategies/{node_id}",
    response_model=ConsiderationStrategyResponse,
)
async def update_consideration_strategy(
    account_id: str,
    node_id: str,
    updates: ConsiderationStrategyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConsiderationStrategyResponse:
    """Update a consideration strategy."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ConsiderationStrategy",
        update_data=updates,
        response_model_class=ConsiderationStrategyResponse,
        service_method=service.update_consideration_strategy,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/consideration-strategies/{node_id}", response_model=DeleteResponse
)
async def delete_consideration_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a consideration strategy."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ConsiderationStrategy",
        service_method=service.delete_consideration_strategy,
        service=service,
        user=user,
    )


# ==================== CONVERSION STRATEGY ENDPOINTS ====================


@router.post(
    "/{account_id}/conversion-strategies",
    response_model=ConversionStrategyResponse,
)
async def create_conversion_strategy(
    account_id: str,
    conversion_strategy: ConversionStrategyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConversionStrategyResponse:
    """Create a new conversion strategy.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ConversionStrategy",
        create_data=conversion_strategy,
        response_model_class=ConversionStrategyResponse,
        service_method=service.create_conversion_strategy,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/conversion-strategies",
    response_model=ConversionStrategyListResponse,
)
async def list_conversion_strategies(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConversionStrategyListResponse:
    """List all conversion strategies with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ConversionStrategy",
        response_model_class=ConversionStrategyResponse,
        list_response_class=ConversionStrategyListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/conversion-strategies/{node_id}",
    response_model=ConversionStrategyResponse,
)
async def get_conversion_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConversionStrategyResponse:
    """Get a specific conversion strategy by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ConversionStrategy",
        response_model_class=ConversionStrategyResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/conversion-strategies/{node_id}",
    response_model=ConversionStrategyResponse,
)
async def update_conversion_strategy(
    account_id: str,
    node_id: str,
    updates: ConversionStrategyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ConversionStrategyResponse:
    """Update a conversion strategy."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ConversionStrategy",
        update_data=updates,
        response_model_class=ConversionStrategyResponse,
        service_method=service.update_conversion_strategy,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/conversion-strategies/{node_id}", response_model=DeleteResponse
)
async def delete_conversion_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a conversion strategy."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ConversionStrategy",
        service_method=service.delete_conversion_strategy,
        service=service,
        user=user,
    )


# ==================== LOYALTY STRATEGY ENDPOINTS ====================


@router.post(
    "/{account_id}/loyalty-strategies",
    response_model=LoyaltyStrategyResponse,
)
async def create_loyalty_strategy(
    account_id: str,
    loyalty_strategy: LoyaltyStrategyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> LoyaltyStrategyResponse:
    """Create a new loyalty strategy.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="LoyaltyStrategy",
        create_data=loyalty_strategy,
        response_model_class=LoyaltyStrategyResponse,
        service_method=service.create_loyalty_strategy,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/loyalty-strategies",
    response_model=LoyaltyStrategyListResponse,
)
async def list_loyalty_strategies(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> LoyaltyStrategyListResponse:
    """List all loyalty strategies with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="LoyaltyStrategy",
        response_model_class=LoyaltyStrategyResponse,
        list_response_class=LoyaltyStrategyListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/loyalty-strategies/{node_id}",
    response_model=LoyaltyStrategyResponse,
)
async def get_loyalty_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> LoyaltyStrategyResponse:
    """Get a specific loyalty strategy by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="LoyaltyStrategy",
        response_model_class=LoyaltyStrategyResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/loyalty-strategies/{node_id}",
    response_model=LoyaltyStrategyResponse,
)
async def update_loyalty_strategy(
    account_id: str,
    node_id: str,
    updates: LoyaltyStrategyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> LoyaltyStrategyResponse:
    """Update a loyalty strategy."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="LoyaltyStrategy",
        update_data=updates,
        response_model_class=LoyaltyStrategyResponse,
        service_method=service.update_loyalty_strategy,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/loyalty-strategies/{node_id}", response_model=DeleteResponse
)
async def delete_loyalty_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a loyalty strategy."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="LoyaltyStrategy",
        service_method=service.delete_loyalty_strategy,
        service=service,
        user=user,
    )
