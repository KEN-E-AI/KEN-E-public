"""User management endpoints with proper authentication."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from google.cloud import firestore

from ..auth.user_context import UserContext, get_current_user_context
from ..firestore import get_firestore_service


router = APIRouter(tags=["users"])


class UserProfile(BaseModel):
    """User profile model."""

    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    email_verified: bool = False


class UserResponse(BaseModel):
    """User response model."""

    uid: str
    email: str
    profile: UserProfile
    permissions: dict[str, dict[str, str]] = Field(
        default_factory=lambda: {"accounts": {}, "organizations": {}}
    )
    created_at: Optional[str] = None
    is_super_admin: bool = False


class NotificationSettings(BaseModel):
    """Notification settings model."""

    email_notifications: bool = True
    push_notifications: bool = False
    weekly_digest: bool = True
    marketing_updates: bool = False


class SecuritySettings(BaseModel):
    """Security settings model."""

    two_factor_enabled: bool = False
    last_login: Optional[str] = None
    login_count: int = 0


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    current_user: UserContext = Depends(get_current_user_context),
    firestore_service=Depends(get_firestore_service),
) -> UserResponse:
    """Get current user's profile."""
    firestore_db = firestore_service.get_client()

    # Get user document
    user_doc = firestore_db.collection("users").document(current_user.user_id).get()

    if not user_doc.exists:
        # Create user if doesn't exist
        user_data = {
            "uid": current_user.user_id,
            "email": current_user.email,
            "profile": {
                "email": current_user.email,
                "email_verified": False,
            },
            "permissions": {
                "accounts": {},
                "organizations": {},
            },
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        firestore_db.collection("users").document(current_user.user_id).set(user_data)

        # Also create default notification and security settings
        default_notifications = NotificationSettings()
        firestore_db.collection("users").document(current_user.user_id).collection(
            "notifications"
        ).document("settings").set(default_notifications.dict())

        default_security = SecuritySettings()
        firestore_db.collection("users").document(current_user.user_id).collection(
            "security"
        ).document("settings").set(default_security.dict())

        # Create notification preferences for the notification system
        default_preferences = {
            "categories": [
                "Data Quality Alert",
                "News & Press",
                "Industry News",
                "Competitor Activities",
                "Scheduled Report Status",
                "KPI Performance",
                "New Features",
            ],
            "channels": ["ui"],
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        firestore_db.collection("users").document(current_user.user_id).collection(
            "preferences"
        ).document("notifications").set(default_preferences)

        return UserResponse(
            uid=current_user.user_id,
            email=current_user.email,
            profile=UserProfile(email=current_user.email),
            permissions={"accounts": {}, "organizations": {}},
            is_super_admin=current_user.is_super_admin,
        )

    user_data = user_doc.to_dict()
    profile_data = user_data.get("profile", {})

    return UserResponse(
        uid=current_user.user_id,
        email=current_user.email,
        profile=UserProfile(
            email=profile_data.get("email", current_user.email),
            first_name=profile_data.get("first_name"),
            last_name=profile_data.get("last_name"),
            job_title=profile_data.get("job_title"),
            email_verified=profile_data.get("email_verified", False),
        ),
        permissions=user_data.get("permissions", {"accounts": {}, "organizations": {}}),
        created_at=user_data.get("created_at"),
        is_super_admin=current_user.is_super_admin,
    )


@router.put("/me/profile", response_model=UserResponse)
async def update_user_profile(
    request: Request,
    profile: UserProfile,
    current_user: UserContext = Depends(get_current_user_context),
    firestore_service=Depends(get_firestore_service),
) -> UserResponse:
    """Update current user's profile."""
    firestore_db = firestore_service.get_client()

    # Update user profile
    firestore_db.collection("users").document(current_user.user_id).update(
        {
            "profile": profile.dict(),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )

    return await get_current_user(request, current_user, firestore_service)


@router.get("/me/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    request: Request,
    current_user: UserContext = Depends(get_current_user_context),
    firestore_service=Depends(get_firestore_service),
) -> NotificationSettings:
    """Get current user's notification settings."""
    firestore_db = firestore_service.get_client()

    # Get notification settings
    settings_doc = (
        firestore_db.collection("users")
        .document(current_user.user_id)
        .collection("notifications")
        .document("settings")
        .get()
    )

    if not settings_doc.exists:
        # Return defaults
        return NotificationSettings()

    return NotificationSettings(**settings_doc.to_dict())


@router.put("/me/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    request: Request,
    settings: NotificationSettings,
    current_user: UserContext = Depends(get_current_user_context),
    firestore_service=Depends(get_firestore_service),
) -> NotificationSettings:
    """Update current user's notification settings."""
    firestore_db = firestore_service.get_client()

    # Update notification settings
    firestore_db.collection("users").document(current_user.user_id).collection(
        "notifications"
    ).document("settings").set(settings.dict())

    return settings


@router.get("/me/security", response_model=SecuritySettings)
async def get_security_settings(
    request: Request,
    current_user: UserContext = Depends(get_current_user_context),
    firestore_service=Depends(get_firestore_service),
) -> SecuritySettings:
    """Get current user's security settings."""
    firestore_db = firestore_service.get_client()

    # Get security settings
    settings_doc = (
        firestore_db.collection("users")
        .document(current_user.user_id)
        .collection("security")
        .document("settings")
        .get()
    )

    if not settings_doc.exists:
        # Return defaults
        return SecuritySettings()

    return SecuritySettings(**settings_doc.to_dict())


@router.put("/me/security", response_model=SecuritySettings)
async def update_security_settings(
    request: Request,
    settings: SecuritySettings,
    current_user: UserContext = Depends(get_current_user_context),
    firestore_service=Depends(get_firestore_service),
) -> SecuritySettings:
    """Update current user's security settings."""
    firestore_db = firestore_service.get_client()

    # Update security settings
    firestore_db.collection("users").document(current_user.user_id).collection(
        "security"
    ).document("settings").set(settings.dict())

    return settings
