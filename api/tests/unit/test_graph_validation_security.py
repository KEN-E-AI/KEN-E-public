"""Security tests for graph validation service.

Tests that validate_node_type properly prevents Cypher injection attacks.
"""

import pytest
from src.kene_api.constants import VALID_NODE_TYPES
from src.kene_api.exceptions import ValidationException
from src.kene_api.services.graph_validation_service import validate_node_type


class TestNodeTypeValidation:
    """Test node type whitelist validation prevents injection."""

    def test_valid_node_types_accepted(self):
        """Valid node types should pass validation without raising."""
        valid_types = [
            "Product",
            "ProductCategory",
            "ValueProposition",
            "Strength",
            "Weakness",
            "Opportunity",
            "Risk",
            "Goal",
            "SWOTAnalysis",
            "Account",
        ]
        for node_type in valid_types:
            # Should not raise
            validate_node_type(node_type)

    def test_all_constant_node_types_accepted(self):
        """All node types in VALID_NODE_TYPES constant should pass."""
        for node_type in VALID_NODE_TYPES:
            # Should not raise
            validate_node_type(node_type)

    def test_invalid_node_type_rejected(self):
        """Invalid node types should raise ValidationException."""
        with pytest.raises(ValidationException) as exc_info:
            validate_node_type("MaliciousNode")

        assert "Invalid node type 'MaliciousNode'" in str(exc_info.value)
        assert exc_info.value.field_name == "node_type"

    def test_cypher_injection_attempt_blocked(self):
        """Cypher injection attempts should be blocked."""
        malicious_inputs = [
            # Attempt to delete nodes
            "Product) DETACH DELETE (n) //",
            # Attempt to match all nodes
            "Product{}) RETURN 1 //",
            # SQL-style injection
            "'; DROP DATABASE; --",
            # Cypher comment injection
            "Product) // malicious comment",
            # Property injection
            "Product {malicious: 'value'}",
            # Label injection with multiple labels
            "Product:Malicious",
            # Relationship injection
            "Product)-[:HACKED]->(",
            # WHERE clause injection
            "Product) WHERE 1=1 //",
        ]

        for malicious in malicious_inputs:
            with pytest.raises(ValidationException, match="Invalid node type"):
                validate_node_type(malicious)

    def test_empty_string_rejected(self):
        """Empty string should be rejected."""
        with pytest.raises(ValidationException):
            validate_node_type("")

    def test_none_raises_error(self):
        """None value should raise TypeError (not string)."""
        with pytest.raises((TypeError, ValidationException)):
            validate_node_type(None)  # type: ignore

    def test_case_sensitive_validation(self):
        """Node type validation should be case-sensitive."""
        # Only exact case should work
        validate_node_type("Product")  # Should not raise

        # Different case should fail
        with pytest.raises(ValidationException):
            validate_node_type("product")

        with pytest.raises(ValidationException):
            validate_node_type("PRODUCT")

    def test_whitespace_not_trimmed(self):
        """Whitespace should not be trimmed - exact match required."""
        with pytest.raises(ValidationException):
            validate_node_type(" Product")

        with pytest.raises(ValidationException):
            validate_node_type("Product ")

        with pytest.raises(ValidationException):
            validate_node_type(" Product ")

    def test_special_characters_rejected(self):
        """Special characters should be rejected."""
        special_chars = [
            "Product\n",
            "Product\t",
            "Product\r",
            "Product;",
            "Product'",
            'Product"',
            "Product`",
            "Product$",
            "Product{",
            "Product}",
            "Product(",
            "Product)",
            "Product[",
            "Product]",
        ]

        for special in special_chars:
            with pytest.raises(ValidationException):
                validate_node_type(special)

    def test_unicode_injection_blocked(self):
        """Unicode-based injection attempts should be blocked."""
        unicode_attempts = [
            "Product\u0000",  # Null byte
            "Product\u202e",  # Right-to-left override
            "Product\ufeff",  # Zero width no-break space
        ]

        for unicode_attempt in unicode_attempts:
            with pytest.raises(ValidationException):
                validate_node_type(unicode_attempt)

    def test_error_message_includes_valid_types(self):
        """Error message should include list of valid types."""
        with pytest.raises(ValidationException) as exc_info:
            validate_node_type("InvalidType")

        error_msg = str(exc_info.value)
        # Should mention some valid types
        assert "Product" in error_msg or "ProductCategory" in error_msg
        assert "Must be one of:" in error_msg
