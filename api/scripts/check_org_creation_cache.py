#!/usr/bin/env python
"""Test script to verify organization creation cache invalidation fix."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.auth.cached_user_context import get_cached_user_context_service
from src.kene_api.auth.firebase_admin import initialize_firebase_admin
from src.kene_api.firestore import get_firestore_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_cache_invalidation():
    """Test that cache is properly invalidated after organization creation."""
    
    # Initialize Firebase
    initialize_firebase_admin()
    
    # Get services
    cached_user_service = get_cached_user_context_service()
    firestore_service = get_firestore_service()
    
    # Test user ID (you can replace with a real user ID)
    test_user_id = "test_user_123"
    test_org_id = "test_org_456"
    
    logger.info(f"Testing cache invalidation for user {test_user_id}")
    
    # Check if user has cached context
    cached_context = cached_user_service.get_user_context(test_user_id)
    if cached_context:
        logger.info(f"Found cached context for user: {cached_context.organization_permissions}")
    else:
        logger.info("No cached context found for user")
    
    # Simulate granting organization permission
    logger.info(f"Simulating grant of admin permission for org {test_org_id}")
    
    # This would normally be done in the organization creation endpoint
    success = firestore_service.set_nested_field(
        collection="users",
        document_id=test_user_id,
        field_path=f"permissions.organizations.{test_org_id}",
        value="admin",
    )
    
    if success:
        logger.info("Permission granted successfully")
        
        # Now invalidate the cache (this is the fix we added)
        cached_user_service.invalidate_user_context(test_user_id)
        logger.info("Cache invalidated")
        
        # Check if cache is cleared
        cached_context = cached_user_service.get_user_context(test_user_id)
        if cached_context:
            logger.warning("Cache still exists after invalidation (shouldn't happen)")
        else:
            logger.info("✅ Cache successfully cleared after invalidation")
    else:
        logger.error("Failed to grant permission")
    
    # Clean up - remove test permission
    try:
        firestore_db = firestore_service.get_client()
        user_ref = firestore_db.collection("users").document(test_user_id)
        from google.cloud.firestore_v1 import DELETE_FIELD
        user_ref.update({f"permissions.organizations.{test_org_id}": DELETE_FIELD})
        logger.info("Cleaned up test permission")
    except Exception as e:
        logger.warning(f"Failed to clean up test permission: {e}")


if __name__ == "__main__":
    asyncio.run(test_cache_invalidation())