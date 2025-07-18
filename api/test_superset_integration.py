#!/usr/bin/env python3
"""
Test script to validate Superset integration implementation.
This script checks that our code is syntactically correct and imports work.
"""

import sys
import os

# Add the API source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_imports():
    """Test that all our imports work correctly."""
    try:
        from kene_api.config import settings

        print("✓ Config import successful")

        # Test that Superset settings are available
        assert hasattr(settings, "superset_base_url")
        assert hasattr(settings, "superset_username")
        assert hasattr(settings, "superset_password")
        print("✓ Superset settings available in config")

        from kene_api.superset import SupersetClient, SupersetClientError

        print("✓ Superset client import successful")

        # Test that we can instantiate the client
        client = SupersetClient()
        print("✓ SupersetClient can be instantiated")

        from kene_api.models.kene_models import Metric, MetricRequest

        print("✓ Model imports successful")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_model_structure():
    """Test that our models have the expected fields."""
    try:
        from kene_api.models.kene_models import Metric, MetricRequest

        # Check that Metric model has expected fields (but not superset_metric_id since it's in relationship)
        metric_fields = Metric.model_fields
        assert "metric_name" in metric_fields
        assert "verbose_name" in metric_fields
        assert "expression" in metric_fields
        assert (
            "superset_metric_id" not in metric_fields
        )  # Should not be in model anymore
        print("✓ Metric model structure is correct (superset_metric_id removed)")

        # Check that MetricRequest model has expected fields (but not superset_metric_id)
        request_fields = MetricRequest.model_fields
        assert "metric_name" in request_fields
        assert (
            "superset_metric_id" not in request_fields
        )  # Should not be in model anymore
        print("✓ MetricRequest model structure is correct (superset_metric_id removed)")

        return True

    except Exception as e:
        print(f"✗ Model structure error: {e}")
        return False


def test_superset_client_methods():
    """Test that SupersetClient has all expected methods."""
    try:
        from kene_api.superset import SupersetClient

        client = SupersetClient()

        # Check that all required methods exist
        required_methods = [
            "authenticate",
            "get_dataset",
            "create_metric",
            "update_metric",
            "delete_metric",
            "health_check",
            "find_metric_by_name",
        ]

        for method in required_methods:
            assert hasattr(client, method), f"Missing method: {method}"
            print(f"✓ SupersetClient has {method} method")

        return True

    except Exception as e:
        print(f"✗ SupersetClient method error: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing Superset Integration Implementation")
    print("=" * 50)

    tests = [test_imports, test_model_structure, test_superset_client_methods]

    all_passed = True
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if not test():
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("✓ All tests passed! Superset integration is ready.")
        return 0
    else:
        print("✗ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
