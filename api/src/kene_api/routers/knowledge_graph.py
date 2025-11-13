"""Unified knowledge graph API router for all strategy node types.

Provides CRUD endpoints for Business, Competitive, Marketing, and Brand strategy nodes.
Phase 1: Business Strategy nodes (9 types)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext
from ..exceptions import (
    DuplicateNodeException,
    GraphSyncException,
    NodeHasDependenciesException,
    NodeNotFoundException,
    ValidationException,
)
from ..models.graph_models import (
    BusinessStrategyResponse,
    CompetitiveEnvironmentResponse,
    CompetitiveEnvironmentUpdate,
    CompetitiveStrategyResponse,
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
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
    OpportunityCreate,
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityUpdate,
    ProductCategoryCreate,
    ProductCategoryListResponse,
    ProductCategoryResponse,
    ProductCategoryUpdate,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    RiskCreate,
    RiskListResponse,
    RiskResponse,
    RiskUpdate,
    StrengthCreate,
    StrengthListResponse,
    StrengthResponse,
    StrengthUpdate,
    SubstituteProductCreate,
    SubstituteProductListResponse,
    SubstituteProductResponse,
    SubstituteProductUpdate,
    ValuePropositionCreate,
    ValuePropositionListResponse,
    ValuePropositionResponse,
    ValuePropositionUpdate,
    WeaknessCreate,
    WeaknessListResponse,
    WeaknessResponse,
    WeaknessUpdate,
)
from ..services.graph_sync_service import GraphSyncService, get_graph_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-graph", tags=["knowledge-graph"])


async def check_graph_access(
    account_id: str,
    user: UserContext,
    required_level: str = "view",
) -> UserContext:
    """Check if user has required access level for graph operations.

    Args:
        account_id: Account ID to check access for
        user: Current user context
        required_level: Required permission level (view or edit)

    Returns:
        User context if access granted

    Raises:
        HTTPException: If access denied
    """
    # Super admins always have access
    if user.is_super_admin:
        return user

    # Check account-level permissions
    if not user.has_account_access(
        account_id, [required_level] if required_level == "edit" else None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions for {required_level} access to account {account_id}",
        )

    return user


# ==================== BUSINESS STRATEGY ENDPOINTS ====================
# Phase 1 Implementation: 9 node types


# ---------- ProductCategory Endpoints ----------


@router.post("/{account_id}/product-categories", response_model=ProductCategoryResponse)
async def create_product_category(
    account_id: str,
    category: ProductCategoryCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Create a new product category.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_product_category(
            account_id, category, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating product category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product category",
        ) from e


@router.get(
    "/{account_id}/product-categories", response_model=ProductCategoryListResponse
)
async def list_product_categories(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryListResponse:
    """List all product categories for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all categories
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(account_id, "ProductCategory")

        # Get paginated results
        categories_data = await service.list_nodes(
            account_id, "ProductCategory", skip=skip, limit=limit
        )
        categories = [ProductCategoryResponse(**cat) for cat in categories_data]

        return ProductCategoryListResponse(
            categories=categories, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list product categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list product categories",
        ) from e


@router.get(
    "/{account_id}/product-categories/{node_id}", response_model=ProductCategoryResponse
)
async def get_product_category(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Get a specific product category by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        category = await service.get_node(account_id, node_id, "ProductCategory")
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product category not found",
            )
        return ProductCategoryResponse(**category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get product category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get product category",
        ) from e


@router.patch(
    "/{account_id}/product-categories/{node_id}", response_model=ProductCategoryResponse
)
async def update_product_category(
    account_id: str,
    node_id: str,
    updates: ProductCategoryUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Update a product category.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_product_category(
            account_id, node_id, updates, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating product category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product category",
        ) from e


@router.delete(
    "/{account_id}/product-categories/{node_id}", response_model=DeleteResponse
)
async def delete_product_category(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a product category.

    Requires edit permission for the account.
    Cannot delete if category has products.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_product_category(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Product category {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting product category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete product category",
        ) from e


# ---------- Product Endpoints ----------


@router.post("/{account_id}/products", response_model=ProductResponse)
async def create_product(
    account_id: str,
    product: ProductCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductResponse:
    """Create a new product.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_product(account_id, product, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product",
        ) from e


@router.get("/{account_id}/products", response_model=ProductListResponse)
async def list_products(
    account_id: str,
    category_node_id: str | None = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductListResponse:
    """List all products for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all products
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(
            account_id, "Product", parent_node_id=category_node_id
        )

        # Get paginated results
        products_data = await service.list_nodes(
            account_id,
            "Product",
            parent_node_id=category_node_id,
            skip=skip,
            limit=limit,
        )
        products = [ProductResponse(**prod) for prod in products_data]

        return ProductListResponse(products=products, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list products",
        ) from e


@router.get("/{account_id}/products/{node_id}", response_model=ProductResponse)
async def get_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductResponse:
    """Get a specific product by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        product = await service.get_node(account_id, node_id, "Product")
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )
        return ProductResponse(**product)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get product",
        ) from e


@router.patch("/{account_id}/products/{node_id}", response_model=ProductResponse)
async def update_product(
    account_id: str,
    node_id: str,
    updates: ProductUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductResponse:
    """Update a product.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_product(
            account_id, node_id, updates, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product",
        ) from e


@router.delete("/{account_id}/products/{node_id}", response_model=DeleteResponse)
async def delete_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a product.

    Requires edit permission for the account.
    Cannot delete if product has value propositions.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_product(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Product {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete product",
        ) from e


# ---------- ValueProposition Endpoints ----------


@router.post(
    "/{account_id}/value-propositions", response_model=ValuePropositionResponse
)
async def create_value_proposition(
    account_id: str,
    value_prop: ValuePropositionCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionResponse:
    """Create a new value proposition.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_value_proposition(
            account_id, value_prop, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating value proposition: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create value proposition",
        ) from e


@router.get(
    "/{account_id}/value-propositions", response_model=ValuePropositionListResponse
)
async def list_value_propositions(
    account_id: str,
    parent_node_id: str | None = Query(
        None, description="Filter by parent (Product, ProductCategory, Account)"
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionListResponse:
    """List all value propositions for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all value propositions
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(
            account_id, "ValueProposition", parent_node_id=parent_node_id
        )

        # Get paginated results
        vps_data = await service.list_nodes(
            account_id,
            "ValueProposition",
            parent_node_id=parent_node_id,
            skip=skip,
            limit=limit,
        )
        value_propositions = [ValuePropositionResponse(**vp) for vp in vps_data]

        return ValuePropositionListResponse(
            value_propositions=value_propositions, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list value propositions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list value propositions",
        ) from e


@router.get(
    "/{account_id}/value-propositions/{node_id}",
    response_model=ValuePropositionResponse,
)
async def get_value_proposition(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionResponse:
    """Get a specific value proposition by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        value_prop = await service.get_node(account_id, node_id, "ValueProposition")
        if not value_prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Value proposition not found",
            )
        return ValuePropositionResponse(**value_prop)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get value proposition: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get value proposition",
        ) from e


@router.patch(
    "/{account_id}/value-propositions/{node_id}",
    response_model=ValuePropositionResponse,
)
async def update_value_proposition(
    account_id: str,
    node_id: str,
    updates: ValuePropositionUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionResponse:
    """Update a value proposition.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_value_proposition(
            account_id, node_id, updates, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating value proposition: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update value proposition",
        ) from e


@router.delete(
    "/{account_id}/value-propositions/{node_id}", response_model=DeleteResponse
)
async def delete_value_proposition(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a value proposition.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_value_proposition(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Value proposition {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting value proposition: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete value proposition",
        ) from e


# ---------- SWOT: Strength Endpoints ----------


@router.post("/{account_id}/strengths", response_model=StrengthResponse)
async def create_strength(
    account_id: str,
    strength: StrengthCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthResponse:
    """Create a new strength.

    Requires edit permission for the account.
    Auto-creates SWOT Analysis hub if doesn't exist.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_strength(account_id, strength, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create strength",
        ) from e


@router.get("/{account_id}/strengths", response_model=StrengthListResponse)
async def list_strengths(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthListResponse:
    """List all strengths for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all strengths
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(account_id, "Strength")

        # Get paginated results
        strengths_data = await service.list_nodes(
            account_id, "Strength", skip=skip, limit=limit
        )
        strengths = [StrengthResponse(**s) for s in strengths_data]

        return StrengthListResponse(strengths=strengths, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list strengths: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list strengths",
        ) from e


@router.get("/{account_id}/strengths/{node_id}", response_model=StrengthResponse)
async def get_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthResponse:
    """Get a specific strength by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        strength = await service.get_node(account_id, node_id, "Strength")
        if not strength:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Strength not found"
            )
        return StrengthResponse(**strength)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get strength",
        ) from e


@router.patch("/{account_id}/strengths/{node_id}", response_model=StrengthResponse)
async def update_strength(
    account_id: str,
    node_id: str,
    updates: StrengthUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthResponse:
    """Update a strength.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_strength(
            account_id, node_id, updates, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update strength",
        ) from e


@router.delete("/{account_id}/strengths/{node_id}", response_model=DeleteResponse)
async def delete_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a strength.

    Requires edit permission for the account.
    Cannot delete if strength has linked opportunities.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_strength(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Strength {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete strength",
        ) from e


# ---------- SWOT: Weakness Endpoints ----------


@router.post("/{account_id}/weaknesses", response_model=WeaknessResponse)
async def create_weakness(
    account_id: str,
    weakness: WeaknessCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessResponse:
    """Create a new weakness.

    Requires edit permission for the account.
    Auto-creates SWOT Analysis hub if doesn't exist.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_weakness(account_id, weakness, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create weakness",
        ) from e


@router.get("/{account_id}/weaknesses", response_model=WeaknessListResponse)
async def list_weaknesses(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessListResponse:
    """List all weaknesses for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all weaknesses
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(account_id, "Weakness")

        # Get paginated results
        weaknesses_data = await service.list_nodes(
            account_id, "Weakness", skip=skip, limit=limit
        )
        weaknesses = [WeaknessResponse(**w) for w in weaknesses_data]

        return WeaknessListResponse(weaknesses=weaknesses, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list weaknesses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list weaknesses",
        ) from e


@router.get("/{account_id}/weaknesses/{node_id}", response_model=WeaknessResponse)
async def get_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessResponse:
    """Get a specific weakness by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        weakness = await service.get_node(account_id, node_id, "Weakness")
        if not weakness:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Weakness not found"
            )
        return WeaknessResponse(**weakness)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weakness",
        ) from e


@router.patch("/{account_id}/weaknesses/{node_id}", response_model=WeaknessResponse)
async def update_weakness(
    account_id: str,
    node_id: str,
    updates: WeaknessUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessResponse:
    """Update a weakness.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_weakness(
            account_id, node_id, updates, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update weakness",
        ) from e


@router.delete("/{account_id}/weaknesses/{node_id}", response_model=DeleteResponse)
async def delete_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a weakness.

    Requires edit permission for the account.
    Cannot delete if weakness has linked risks.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_weakness(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Weakness {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete weakness",
        ) from e


# ---------- SWOT: Opportunity Endpoints ----------


@router.post("/{account_id}/opportunities", response_model=OpportunityResponse)
async def create_opportunity(
    account_id: str,
    opportunity: OpportunityCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityResponse:
    """Create a new opportunity.

    Requires edit permission for the account.
    Must be linked to a parent Strength.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_opportunity(account_id, opportunity, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating opportunity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create opportunity",
        ) from e


@router.get("/{account_id}/opportunities", response_model=OpportunityListResponse)
async def list_opportunities(
    account_id: str,
    strength_node_id: str | None = Query(None, description="Filter by parent strength"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityListResponse:
    """List all opportunities for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all opportunities
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(
            account_id, "Opportunity", parent_node_id=strength_node_id
        )

        # Get paginated results
        opportunities_data = await service.list_nodes(
            account_id,
            "Opportunity",
            parent_node_id=strength_node_id,
            skip=skip,
            limit=limit,
        )
        opportunities = [OpportunityResponse(**o) for o in opportunities_data]

        return OpportunityListResponse(
            opportunities=opportunities, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list opportunities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list opportunities",
        ) from e


@router.get("/{account_id}/opportunities/{node_id}", response_model=OpportunityResponse)
async def get_opportunity(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityResponse:
    """Get a specific opportunity by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        opportunity = await service.get_node(account_id, node_id, "Opportunity")
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found"
            )
        return OpportunityResponse(**opportunity)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get opportunity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get opportunity",
        ) from e


@router.patch(
    "/{account_id}/opportunities/{node_id}", response_model=OpportunityResponse
)
async def update_opportunity(
    account_id: str,
    node_id: str,
    updates: OpportunityUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityResponse:
    """Update an opportunity.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_opportunity(
            account_id, node_id, updates, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating opportunity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update opportunity",
        ) from e


@router.delete("/{account_id}/opportunities/{node_id}", response_model=DeleteResponse)
async def delete_opportunity(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete an opportunity.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_opportunity(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Opportunity {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting opportunity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete opportunity",
        ) from e


# ---------- SWOT: Risk Endpoints ----------


@router.post("/{account_id}/risks", response_model=RiskResponse)
async def create_risk(
    account_id: str,
    risk: RiskCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskResponse:
    """Create a new risk.

    Requires edit permission for the account.
    Must be linked to a parent Weakness.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_risk(account_id, risk, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create risk",
        ) from e


@router.get("/{account_id}/risks", response_model=RiskListResponse)
async def list_risks(
    account_id: str,
    weakness_node_id: str | None = Query(None, description="Filter by parent weakness"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskListResponse:
    """List all risks for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all risks
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(
            account_id, "Risk", parent_node_id=weakness_node_id
        )

        # Get paginated results
        risks_data = await service.list_nodes(
            account_id, "Risk", parent_node_id=weakness_node_id, skip=skip, limit=limit
        )
        risks = [RiskResponse(**r) for r in risks_data]

        return RiskListResponse(risks=risks, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list risks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list risks",
        ) from e


@router.get("/{account_id}/risks/{node_id}", response_model=RiskResponse)
async def get_risk(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskResponse:
    """Get a specific risk by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        risk = await service.get_node(account_id, node_id, "Risk")
        if not risk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found"
            )
        return RiskResponse(**risk)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get risk",
        ) from e


@router.patch("/{account_id}/risks/{node_id}", response_model=RiskResponse)
async def update_risk(
    account_id: str,
    node_id: str,
    updates: RiskUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskResponse:
    """Update a risk.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_risk(account_id, node_id, updates, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update risk",
        ) from e


@router.delete("/{account_id}/risks/{node_id}", response_model=DeleteResponse)
async def delete_risk(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a risk.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_risk(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Risk {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete risk",
        ) from e


# ---------- Goal Endpoints ----------


@router.post("/{account_id}/goals", response_model=GoalResponse)
async def create_goal(
    account_id: str,
    goal: GoalCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalResponse:
    """Create a new strategic goal.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_goal(account_id, goal, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create goal",
        ) from e


@router.get("/{account_id}/goals", response_model=GoalListResponse)
async def list_goals(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalListResponse:
    """List all goals for an account with optional pagination.

    Requires view permission for the account.

    Pagination is optional:
    - Without limit: Returns all goals
    - With limit: Returns paginated results using skip/limit
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count from database (not just returned results)
        total_count = await service.count_nodes(account_id, "Goal")

        # Get paginated results
        goals_data = await service.list_nodes(
            account_id, "Goal", skip=skip, limit=limit
        )
        goals = [GoalResponse(**g) for g in goals_data]

        return GoalListResponse(goals=goals, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list goals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list goals",
        ) from e


@router.get("/{account_id}/goals/{node_id}", response_model=GoalResponse)
async def get_goal(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalResponse:
    """Get a specific goal by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        goal = await service.get_node(account_id, node_id, "Goal")
        if not goal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
            )
        return GoalResponse(**goal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get goal",
        ) from e


@router.patch("/{account_id}/goals/{node_id}", response_model=GoalResponse)
async def update_goal(
    account_id: str,
    node_id: str,
    updates: GoalUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalResponse:
    """Update a goal.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_goal(account_id, node_id, updates, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update goal",
        ) from e


@router.delete("/{account_id}/goals/{node_id}", response_model=DeleteResponse)
async def delete_goal(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a goal.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_goal(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True,
            message=f"Goal {node_id} deleted successfully",
            deleted_node_id=node_id,
        )
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete goal",
        ) from e


# ==================== AGGREGATED VIEWS ====================


@router.get("/{account_id}/business-strategy", response_model=BusinessStrategyResponse)
async def get_business_strategy(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BusinessStrategyResponse:
    """Get complete business strategy graph for an account.

    Returns all nodes in a hierarchical structure similar to Firestore document.
    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Fetch all node types in parallel
        categories_data = await service.list_nodes(account_id, "ProductCategory")
        products_data = await service.list_nodes(account_id, "Product")
        vps_data = await service.list_nodes(account_id, "ValueProposition")
        strengths_data = await service.list_nodes(account_id, "Strength")
        weaknesses_data = await service.list_nodes(account_id, "Weakness")
        opportunities_data = await service.list_nodes(account_id, "Opportunity")
        risks_data = await service.list_nodes(account_id, "Risk")
        goals_data = await service.list_nodes(account_id, "Goal")

        # Get account info
        account_query = "MATCH (acc:Account {account_id: $account_id}) RETURN acc"
        account_result = await service.neo4j.execute_query(
            account_query, {"account_id": account_id}
        )

        if not account_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
            )

        account = account_result[0]["acc"]

        # Try to get SWOT hub
        swot_data = await service.list_nodes(account_id, "SWOTAnalysis")
        swot_analysis = swot_data[0] if swot_data else None

        return BusinessStrategyResponse(
            account_id=account_id,
            company_name=account.get("company_name", ""),
            company_overview=account.get("company_overview", ""),
            product_categories=[
                ProductCategoryResponse(**cat) for cat in categories_data
            ],
            products=[ProductResponse(**prod) for prod in products_data],
            value_propositions=[ValuePropositionResponse(**vp) for vp in vps_data],
            swot_analysis=swot_analysis,
            strengths=[StrengthResponse(**s) for s in strengths_data],
            weaknesses=[WeaknessResponse(**w) for w in weaknesses_data],
            opportunities=[OpportunityResponse(**o) for o in opportunities_data],
            risks=[RiskResponse(**r) for r in risks_data],
            goals=[GoalResponse(**g) for g in goals_data],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get business strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get business strategy",
        ) from e


# ==================== COMPETITIVE STRATEGY ENDPOINTS ====================
# Steps 2 & 3 Implementation: 6 node types


# ---------- Competitor Endpoints ----------


@router.post("/{account_id}/competitors", response_model=CompetitorResponse)
async def create_competitor(
    account_id: str,
    competitor: CompetitorCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorResponse:
    """Create a new competitor.

    Requires edit permission for the account.
    Auto-creates CompetitiveEnvironment hub if it doesn't exist.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_competitor(account_id, competitor, user.user_id)
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except DuplicateNodeException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating competitor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create competitor",
        ) from e


@router.get("/{account_id}/competitors", response_model=CompetitorListResponse)
async def list_competitors(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorListResponse:
    """List all competitors for an account with optional pagination.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(account_id, "Competitor")
        competitors_data = await service.list_nodes(
            account_id, "Competitor", skip=skip, limit=limit
        )
        competitors = [CompetitorResponse(**c) for c in competitors_data]

        return CompetitorListResponse(competitors=competitors, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list competitors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list competitors",
        ) from e


@router.get("/{account_id}/competitors/{node_id}", response_model=CompetitorResponse)
async def get_competitor(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorResponse:
    """Get a specific competitor by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        competitor = await service.get_node(account_id, node_id, "Competitor")
        if not competitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found"
            )
        return CompetitorResponse(**competitor)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get competitor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitor",
        ) from e


@router.patch("/{account_id}/competitors/{node_id}", response_model=CompetitorResponse)
async def update_competitor(
    account_id: str,
    node_id: str,
    updates: CompetitorUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorResponse:
    """Update a competitor.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_competitor(
            account_id, node_id, updates, user.user_id
        )
        return result
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update competitor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update competitor",
        ) from e


@router.delete("/{account_id}/competitors/{node_id}", response_model=DeleteResponse)
async def delete_competitor(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor.

    Requires edit permission for the account.
    Will fail if competitor has dependent nodes (tactics, strengths, weaknesses, products, VPs).
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_competitor(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True, message=f"Competitor {node_id} deleted successfully"
        )
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete competitor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete competitor",
        ) from e


# ---------- CompetitorTactic Endpoints ----------


@router.post(
    "/{account_id}/competitor-tactics", response_model=CompetitorTacticResponse
)
async def create_competitor_tactic(
    account_id: str,
    tactic: CompetitorTacticCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorTacticResponse:
    """Create a new competitor tactic.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_competitor_tactic(
            account_id, tactic, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating competitor tactic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create competitor tactic",
        ) from e


@router.get(
    "/{account_id}/competitor-tactics", response_model=CompetitorTacticListResponse
)
async def list_competitor_tactics(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorTacticListResponse:
    """List all competitor tactics for an account with optional pagination.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(account_id, "CompetitorTactic")
        tactics_data = await service.list_nodes(
            account_id, "CompetitorTactic", skip=skip, limit=limit
        )
        tactics = [CompetitorTacticResponse(**t) for t in tactics_data]

        return CompetitorTacticListResponse(tactics=tactics, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list competitor tactics: {e}")
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

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        tactic = await service.get_node(account_id, node_id, "CompetitorTactic")
        if not tactic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitor tactic not found",
            )
        return CompetitorTacticResponse(**tactic)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get competitor tactic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitor tactic",
        ) from e


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
    """Update a competitor tactic.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_competitor_tactic(
            account_id, node_id, updates, user.user_id
        )
        return result
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update competitor tactic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update competitor tactic",
        ) from e


@router.delete(
    "/{account_id}/competitor-tactics/{node_id}", response_model=DeleteResponse
)
async def delete_competitor_tactic(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor tactic.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_competitor_tactic(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True, message=f"Competitor tactic {node_id} deleted successfully"
        )
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete competitor tactic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete competitor tactic",
        ) from e


# ---------- CompetitorStrength Endpoints ----------


@router.post(
    "/{account_id}/competitor-strengths", response_model=CompetitorStrengthResponse
)
async def create_competitor_strength(
    account_id: str,
    strength: CompetitorStrengthCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorStrengthResponse:
    """Create a new competitor strength.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_competitor_strength(
            account_id, strength, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating competitor strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create competitor strength",
        ) from e


@router.get(
    "/{account_id}/competitor-strengths", response_model=CompetitorStrengthListResponse
)
async def list_competitor_strengths(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorStrengthListResponse:
    """List all competitor strengths for an account with optional pagination.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(account_id, "CompetitorStrength")
        strengths_data = await service.list_nodes(
            account_id, "CompetitorStrength", skip=skip, limit=limit
        )
        strengths = [CompetitorStrengthResponse(**s) for s in strengths_data]

        return CompetitorStrengthListResponse(
            strengths=strengths, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list competitor strengths: {e}")
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

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        strength = await service.get_node(account_id, node_id, "CompetitorStrength")
        if not strength:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitor strength not found",
            )
        return CompetitorStrengthResponse(**strength)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get competitor strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitor strength",
        ) from e


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
    """Update a competitor strength.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_competitor_strength(
            account_id, node_id, updates, user.user_id
        )
        return result
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update competitor strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update competitor strength",
        ) from e


@router.delete(
    "/{account_id}/competitor-strengths/{node_id}", response_model=DeleteResponse
)
async def delete_competitor_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor strength.

    Requires edit permission for the account.
    Will fail if strength has dependent Risk nodes.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_competitor_strength(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True, message=f"Competitor strength {node_id} deleted successfully"
        )
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete competitor strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete competitor strength",
        ) from e


# ---------- CompetitorWeakness Endpoints ----------


@router.post(
    "/{account_id}/competitor-weaknesses", response_model=CompetitorWeaknessResponse
)
async def create_competitor_weakness(
    account_id: str,
    weakness: CompetitorWeaknessCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorWeaknessResponse:
    """Create a new competitor weakness.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_competitor_weakness(
            account_id, weakness, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating competitor weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create competitor weakness",
        ) from e


@router.get(
    "/{account_id}/competitor-weaknesses", response_model=CompetitorWeaknessListResponse
)
async def list_competitor_weaknesses(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitorWeaknessListResponse:
    """List all competitor weaknesses for an account with optional pagination.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(account_id, "CompetitorWeakness")
        weaknesses_data = await service.list_nodes(
            account_id, "CompetitorWeakness", skip=skip, limit=limit
        )
        weaknesses = [CompetitorWeaknessResponse(**w) for w in weaknesses_data]

        return CompetitorWeaknessListResponse(
            weaknesses=weaknesses, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list competitor weaknesses: {e}")
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

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        weakness = await service.get_node(account_id, node_id, "CompetitorWeakness")
        if not weakness:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitor weakness not found",
            )
        return CompetitorWeaknessResponse(**weakness)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get competitor weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitor weakness",
        ) from e


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
    """Update a competitor weakness.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_competitor_weakness(
            account_id, node_id, updates, user.user_id
        )
        return result
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update competitor weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update competitor weakness",
        ) from e


@router.delete(
    "/{account_id}/competitor-weaknesses/{node_id}", response_model=DeleteResponse
)
async def delete_competitor_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a competitor weakness.

    Requires edit permission for the account.
    Will fail if weakness has dependent Opportunity nodes.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_competitor_weakness(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True, message=f"Competitor weakness {node_id} deleted successfully"
        )
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete competitor weakness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete competitor weakness",
        ) from e


# ---------- SubstituteProduct Endpoints ----------


@router.post(
    "/{account_id}/substitute-products", response_model=SubstituteProductResponse
)
async def create_substitute_product(
    account_id: str,
    product: SubstituteProductCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SubstituteProductResponse:
    """Create a new substitute product.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_substitute_product(
            account_id, product, user.user_id
        )
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating substitute product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create substitute product",
        ) from e


@router.get(
    "/{account_id}/substitute-products", response_model=SubstituteProductListResponse
)
async def list_substitute_products(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None,
        ge=1,
        le=1000,
        description="Maximum number of items to return (default: all)",
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SubstituteProductListResponse:
    """List all substitute products for an account with optional pagination.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        total_count = await service.count_nodes(account_id, "SubstituteProduct")
        products_data = await service.list_nodes(
            account_id, "SubstituteProduct", skip=skip, limit=limit
        )
        products = [SubstituteProductResponse(**p) for p in products_data]

        return SubstituteProductListResponse(products=products, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list substitute products: {e}")
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

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        product = await service.get_node(account_id, node_id, "SubstituteProduct")
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Substitute product not found",
            )
        return SubstituteProductResponse(**product)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get substitute product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get substitute product",
        ) from e


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
    """Update a substitute product.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_substitute_product(
            account_id, node_id, updates, user.user_id
        )
        return result
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update substitute product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update substitute product",
        ) from e


@router.delete(
    "/{account_id}/substitute-products/{node_id}", response_model=DeleteResponse
)
async def delete_substitute_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a substitute product.

    Requires edit permission for the account.
    Will fail if product has dependent ValueProposition nodes.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_substitute_product(account_id, node_id, user.user_id)
        return DeleteResponse(
            success=True, message=f"Substitute product {node_id} deleted successfully"
        )
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NodeHasDependenciesException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete substitute product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete substitute product",
        ) from e


# ---------- CompetitiveEnvironment Endpoints ----------


@router.get(
    "/{account_id}/competitive-environment",
    response_model=CompetitiveEnvironmentResponse,
)
async def get_competitive_environment(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitiveEnvironmentResponse:
    """Get the competitive environment hub for an account.

    Requires view permission for the account.
    Returns 404 if no competitive environment exists yet.
    """
    await check_graph_access(account_id, user, "view")

    try:
        envs = await service.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )
        if not envs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitive environment not found. Create a competitor to auto-create the environment.",
            )
        return CompetitiveEnvironmentResponse(**envs[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get competitive environment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitive environment",
        ) from e


@router.patch(
    "/{account_id}/competitive-environment/{node_id}",
    response_model=CompetitiveEnvironmentResponse,
)
async def update_competitive_environment(
    account_id: str,
    node_id: str,
    updates: CompetitiveEnvironmentUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitiveEnvironmentResponse:
    """Update the competitive environment.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_competitive_environment(
            account_id, node_id, updates, user.user_id
        )
        return result
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except GraphSyncException as e:
        logger.error(f"Graph sync error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update competitive environment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update competitive environment",
        ) from e


# ---------- Aggregated Competitive Strategy View ----------


@router.get(
    "/{account_id}/competitive-strategy", response_model=CompetitiveStrategyResponse
)
async def get_competitive_strategy(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitiveStrategyResponse:
    """Get complete competitive strategy graph for an account.

    Returns all competitive nodes in a single structured response:
    - CompetitiveEnvironment (hub)
    - Competitors
    - CompetitorTactics
    - CompetitorStrengths
    - CompetitorWeaknesses
    - SubstituteProducts

    Note: Risk and Opportunity nodes created by competitive SWOT can be queried
    separately via the /risks and /opportunities endpoints.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get competitive environment
        env_data = await service.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )
        comp_env = CompetitiveEnvironmentResponse(**env_data[0]) if env_data else None

        # Get all competitive nodes
        competitors_data = await service.list_nodes(account_id, "Competitor")
        tactics_data = await service.list_nodes(account_id, "CompetitorTactic")
        strengths_data = await service.list_nodes(account_id, "CompetitorStrength")
        weaknesses_data = await service.list_nodes(account_id, "CompetitorWeakness")
        products_data = await service.list_nodes(account_id, "SubstituteProduct")

        return CompetitiveStrategyResponse(
            account_id=account_id,
            competitive_environment=comp_env,
            competitors=[CompetitorResponse(**c) for c in competitors_data],
            competitor_tactics=[CompetitorTacticResponse(**t) for t in tactics_data],
            competitor_strengths=[
                CompetitorStrengthResponse(**s) for s in strengths_data
            ],
            competitor_weaknesses=[
                CompetitorWeaknessResponse(**w) for w in weaknesses_data
            ],
            substitute_products=[SubstituteProductResponse(**p) for p in products_data],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get competitive strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitive strategy",
        ) from e
