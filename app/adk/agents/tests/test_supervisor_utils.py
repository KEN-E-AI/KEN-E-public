"""Test shared supervisor utilities."""

import json

from ..utils.supervisor_utils import dispatch_with_context, extract_tenant_context


def test_extract_tenant_context_from_string():
    """Test extracting tenant context from a plain string."""
    input_data = "This is a test message"
    tenant_id, tenant_context, message = extract_tenant_context(input_data)

    assert tenant_id is None
    assert tenant_context is None
    assert message == "This is a test message"


def test_extract_tenant_context_from_dict_with_message():
    """Test extracting tenant context from dict with 'message' key."""
    input_data = {
        "message": "Test message",
        "tenant_id": "test-tenant",
        "tenant_credentials": "test-creds",
    }
    tenant_id, tenant_context, message = extract_tenant_context(input_data)

    assert tenant_id == "test-tenant"
    assert tenant_context == {
        "tenant_id": "test-tenant",
        "tenant_credentials": "test-creds",
    }
    assert message == "Test message"


def test_extract_tenant_context_from_dict_with_query():
    """Test extracting tenant context from dict with 'query' key."""
    input_data = {
        "query": "Test query",
        "tenant_id": "test-tenant",
        "tenant_credentials": "test-creds",
    }
    tenant_id, tenant_context, message = extract_tenant_context(input_data)

    assert tenant_id == "test-tenant"
    assert tenant_context == {
        "tenant_id": "test-tenant",
        "tenant_credentials": "test-creds",
    }
    assert message == "Test query"


def test_extract_tenant_context_from_other_type():
    """Test extracting tenant context from non-string, non-dict type."""
    input_data = 12345
    tenant_id, tenant_context, message = extract_tenant_context(input_data)

    assert tenant_id is None
    assert tenant_context is None
    assert message == "12345"


def test_dispatch_with_context_wrapper():
    """Test the dispatch_with_context wrapper function."""

    # Create a mock dispatch function
    def mock_dispatch(message: str, tenant_context: dict | None = None):
        return {"result": f"Processed: {message}", "tenant": tenant_context}

    # Wrap it
    wrapped = dispatch_with_context(mock_dispatch)

    # Test with string input
    result = wrapped("test message")
    assert result == "Processed: test message"

    # Test with JSON input
    json_input = json.dumps(
        {
            "message": "json message",
            "tenant_id": "test-id",
            "tenant_credentials": "test-creds",
        }
    )
    result = wrapped(json_input)
    assert result == "Processed: json message"
