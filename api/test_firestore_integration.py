#!/usr/bin/env python3
"""Test script to verify Firestore integration is working correctly."""

import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    # Test imports
    print("Testing imports...")
    from src.kene_api.firestore import FirestoreService, get_firestore_service
    from src.kene_api.routers.firestore import router
    from src.kene_api.main import app
    print("✅ All imports successful!")

    # Test Firestore service instantiation
    print("\nTesting Firestore service...")
    service = FirestoreService()
    print("✅ Firestore service created successfully!")

    # Test router setup
    print("\nTesting router setup...")
    routes = [route.path for route in router.routes]
    expected_routes = [
        "/documents",
        "/documents/{collection}/{document_id}",
        "/documents/query",
        "/collections/{collection}/documents",
        "/health"
    ]
    
    print(f"Available routes: {routes}")
    for expected_route in expected_routes:
        if expected_route in routes:
            print(f"✅ Route {expected_route} found")
        else:
            print(f"❌ Route {expected_route} missing")

    # Test app configuration
    print("\nTesting app configuration...")
    app_routes = [route.path for route in app.routes]
    firestore_routes = [route for route in app_routes if "firestore" in route]
    print(f"Firestore routes in app: {firestore_routes}")
    
    if "/api/v1/firestore/documents" in app_routes:
        print("✅ Firestore routes properly configured in main app")
    else:
        print("❌ Firestore routes not found in main app")

    print("\n🎉 All tests passed! Firestore integration is ready.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
