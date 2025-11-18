"""Brand strategy node endpoints.

CRUD endpoints for 7 brand strategy node types:
- BrandPersonality, VoiceAndTone, ColorPalette, Typography
- ImageStyle, MissionAndValues, BrandIdentity (hub)
"""

import logging

from fastapi import APIRouter, Depends, Query

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...models.graph_models import (
    BrandIdentityResponse,
    BrandIdentityUpdate,
    BrandPersonalityCreate,
    BrandPersonalityListResponse,
    BrandPersonalityResponse,
    BrandPersonalityUpdate,
    ColorPaletteCreate,
    ColorPaletteListResponse,
    ColorPaletteResponse,
    ColorPaletteUpdate,
    DeleteResponse,
    ImageStyleCreate,
    ImageStyleListResponse,
    ImageStyleResponse,
    ImageStyleUpdate,
    MissionAndValuesCreate,
    MissionAndValuesListResponse,
    MissionAndValuesResponse,
    MissionAndValuesUpdate,
    TypographyCreate,
    TypographyListResponse,
    TypographyResponse,
    TypographyUpdate,
    VoiceAndToneCreate,
    VoiceAndToneListResponse,
    VoiceAndToneResponse,
    VoiceAndToneUpdate,
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import CRUDEndpoints

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== BRAND PERSONALITY ENDPOINTS ====================


@router.post(
    "/{account_id}/brand-personalities", response_model=BrandPersonalityResponse
)
async def create_brand_personality(
    account_id: str,
    brand_personality: BrandPersonalityCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandPersonalityResponse:
    """Create a new brand personality.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="BrandPersonality",
        create_data=brand_personality,
        service_method=service.create_brand_personality,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/brand-personalities", response_model=BrandPersonalityListResponse
)
async def list_brand_personalities(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandPersonalityListResponse:
    """List all brand personalities with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="BrandPersonality",
        list_response_class=BrandPersonalityListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/brand-personalities/{node_id}",
    response_model=BrandPersonalityResponse,
)
async def get_brand_personality(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandPersonalityResponse:
    """Get a specific brand personality by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="BrandPersonality",
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/brand-personalities/{node_id}",
    response_model=BrandPersonalityResponse,
)
async def update_brand_personality(
    account_id: str,
    node_id: str,
    updates: BrandPersonalityUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandPersonalityResponse:
    """Update a brand personality."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="BrandPersonality",
        update_data=updates,
        service_method=service.update_brand_personality,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/brand-personalities/{node_id}", response_model=DeleteResponse
)
async def delete_brand_personality(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a brand personality."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="BrandPersonality",
        service_method=service.delete_brand_personality,
        service=service,
        user=user,
    )


# ==================== VOICE AND TONE ENDPOINTS ====================


@router.post("/{account_id}/voice-and-tone", response_model=VoiceAndToneResponse)
async def create_voice_and_tone(
    account_id: str,
    voice_and_tone: VoiceAndToneCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> VoiceAndToneResponse:
    """Create a new voice and tone.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="VoiceAndTone",
        create_data=voice_and_tone,
        service_method=service.create_voice_and_tone,
        service=service,
        user=user,
    )


@router.get("/{account_id}/voice-and-tone", response_model=VoiceAndToneListResponse)
async def list_voice_and_tone(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> VoiceAndToneListResponse:
    """List all voice and tone entries with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="VoiceAndTone",
        list_response_class=VoiceAndToneListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/voice-and-tone/{node_id}", response_model=VoiceAndToneResponse
)
async def get_voice_and_tone(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> VoiceAndToneResponse:
    """Get a specific voice and tone by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="VoiceAndTone",
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/voice-and-tone/{node_id}", response_model=VoiceAndToneResponse
)
async def update_voice_and_tone(
    account_id: str,
    node_id: str,
    updates: VoiceAndToneUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> VoiceAndToneResponse:
    """Update voice and tone."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="VoiceAndTone",
        update_data=updates,
        service_method=service.update_voice_and_tone,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/voice-and-tone/{node_id}", response_model=DeleteResponse)
async def delete_voice_and_tone(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete voice and tone."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="VoiceAndTone",
        service_method=service.delete_voice_and_tone,
        service=service,
        user=user,
    )


# ==================== COLOR PALETTE ENDPOINTS ====================


@router.post("/{account_id}/color-palettes", response_model=ColorPaletteResponse)
async def create_color_palette(
    account_id: str,
    color_palette: ColorPaletteCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ColorPaletteResponse:
    """Create a new color palette.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ColorPalette",
        create_data=color_palette,
        service_method=service.create_color_palette,
        service=service,
        user=user,
    )


@router.get("/{account_id}/color-palettes", response_model=ColorPaletteListResponse)
async def list_color_palettes(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ColorPaletteListResponse:
    """List all color palettes with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ColorPalette",
        list_response_class=ColorPaletteListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/color-palettes/{node_id}", response_model=ColorPaletteResponse
)
async def get_color_palette(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ColorPaletteResponse:
    """Get a specific color palette by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ColorPalette",
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/color-palettes/{node_id}", response_model=ColorPaletteResponse
)
async def update_color_palette(
    account_id: str,
    node_id: str,
    updates: ColorPaletteUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ColorPaletteResponse:
    """Update a color palette."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ColorPalette",
        update_data=updates,
        service_method=service.update_color_palette,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/color-palettes/{node_id}", response_model=DeleteResponse)
async def delete_color_palette(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a color palette."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ColorPalette",
        service_method=service.delete_color_palette,
        service=service,
        user=user,
    )


# ==================== TYPOGRAPHY ENDPOINTS ====================


@router.post("/{account_id}/typography", response_model=TypographyResponse)
async def create_typography(
    account_id: str,
    typography: TypographyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> TypographyResponse:
    """Create a new typography.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="Typography",
        create_data=typography,
        service_method=service.create_typography,
        service=service,
        user=user,
    )


@router.get("/{account_id}/typography", response_model=TypographyListResponse)
async def list_typography(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> TypographyListResponse:
    """List all typography entries with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="Typography",
        list_response_class=TypographyListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/typography/{node_id}", response_model=TypographyResponse)
async def get_typography(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> TypographyResponse:
    """Get a specific typography by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Typography",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/typography/{node_id}", response_model=TypographyResponse)
async def update_typography(
    account_id: str,
    node_id: str,
    updates: TypographyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> TypographyResponse:
    """Update typography."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Typography",
        update_data=updates,
        service_method=service.update_typography,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/typography/{node_id}", response_model=DeleteResponse)
async def delete_typography(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete typography."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="Typography",
        service_method=service.delete_typography,
        service=service,
        user=user,
    )


# ==================== IMAGE STYLE ENDPOINTS ====================


@router.post("/{account_id}/image-styles", response_model=ImageStyleResponse)
async def create_image_style(
    account_id: str,
    image_style: ImageStyleCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ImageStyleResponse:
    """Create a new image style.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ImageStyle",
        create_data=image_style,
        service_method=service.create_image_style,
        service=service,
        user=user,
    )


@router.get("/{account_id}/image-styles", response_model=ImageStyleListResponse)
async def list_image_styles(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ImageStyleListResponse:
    """List all image styles with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ImageStyle",
        list_response_class=ImageStyleListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/image-styles/{node_id}", response_model=ImageStyleResponse)
async def get_image_style(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ImageStyleResponse:
    """Get a specific image style by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ImageStyle",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/image-styles/{node_id}", response_model=ImageStyleResponse)
async def update_image_style(
    account_id: str,
    node_id: str,
    updates: ImageStyleUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ImageStyleResponse:
    """Update an image style."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ImageStyle",
        update_data=updates,
        service_method=service.update_image_style,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/image-styles/{node_id}", response_model=DeleteResponse)
async def delete_image_style(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete an image style."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ImageStyle",
        service_method=service.delete_image_style,
        service=service,
        user=user,
    )


# ==================== MISSION AND VALUES ENDPOINTS ====================


@router.post(
    "/{account_id}/mission-and-values", response_model=MissionAndValuesResponse
)
async def create_mission_and_values(
    account_id: str,
    mission_and_values: MissionAndValuesCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> MissionAndValuesResponse:
    """Create a new mission and values.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="MissionAndValues",
        create_data=mission_and_values,
        service_method=service.create_mission_and_values,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/mission-and-values", response_model=MissionAndValuesListResponse
)
async def list_mission_and_values(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> MissionAndValuesListResponse:
    """List all mission and values entries with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="MissionAndValues",
        list_response_class=MissionAndValuesListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/mission-and-values/{node_id}",
    response_model=MissionAndValuesResponse,
)
async def get_mission_and_values(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> MissionAndValuesResponse:
    """Get a specific mission and values by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="MissionAndValues",
        service=service,
        user=user,
    )


@router.patch(
    "/{account_id}/mission-and-values/{node_id}",
    response_model=MissionAndValuesResponse,
)
async def update_mission_and_values(
    account_id: str,
    node_id: str,
    updates: MissionAndValuesUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> MissionAndValuesResponse:
    """Update mission and values."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="MissionAndValues",
        update_data=updates,
        service_method=service.update_mission_and_values,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/mission-and-values/{node_id}", response_model=DeleteResponse
)
async def delete_mission_and_values(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete mission and values."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="MissionAndValues",
        service_method=service.delete_mission_and_values,
        service=service,
        user=user,
    )


# ==================== BRAND IDENTITY ENDPOINTS ====================
# Note: BrandIdentity is a hub node with max_per_account=1.
# Only GET and PATCH operations are supported (no CREATE/DELETE service methods).


@router.get("/{account_id}/brand-identity", response_model=BrandIdentityResponse)
async def get_brand_identity(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandIdentityResponse:
    """Get the brand identity hub node.

    Note: There should only be one brand identity node per account.
    """
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=f"{account_id}_brand_identity",
        node_type="BrandIdentity",
        service=service,
        user=user,
    )


@router.patch("/{account_id}/brand-identity", response_model=BrandIdentityResponse)
async def update_brand_identity(
    account_id: str,
    updates: BrandIdentityUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BrandIdentityResponse:
    """Update the brand identity hub node."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=f"{account_id}_brand_identity",
        node_type="BrandIdentity",
        update_data=updates,
        service_method=service.update_brand_identity,
        service=service,
        user=user,
    )
