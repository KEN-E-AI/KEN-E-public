#!/usr/bin/env python3
"""Test the enhanced JSON parser with various messy inputs."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.strategy_agent.enhanced_json_parser import EnhancedJsonParser


def test_parser():
    """Test the enhanced JSON parser with different scenarios."""

    parser = EnhancedJsonParser()

    # Test cases
    test_cases = [
        {
            "name": "Clean JSON",
            "input": '{"key": "value", "number": 42}',
            "expected": {"key": "value", "number": 42},
        },
        {
            "name": "Markdown-wrapped JSON",
            "input": """```json
{
    "title": "Test Strategy",
    "sections": ["intro", "body", "conclusion"],
    "valid": true
}
```""",
            "expected": {
                "title": "Test Strategy",
                "sections": ["intro", "body", "conclusion"],
                "valid": True,
            },
        },
        {
            "name": "JSON with narrative text",
            "input": """Here is the strategy document I've created:

{
    "document_type": "marketing_strategy",
    "content": "This is the main content",
    "status": "complete"
}

This document provides comprehensive guidance.""",
            "expected": {
                "document_type": "marketing_strategy",
                "content": "This is the main content",
                "status": "complete",
            },
        },
        {
            "name": "Markdown with extra text",
            "input": """I'll create a strategy document for you:

```json
{
    "company": "TechCorp",
    "strategy": {
        "focus": "digital transformation",
        "budget": 100000
    }
}
```

This strategy focuses on key areas.""",
            "expected": {
                "company": "TechCorp",
                "strategy": {"focus": "digital transformation", "budget": 100000},
            },
        },
    ]

    # Run tests
    passed = 0
    failed = 0

    for test in test_cases:
        print(f"\nTesting: {test['name']}")
        print(f"Input preview: {test['input'][:50]}...")

        try:
            result = parser.parse_json(test["input"])

            if result == test["expected"]:
                print("✅ PASSED")
                passed += 1
            else:
                print("❌ FAILED - Result mismatch")
                print(f"   Expected: {test['expected']}")
                print(f"   Got: {result}")
                failed += 1

        except Exception as e:
            print(f"❌ FAILED with exception: {e}")
            failed += 1

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Test Results: {passed} passed, {failed} failed")
    print(f"{'=' * 50}")

    return failed == 0


if __name__ == "__main__":
    success = test_parser()
    sys.exit(0 if success else 1)
