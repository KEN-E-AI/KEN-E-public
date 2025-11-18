"""Competitive strategy node endpoints.

CRUD endpoints for 6 competitive strategy node types:
- Competitor, CompetitorTactic, CompetitorStrength, CompetitorWeakness
- SubstituteProduct, CompetitiveEnvironment (hub)
"""

import logging

from fastapi import APIRouter, Depends, Query

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...models.graph_models import (
    CompetitiveEnvironmentResponse,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorResponse,
    CompetitorStrengthCreate,
    CompetitorStrengthListResponse,
    CompetitorStrengthResponse,
    CompetitorStrengthUpdate,
    CompetitorTacticCreate,
    CompetitorTacticListResponse,
    CompetitorTacticResponse,
    CompetitorTacticUpdate,
    CompetitorUpdate,
    CompetitorWeaknessCreate,
    CompetitorWeaknessListResponse,
    CompetitorWeaknessResponse,
    CompetitorWeaknessUpdate,
    DeleteResponse,
    SubstituteProductCreate,
    SubstituteProductListResponse,
    SubstituteProductResponse,
    SubstituteProductUpdate,
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import CRUDEndpoints

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== COMPETITOR ENDPOINTS ====================


@router.post("/{account_id}/competitors", response_model=CompetitorResponse)
async def create_competitor(
    account_id: str,
    competitor: CompetitorCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorResponse:
    """Create a new competitor.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Competitor",
        create_data=competitor,
        service_method=service.create_competitor,
        service=service,
        user=user,
    )


@router.get("/{account_id}/competitors", response_model=CompetitorListResponse)
async def list_competitors(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorListResponse:
    """List all competitors with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="Competitor",
        response_model_class=CompetitorResponse,
        list_response_class=CompetitorListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/competitors/{node_id}", response_model=CompetitorResponse)
async def get_competitor(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorResponse:
    """Get a specific competitor by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Competitor",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/competitors/{node_id}", response_model=CompetitorResponse)
async def update_competitor(
    account_id: str,
    node_id: str,
    updates: CompetitorUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorResponse:
    """Update a competitor."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Competitor",
        update_data=updates,
        service_method=service.update_competitor,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/competitors/{node_id}", response_model=DeleteResponse)
async def delete_competitor(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Competitor",
        service_method=service.delete_competitor,
        service=service,
        user=user,
    )


# ==================== COMPETITOR TACTIC ENDPOINTS ====================


@router.post(
    "/{account_id}/competitor-tactics", response_model=CompetitorTacticResponse
)
async def create_competitor_tactic(
    account_id: str,
    competitor_tactic: CompetitorTacticCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorTacticResponse:
    """Create a new competitor tactic.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="CompetitorTactic",
        create_data=competitor_tactic,
        service_method=service.create_competitor_tactic,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/competitor-tactics", response_model=CompetitorTacticListResponse
)
async def list_competitor_tactics(
    account_id: str,
    competitor_node_id: str | None = Query(None, description="Filter by competitor"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorTacticListResponse:
    """List all competitor tactics with optional pagination.

    Special case: Fetches parent competitor_node_id from relationship.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "view")

    try:
        # Get total count
        total_count = await service.count_nodes(
            account_id,
            "CompetitorTactic",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
        )

        # Get paginated results
        tactics_data = await service.list_nodes(
            account_id,
            "CompetitorTactic",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
            skip=skip,
            limit=limit,
        )

        # Map parent_node_id to competitor_node_id for response model
        tactics = [
            CompetitorTacticResponse(
                **{
                    **t,
                    "competitor_node_id": t.get("parent_node_id", ""),
                }
            )
            for t in tactics_data
        ]

        return CompetitorTacticListResponse(tactics=tactics, total_count=total_count)
    except Exception as e:
        logger.exception(f"Failed to list competitor tactics: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list competitor tactics",
        ) from e


@router.get(
    "/{account_id}/competitor-tactics/{node_id}",
    response_model=CompetitorTacticResponse,
)
async def get_competitor_tactic(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorTacticResponse:
    """Get a specific competitor tactic by node_id.

    Special case: Fetches parent competitor relationship.
    """
    competitor_query = """
    MATCH (c:Competitor)-[:USES_TACTIC]->(t:CompetitorTactic {node_id: $node_id})
    RETURN c.node_id as competitor_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorTactic",
        relationship_query=competitor_query,
        relationship_field="competitor_node_id",
        response_model_class=CompetitorTacticResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/competitor-tactics/{node_id}",
    response_model=CompetitorTacticResponse,
)
async def update_competitor_tactic(
    account_id: str,
    node_id: str,
    updates: CompetitorTacticUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorTacticResponse:
    """Update a competitor tactic."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorTactic",
        update_data=updates,
        service_method=service.update_competitor_tactic,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/competitor-tactics/{node_id}", response_model=DeleteResponse
)
async def delete_competitor_tactic(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor tactic."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorTactic",
        service_method=service.delete_competitor_tactic,
        service=service,
        user=user,
    )


# ==================== COMPETITOR STRENGTH ENDPOINTS ====================


@router.post(
    "/{account_id}/competitor-strengths", response_model=CompetitorStrengthResponse
)
async def create_competitor_strength(
    account_id: str,
    competitor_strength: CompetitorStrengthCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorStrengthResponse:
    """Create a new competitor strength.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="CompetitorStrength",
        create_data=competitor_strength,
        service_method=service.create_competitor_strength,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/competitor-strengths", response_model=CompetitorStrengthListResponse
)
async def list_competitor_strengths(
    account_id: str,
    competitor_node_id: str | None = Query(None, description="Filter by competitor"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorStrengthListResponse:
    """List all competitor strengths with optional pagination.

    Special case: Fetches parent competitor_node_id from relationship.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(
            account_id,
            "CompetitorStrength",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
        )

        strengths_data = await service.list_nodes(
            account_id,
            "CompetitorStrength",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
            skip=skip,
            limit=limit,
        )

        strengths = [
            CompetitorStrengthResponse(
                **{
                    **s,
                    "competitor_node_id": s.get("parent_node_id", ""),
                }
            )
            for s in strengths_data
        ]

        return CompetitorStrengthListResponse(
            strengths=strengths, total_count=total_count
        )
    except Exception as e:
        logger.exception(f"Failed to list competitor strengths: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list competitor strengths",
        ) from e


@router.get(
    "/{account_id}/competitor-strengths/{node_id}",
    response_model=CompetitorStrengthResponse,
)
async def get_competitor_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorStrengthResponse:
    """Get a specific competitor strength by node_id.

    Special case: Fetches parent competitor relationship.
    """
    competitor_query = """
    MATCH (c:Competitor)-[:HAS_STRENGTH]->(s:CompetitorStrength {node_id: $node_id})
    RETURN c.node_id as competitor_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorStrength",
        relationship_query=competitor_query,
        relationship_field="competitor_node_id",
        response_model_class=CompetitorStrengthResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/competitor-strengths/{node_id}",
    response_model=CompetitorStrengthResponse,
)
async def update_competitor_strength(
    account_id: str,
    node_id: str,
    updates: CompetitorStrengthUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorStrengthResponse:
    """Update a competitor strength."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorStrength",
        update_data=updates,
        service_method=service.update_competitor_strength,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/competitor-strengths/{node_id}", response_model=DeleteResponse
)
async def delete_competitor_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor strength."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorStrength",
        service_method=service.delete_competitor_strength,
        service=service,
        user=user,
    )


# ==================== COMPETITOR WEAKNESS ENDPOINTS ====================


@router.post(
    "/{account_id}/competitor-weaknesses", response_model=CompetitorWeaknessResponse
)
async def create_competitor_weakness(
    account_id: str,
    competitor_weakness: CompetitorWeaknessCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorWeaknessResponse:
    """Create a new competitor weakness.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="CompetitorWeakness",
        create_data=competitor_weakness,
        service_method=service.create_competitor_weakness,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/competitor-weaknesses", response_model=CompetitorWeaknessListResponse
)
async def list_competitor_weaknesses(
    account_id: str,
    competitor_node_id: str | None = Query(None, description="Filter by competitor"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorWeaknessListResponse:
    """List all competitor weaknesses with optional pagination.

    Special case: Fetches parent competitor_node_id from relationship.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(
            account_id,
            "CompetitorWeakness",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
        )

        weaknesses_data = await service.list_nodes(
            account_id,
            "CompetitorWeakness",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
            skip=skip,
            limit=limit,
        )

        weaknesses = [
            CompetitorWeaknessResponse(
                **{
                    **w,
                    "competitor_node_id": w.get("parent_node_id", ""),
                }
            )
            for w in weaknesses_data
        ]

        return CompetitorWeaknessListResponse(
            weaknesses=weaknesses, total_count=total_count
        )
    except Exception as e:
        logger.exception(f"Failed to list competitor weaknesses: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list competitor weaknesses",
        ) from e


@router.get(
    "/{account_id}/competitor-weaknesses/{node_id}",
    response_model=CompetitorWeaknessResponse,
)
async def get_competitor_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorWeaknessResponse:
    """Get a specific competitor weakness by node_id.

    Special case: Fetches parent competitor relationship.
    """
    competitor_query = """
    MATCH (c:Competitor)-[:HAS_WEAKNESS]->(w:CompetitorWeakness {node_id: $node_id})
    RETURN c.node_id as competitor_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorWeakness",
        relationship_query=competitor_query,
        relationship_field="competitor_node_id",
        response_model_class=CompetitorWeaknessResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/competitor-weaknesses/{node_id}",
    response_model=CompetitorWeaknessResponse,
)
async def update_competitor_weakness(
    account_id: str,
    node_id: str,
    updates: CompetitorWeaknessUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorWeaknessResponse:
    """Update a competitor weakness."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorWeakness",
        update_data=updates,
        service_method=service.update_competitor_weakness,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/competitor-weaknesses/{node_id}", response_model=DeleteResponse
)
async def delete_competitor_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor weakness."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="CompetitorWeakness",
        service_method=service.delete_competitor_weakness,
        service=service,
        user=user,
    )


# ==================== SUBSTITUTE PRODUCT ENDPOINTS ====================


@router.post(
    "/{account_id}/substitute-products", response_model=SubstituteProductResponse
)
async def create_substitute_product(
    account_id: str,
    substitute_product: SubstituteProductCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SubstituteProductResponse:
    """Create a new substitute product.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="SubstituteProduct",
        create_data=substitute_product,
        service_method=service.create_substitute_product,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/substitute-products", response_model=SubstituteProductListResponse
)
async def list_substitute_products(
    account_id: str,
    competitor_node_id: str | None = Query(None, description="Filter by competitor"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SubstituteProductListResponse:
    """List all substitute products with optional pagination.

    Special case: Fetches parent competitor_node_id from relationship.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(
            account_id,
            "SubstituteProduct",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
        )

        products_data = await service.list_nodes(
            account_id,
            "SubstituteProduct",
            parent_node_id=competitor_node_id,
            parent_node_type="Competitor" if competitor_node_id else None,
            skip=skip,
            limit=limit,
        )

        products = [
            SubstituteProductResponse(
                **{
                    **p,
                    "competitor_node_id": p.get("parent_node_id", ""),
                }
            )
            for p in products_data
        ]

        return SubstituteProductListResponse(products=products, total_count=total_count)
    except Exception as e:
        logger.exception(f"Failed to list substitute products: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list substitute products",
        ) from e


@router.get(
    "/{account_id}/substitute-products/{node_id}",
    response_model=SubstituteProductResponse,
)
async def get_substitute_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SubstituteProductResponse:
    """Get a specific substitute product by node_id.

    Special case: Fetches parent competitor relationship.
    """
    competitor_query = """
    MATCH (c:Competitor)-[:OFFERS_PRODUCT]->(p:SubstituteProduct {node_id: $node_id})
    RETURN c.node_id as competitor_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="SubstituteProduct",
        relationship_query=competitor_query,
        relationship_field="competitor_node_id",
        response_model_class=SubstituteProductResponse,
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/substitute-products/{node_id}",
    response_model=SubstituteProductResponse,
)
async def update_substitute_product(
    account_id: str,
    node_id: str,
    updates: SubstituteProductUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SubstituteProductResponse:
    """Update a substitute product."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="SubstituteProduct",
        update_data=updates,
        service_method=service.update_substitute_product,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/substitute-products/{node_id}", response_model=DeleteResponse
)
async def delete_substitute_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a substitute product."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="SubstituteProduct",
        service_method=service.delete_substitute_product,
        service=service,
        user=user,
    )


# ==================== COMPETITIVE ENVIRONMENT ENDPOINTS ====================
# Note: CompetitiveEnvironment is a hub node.
# Only GET and PATCH operations are supported (no CREATE/DELETE service methods).


@router.get(
    "/{account_id}/competitive-environment",
    response_model=CompetitiveEnvironmentResponse,
)
async def get_competitive_environment(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitiveEnvironmentResponse:
    """Get the competitive environment hub node.

    Note: There should only be one competitive environment node per account.
    It auto-creates when the first competitor is added.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "view")

    try:
        nodes_data = await service.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )
        if not nodes_data:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitive environment not found",
            )
        return CompetitiveEnvironmentResponse(**nodes_data[0])
    except Exception as e:
        logger.exception(f"Failed to get competitive environment: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitive environment",
        ) from e


@router.patch(
    "/{account_id}/competitive-environment",
    response_model=CompetitiveEnvironmentResponse,
)
async def update_competitive_environment(
    account_id: str,
    updates: dict,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitiveEnvironmentResponse:
    """Update the competitive environment hub node.

    Note: Fetches the existing node first, then updates it.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "edit")

    try:
        # Fetch the existing competitive environment node
        nodes_data = await service.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )
        if not nodes_data:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitive environment not found",
            )

        node_id = nodes_data[0]["node_id"]

        # Update using the service method
        updated_node = await service.update_competitive_environment(
            account_id=account_id,
            node_id=node_id,
            updates=updates,
        )
        return CompetitiveEnvironmentResponse(**updated_node)
    except Exception as e:
        logger.exception(f"Failed to update competitive environment: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update competitive environment",
        ) from e
