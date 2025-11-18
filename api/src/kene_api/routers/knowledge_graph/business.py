"""Business strategy node endpoints.

CRUD endpoints for 9 business strategy node types:
- ProductCategory, Product, ValueProposition
- Strength, Weakness, Opportunity, Risk
- Goal, SWOTAnalysis (hub node - GET/LIST only)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...models.graph_models import (
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
    SWOTAnalysisResponse,
    ValuePropositionCreate,
    ValuePropositionListResponse,
    ValuePropositionResponse,
    ValuePropositionUpdate,
    WeaknessCreate,
    WeaknessListResponse,
    WeaknessResponse,
    WeaknessUpdate,
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import CRUDEndpoints, check_graph_access

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== PRODUCT CATEGORY ENDPOINTS ====================


@router.post("/{account_id}/product-categories", response_model=ProductCategoryResponse)
async def create_product_category(
    account_id: str,
    product_category: ProductCategoryCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Create a new product category.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ProductCategory",
        create_data=product_category,
        service_method=service.create_product_category,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/product-categories", response_model=ProductCategoryListResponse
)
async def list_product_categories(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryListResponse:
    """List all product categories with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ProductCategory",
        response_model_class=ProductCategoryResponse,
        list_response_class=ProductCategoryListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/product-categories/{node_id}", response_model=ProductCategoryResponse
)
async def get_product_category(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Get a specific product category by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProductCategory",
        service=service,
        user=user,
    )


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
    """Update a product category."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProductCategory",
        update_data=updates,
        service_method=service.update_product_category,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/product-categories/{node_id}", response_model=DeleteResponse
)
async def delete_product_category(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a product category."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProductCategory",
        service_method=service.delete_product_category,
        service=service,
        user=user,
    )


# ==================== PRODUCT ENDPOINTS ====================


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
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Product",
        create_data=product,
        service_method=service.create_product,
        service=service,
        user=user,
    )


@router.get("/{account_id}/products", response_model=ProductListResponse)
async def list_products(
    account_id: str,
    category_node_id: str | None = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductListResponse:
    """List all products with optional pagination.

    Special case: Uses optimized query to fetch category information
    and avoid N+1 query problem.
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Use optimized method that fetches category information in single query
        # Avoids N+1 query problem by using OPTIONAL MATCH
        products_data, total_count = await service.list_products_with_categories(
            account_id=account_id,
            category_node_id=category_node_id,
            skip=skip,
            limit=limit,
        )

        products = [ProductResponse(**prod) for prod in products_data]

        return ProductListResponse(products=products, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list products: {e}")
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

    Special case: Fetches category relationship.
    """
    category_query = """
    MATCH (cat:ProductCategory)-[:INCLUDES_PRODUCT]->(p:Product {node_id: $node_id})
    RETURN cat.node_id as category_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="Product",
        relationship_query=category_query,
        relationship_field="category_node_id",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/products/{node_id}", response_model=ProductResponse)
async def update_product(
    account_id: str,
    node_id: str,
    updates: ProductUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductResponse:
    """Update a product."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Product",
        update_data=updates,
        service_method=service.update_product,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/products/{node_id}", response_model=DeleteResponse)
async def delete_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a product."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Product",
        service_method=service.delete_product,
        service=service,
        user=user,
    )


# ==================== VALUE PROPOSITION ENDPOINTS ====================


@router.post(
    "/{account_id}/value-propositions", response_model=ValuePropositionResponse
)
async def create_value_proposition(
    account_id: str,
    value_proposition: ValuePropositionCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionResponse:
    """Create a new value proposition.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ValueProposition",
        create_data=value_proposition,
        service_method=service.create_value_proposition,
        service=service,
        user=user,
    )


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
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionListResponse:
    """List all value propositions with optional pagination.

    Can filter by parent (Product, ProductCategory, or Account).
    Special case: Filters out invalid parent_node_type values from service layer.
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count
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

        # Filter parent_node_type to valid values or set to None
        # Service may return incorrect label (e.g., 'Strategy' instead of 'ProductCategory')
        valid_parent_types = {"Product", "ProductCategory", "Account"}
        value_propositions = []
        for vp in vps_data:
            parent_type = vp.get("parent_node_type")
            if parent_type not in valid_parent_types:
                # Remove invalid parent_node_type to avoid validation error
                vp = {**vp, "parent_node_type": None, "parent_node_id": None}
            value_propositions.append(ValuePropositionResponse(**vp))

        return ValuePropositionListResponse(
            value_propositions=value_propositions, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list value propositions: {e}")
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
    """Get a specific value proposition by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ValueProposition",
        service=service,
        user=user,
    )


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
    """Update a value proposition."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ValueProposition",
        update_data=updates,
        service_method=service.update_value_proposition,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/value-propositions/{node_id}", response_model=DeleteResponse
)
async def delete_value_proposition(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a value proposition."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ValueProposition",
        service_method=service.delete_value_proposition,
        service=service,
        user=user,
    )


# ==================== STRENGTH ENDPOINTS ====================


@router.post("/{account_id}/strengths", response_model=StrengthResponse)
async def create_strength(
    account_id: str,
    strength: StrengthCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthResponse:
    """Create a new strength.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Strength",
        create_data=strength,
        service_method=service.create_strength,
        service=service,
        user=user,
    )


@router.get("/{account_id}/strengths", response_model=StrengthListResponse)
async def list_strengths(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthListResponse:
    """List all strengths with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="Strength",
        response_model_class=StrengthResponse,
        list_response_class=StrengthListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/strengths/{node_id}", response_model=StrengthResponse)
async def get_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthResponse:
    """Get a specific strength by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Strength",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/strengths/{node_id}", response_model=StrengthResponse)
async def update_strength(
    account_id: str,
    node_id: str,
    updates: StrengthUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> StrengthResponse:
    """Update a strength."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Strength",
        update_data=updates,
        service_method=service.update_strength,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/strengths/{node_id}", response_model=DeleteResponse)
async def delete_strength(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a strength."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Strength",
        service_method=service.delete_strength,
        service=service,
        user=user,
    )


# ==================== WEAKNESS ENDPOINTS ====================


@router.post("/{account_id}/weaknesses", response_model=WeaknessResponse)
async def create_weakness(
    account_id: str,
    weakness: WeaknessCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessResponse:
    """Create a new weakness.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Weakness",
        create_data=weakness,
        service_method=service.create_weakness,
        service=service,
        user=user,
    )


@router.get("/{account_id}/weaknesses", response_model=WeaknessListResponse)
async def list_weaknesses(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessListResponse:
    """List all weaknesses with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="Weakness",
        response_model_class=WeaknessResponse,
        list_response_class=WeaknessListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/weaknesses/{node_id}", response_model=WeaknessResponse)
async def get_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessResponse:
    """Get a specific weakness by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Weakness",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/weaknesses/{node_id}", response_model=WeaknessResponse)
async def update_weakness(
    account_id: str,
    node_id: str,
    updates: WeaknessUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> WeaknessResponse:
    """Update a weakness."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Weakness",
        update_data=updates,
        service_method=service.update_weakness,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/weaknesses/{node_id}", response_model=DeleteResponse)
async def delete_weakness(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a weakness."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Weakness",
        service_method=service.delete_weakness,
        service=service,
        user=user,
    )


# ==================== OPPORTUNITY ENDPOINTS ====================


@router.post("/{account_id}/opportunities", response_model=OpportunityResponse)
async def create_opportunity(
    account_id: str,
    opportunity: OpportunityCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityResponse:
    """Create a new opportunity.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Opportunity",
        create_data=opportunity,
        service_method=service.create_opportunity,
        service=service,
        user=user,
    )


@router.get("/{account_id}/opportunities", response_model=OpportunityListResponse)
async def list_opportunities(
    account_id: str,
    strength_node_id: str | None = Query(None, description="Filter by parent Strength"),
    weakness_node_id: str | None = Query(
        None, description="Filter by parent CompetitorWeakness"
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityListResponse:
    """List all opportunities with optional pagination.

    Can filter by either Strength or CompetitorWeakness parent.
    """
    await check_graph_access(account_id, user, "view")

    # Determine parent filter
    if strength_node_id and weakness_node_id:
        raise ValueError("Cannot filter by both strength_node_id and weakness_node_id")

    parent_node_id = strength_node_id or weakness_node_id
    parent_node_type = (
        "Strength"
        if strength_node_id
        else "CompetitorWeakness"
        if weakness_node_id
        else None
    )

    try:
        # Get total count
        total_count = await service.count_nodes(
            account_id,
            "Opportunity",
            parent_node_id=parent_node_id,
            parent_node_type=parent_node_type,
        )

        # Get paginated results
        opportunities_data = await service.list_nodes(
            account_id,
            "Opportunity",
            parent_node_id=parent_node_id,
            parent_node_type=parent_node_type,
            skip=skip,
            limit=limit,
        )

        # Map parent_node_id to appropriate field based on parent type
        opportunities = []
        for o in opportunities_data:
            # Start with all node data
            response_data = dict(o)

            # Determine which parent field to populate based on parent_node_type in the data
            parent_type = o.get("parent_node_type")
            parent_id = o.get("parent_node_id")

            if parent_type == "Strength" or (not parent_type and strength_node_id):
                response_data["strength_node_id"] = parent_id or o.get(
                    "strength_node_id"
                )
                response_data["weakness_node_id"] = None
            elif parent_type == "CompetitorWeakness" or (
                not parent_type and weakness_node_id
            ):
                response_data["weakness_node_id"] = parent_id or o.get(
                    "weakness_node_id"
                )
                response_data["strength_node_id"] = None
            else:
                # Default case - set both to None if no parent info
                response_data.setdefault("strength_node_id", None)
                response_data.setdefault("weakness_node_id", None)

            # Remove internal fields before creating response
            response_data.pop("parent_node_id", None)
            response_data.pop("parent_node_type", None)

            opportunities.append(OpportunityResponse(**response_data))

        return OpportunityListResponse(
            opportunities=opportunities, total_count=total_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list opportunities: {e}")
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

    Special case: Fetches parent strength relationship.
    """
    strength_query = """
    MATCH (s:Strength)-[:CREATES]->(o:Opportunity {node_id: $node_id})
    RETURN s.node_id as strength_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="Opportunity",
        relationship_query=strength_query,
        relationship_field="strength_node_id",
        service=service,
        user=user,
    )


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
    """Update an opportunity."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Opportunity",
        update_data=updates,
        service_method=service.update_opportunity,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/opportunities/{node_id}", response_model=DeleteResponse)
async def delete_opportunity(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete an opportunity."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Opportunity",
        service_method=service.delete_opportunity,
        service=service,
        user=user,
    )


# ==================== RISK ENDPOINTS ====================


@router.post("/{account_id}/risks", response_model=RiskResponse)
async def create_risk(
    account_id: str,
    risk: RiskCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskResponse:
    """Create a new risk.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Risk",
        create_data=risk,
        service_method=service.create_risk,
        service=service,
        user=user,
    )


@router.get("/{account_id}/risks", response_model=RiskListResponse)
async def list_risks(
    account_id: str,
    weakness_node_id: str | None = Query(None, description="Filter by parent weakness"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskListResponse:
    """List all risks with optional pagination.

    Special case: Maps parent_node_id to weakness_node_id for response model.
    """
    await check_graph_access(account_id, user, "view")

    try:
        # Get total count
        total_count = await service.count_nodes(
            account_id,
            "Risk",
            parent_node_id=weakness_node_id,
            parent_node_type="Weakness",
        )

        # Get paginated results
        risks_data = await service.list_nodes(
            account_id,
            "Risk",
            parent_node_id=weakness_node_id,
            parent_node_type="Weakness",
            skip=skip,
            limit=limit,
        )

        # Map parent_node_id to weakness_node_id for the response model
        risks = [
            RiskResponse(
                **{
                    **r,
                    "weakness_node_id": r.get(
                        "parent_node_id", r.get("weakness_node_id")
                    ),
                }
            )
            for r in risks_data
        ]

        return RiskListResponse(risks=risks, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list risks: {e}")
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

    Special case: Fetches parent weakness relationship.
    """
    weakness_query = """
    MATCH (w:Weakness)-[:CREATES]->(r:Risk {node_id: $node_id})
    RETURN w.node_id as weakness_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="Risk",
        relationship_query=weakness_query,
        relationship_field="weakness_node_id",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/risks/{node_id}", response_model=RiskResponse)
async def update_risk(
    account_id: str,
    node_id: str,
    updates: RiskUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RiskResponse:
    """Update a risk."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Risk",
        update_data=updates,
        service_method=service.update_risk,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/risks/{node_id}", response_model=DeleteResponse)
async def delete_risk(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a risk."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Risk",
        service_method=service.delete_risk,
        service=service,
        user=user,
    )


# ==================== GOAL ENDPOINTS ====================


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
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Goal",
        create_data=goal,
        service_method=service.create_goal,
        service=service,
        user=user,
    )


@router.get("/{account_id}/goals", response_model=GoalListResponse)
async def list_goals(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalListResponse:
    """List all goals with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="Goal",
        response_model_class=GoalResponse,
        list_response_class=GoalListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/goals/{node_id}", response_model=GoalResponse)
async def get_goal(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalResponse:
    """Get a specific goal by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Goal",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/goals/{node_id}", response_model=GoalResponse)
async def update_goal(
    account_id: str,
    node_id: str,
    updates: GoalUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> GoalResponse:
    """Update a goal."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Goal",
        update_data=updates,
        service_method=service.update_goal,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/goals/{node_id}", response_model=DeleteResponse)
async def delete_goal(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a goal."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Goal",
        service_method=service.delete_goal,
        service=service,
        user=user,
    )


# ==================== SWOT ANALYSIS ENDPOINTS ====================
# Note: SWOTAnalysis is a hub node with max_per_account=1.
# Only GET and LIST operations are supported (no CREATE/UPDATE/DELETE service methods).


@router.get("/{account_id}/swot-analysis", response_model=list[SWOTAnalysisResponse])
async def list_swot_analysis(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> list[SWOTAnalysisResponse]:
    """List SWOT analysis nodes.

    Note: There should only be one SWOT analysis node per account.
    Returns a list for consistency with other list endpoints.
    """
    from .crud_factory import check_graph_access

    await check_graph_access(account_id, user, "view")

    try:
        nodes_data = await service.list_nodes(
            account_id, "SWOTAnalysis", skip=0, limit=1
        )
        return [SWOTAnalysisResponse(**node) for node in nodes_data]
    except Exception as e:
        logger.exception(f"Failed to list SWOT analysis: {e}")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list SWOT analysis",
        ) from e


@router.get(
    "/{account_id}/swot-analysis/{node_id}", response_model=SWOTAnalysisResponse
)
async def get_swot_analysis(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> SWOTAnalysisResponse:
    """Get a specific SWOT analysis node by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="SWOTAnalysis",
        service=service,
        user=user,
    )
