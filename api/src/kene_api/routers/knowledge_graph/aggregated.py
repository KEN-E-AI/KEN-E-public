"""Aggregated strategy view endpoints.

Read-only endpoints that combine multiple node types into unified strategy views.
These endpoints provide complete strategy snapshots for each domain.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...models.graph_models import (
    BrandAwarenessStrategyResponse,
    BrandIdentityResponse,
    BrandPersonalityResponse,
    BrandStrategyResponse,
    BusinessStrategyResponse,
    ColorPaletteResponse,
    CompetitiveEnvironmentResponse,
    CompetitiveStrategyResponse,
    CompetitorResponse,
    CompetitorStrengthResponse,
    CompetitorTacticResponse,
    CompetitorWeaknessResponse,
    ConsiderationStrategyResponse,
    ConversionStrategyResponse,
    CustomerProfileResponse,
    GoalResponse,
    ImageStyleResponse,
    LoyaltyStrategyResponse,
    MarketingStrategyResponse,
    MissionAndValuesResponse,
    OpportunityResponse,
    ProblemAwarenessStrategyResponse,
    ProductCategoryResponse,
    ProductResponse,
    RiskResponse,
    StrengthResponse,
    SubstituteProductResponse,
    TypographyResponse,
    ValuePropositionResponse,
    VoiceAndToneResponse,
    WeaknessResponse,
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import check_graph_access

logger = logging.getLogger(__name__)

router = APIRouter()  # No prefix - parent handles it


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
        # Fetch all node types in parallel using asyncio.gather
        (
            categories_data,
            products_data,
            vps_data,
            strengths_data,
            weaknesses_data,
            opportunities_data,
            risks_data,
            goals_data,
            swot_data,
        ) = await asyncio.gather(
            service.list_nodes(account_id, "ProductCategory"),
            service.list_nodes(account_id, "Product"),
            service.list_nodes(account_id, "ValueProposition"),
            service.list_nodes(account_id, "Strength"),
            service.list_nodes(account_id, "Weakness"),
            service.list_nodes(account_id, "Opportunity"),
            service.list_nodes(account_id, "Risk"),
            service.list_nodes(account_id, "Goal"),
            service.list_nodes(account_id, "SWOTAnalysis"),
        )

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
        logger.exception(f"Failed to get business strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get business strategy",
        ) from e


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
        # Get all competitive nodes in parallel using asyncio.gather
        (
            env_data,
            competitors_data,
            tactics_data,
            strengths_data,
            weaknesses_data,
            products_data,
        ) = await asyncio.gather(
            service.list_nodes(account_id, "CompetitiveEnvironment", skip=0, limit=1),
            service.list_nodes(account_id, "Competitor"),
            service.list_nodes(account_id, "CompetitorTactic"),
            service.list_nodes(account_id, "CompetitorStrength"),
            service.list_nodes(account_id, "CompetitorWeakness"),
            service.list_nodes(account_id, "SubstituteProduct"),
        )
        comp_env = CompetitiveEnvironmentResponse(**env_data[0]) if env_data else None

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


@router.get(
    "/{account_id}/marketing-strategy", response_model=MarketingStrategyResponse
)
async def get_marketing_strategy(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> MarketingStrategyResponse:
    """Get complete marketing strategy graph."""
    await check_graph_access(account_id, user, "view")

    try:
        # Get all marketing nodes in parallel using asyncio.gather
        (
            profiles_data,
            problem_data,
            brand_data,
            consideration_data,
            conversion_data,
            loyalty_data,
        ) = await asyncio.gather(
            service.list_nodes(account_id, "CustomerProfile"),
            service.list_nodes(account_id, "ProblemAwarenessStrategy"),
            service.list_nodes(account_id, "BrandAwarenessStrategy"),
            service.list_nodes(account_id, "ConsiderationStrategy"),
            service.list_nodes(account_id, "ConversionStrategy"),
            service.list_nodes(account_id, "LoyaltyStrategy"),
        )

        return MarketingStrategyResponse(
            account_id=account_id,
            customer_profiles=[CustomerProfileResponse(**p) for p in profiles_data],
            problem_awareness_strategies=[
                ProblemAwarenessStrategyResponse(**s) for s in problem_data
            ],
            brand_awareness_strategies=[
                BrandAwarenessStrategyResponse(**s) for s in brand_data
            ],
            consideration_strategies=[
                ConsiderationStrategyResponse(**s) for s in consideration_data
            ],
            conversion_strategies=[
                ConversionStrategyResponse(**s) for s in conversion_data
            ],
            loyalty_strategies=[LoyaltyStrategyResponse(**s) for s in loyalty_data],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get marketing strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get marketing strategy",
        ) from e


@router.get("/{account_id}/brand-strategy", response_model=BrandStrategyResponse)
async def get_brand_strategy(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandStrategyResponse:
    """Get complete brand strategy graph."""
    await check_graph_access(account_id, user, "view")

    try:
        # Get all brand nodes in parallel using asyncio.gather
        (
            identity,
            personalities_data,
            voice_tones_data,
            palettes_data,
            typographies_data,
            styles_data,
            mission_data,
        ) = await asyncio.gather(
            service.get_brand_identity(account_id),
            service.list_nodes(account_id, "BrandPersonality"),
            service.list_nodes(account_id, "VoiceAndTone"),
            service.list_nodes(account_id, "ColorPalette"),
            service.list_nodes(account_id, "Typography"),
            service.list_nodes(account_id, "ImageStyle"),
            service.list_nodes(account_id, "MissionAndValues"),
        )

        return BrandStrategyResponse(
            account_id=account_id,
            brand_identity=BrandIdentityResponse(**identity) if identity else None,
            brand_personalities=[
                BrandPersonalityResponse(**p) for p in personalities_data
            ],
            voice_and_tones=[VoiceAndToneResponse(**v) for v in voice_tones_data],
            color_palettes=[ColorPaletteResponse(**c) for c in palettes_data],
            typographies=[TypographyResponse(**t) for t in typographies_data],
            image_styles=[ImageStyleResponse(**s) for s in styles_data],
            mission_and_values=[MissionAndValuesResponse(**m) for m in mission_data],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get brand strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get brand strategy",
        ) from e
