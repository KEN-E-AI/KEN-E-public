"""Unit tests for graph model validation."""

from datetime import datetime

import pytest
from pydantic import ValidationError
from src.kene_api.models.graph_models import ProductResponse, ValuePropositionResponse


class TestProductResponse:
    """Tests for ProductResponse model validation."""

    def test_product_response_with_valid_url(self):
        """Test ProductResponse accepts valid HTTP(S) URLs."""
        product = ProductResponse(
            node_id="prod_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            product_name="Test Product",
            description="Test description",
            references=[],
            product_detail_page="https://example.com/product",
            category_node_id="cat_test",
        )
        assert product.product_detail_page == "https://example.com/product"

    def test_product_response_with_http_url(self):
        """Test ProductResponse accepts HTTP URLs."""
        product = ProductResponse(
            node_id="prod_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            product_name="Test Product",
            description="Test description",
            references=[],
            product_detail_page="http://example.com/product",
            category_node_id="cat_test",
        )
        assert product.product_detail_page == "http://example.com/product"

    def test_product_response_with_none_url(self):
        """Test ProductResponse accepts None for product_detail_page."""
        product = ProductResponse(
            node_id="prod_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            product_name="Test Product",
            description="Test description",
            references=[],
            product_detail_page=None,
            category_node_id="cat_test",
        )
        assert product.product_detail_page is None

    def test_product_response_with_invalid_url(self):
        """Test ProductResponse rejects invalid URLs."""
        with pytest.raises(ValidationError) as exc_info:
            ProductResponse(
                node_id="prod_test_123",
                account_id="acc_test",
                created_time=datetime.now(),
                last_modified=datetime.now(),
                created_by="user_test",
                last_modified_by="user_test",
                product_name="Test Product",
                description="Test description",
                references=[],
                product_detail_page="not-a-valid-url",
                category_node_id="cat_test",
            )
        assert "must be a valid HTTP(S) URL" in str(exc_info.value)

    def test_product_response_strips_whitespace_from_url(self):
        """Test ProductResponse strips whitespace from URLs."""
        product = ProductResponse(
            node_id="prod_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            product_name="Test Product",
            description="Test description",
            references=[],
            product_detail_page="  https://example.com/product  ",
            category_node_id="cat_test",
        )
        assert product.product_detail_page == "https://example.com/product"


class TestValuePropositionResponse:
    """Tests for ValuePropositionResponse model validation."""

    def test_value_proposition_with_both_parent_fields(self):
        """Test ValuePropositionResponse accepts both parent fields together."""
        vp = ValuePropositionResponse(
            node_id="vp_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            display_name="Test VP",
            description="Test description",
            references=[],
            parent_node_id="prod_test_123",
            parent_node_type="Product",
        )
        assert vp.parent_node_id == "prod_test_123"
        assert vp.parent_node_type == "Product"

    def test_value_proposition_with_both_parent_fields_none(self):
        """Test ValuePropositionResponse accepts both parent fields as None."""
        vp = ValuePropositionResponse(
            node_id="vp_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            display_name="Test VP",
            description="Test description",
            references=[],
            parent_node_id=None,
            parent_node_type=None,
        )
        assert vp.parent_node_id is None
        assert vp.parent_node_type is None

    def test_value_proposition_with_valid_parent_types(self):
        """Test ValuePropositionResponse accepts all valid parent types."""
        valid_types = ["Product", "ProductCategory", "Account"]
        for parent_type in valid_types:
            vp = ValuePropositionResponse(
                node_id="vp_test_123",
                account_id="acc_test",
                created_time=datetime.now(),
                last_modified=datetime.now(),
                created_by="user_test",
                last_modified_by="user_test",
                display_name="Test VP",
                description="Test description",
                references=[],
                parent_node_id="parent_test_123",
                parent_node_type=parent_type,
            )
            assert vp.parent_node_type == parent_type

    def test_value_proposition_with_invalid_parent_type(self):
        """Test ValuePropositionResponse rejects invalid parent types."""
        with pytest.raises(ValidationError) as exc_info:
            ValuePropositionResponse(
                node_id="vp_test_123",
                account_id="acc_test",
                created_time=datetime.now(),
                last_modified=datetime.now(),
                created_by="user_test",
                last_modified_by="user_test",
                display_name="Test VP",
                description="Test description",
                references=[],
                parent_node_id="parent_test_123",
                parent_node_type="InvalidType",
            )
        assert "must be one of" in str(exc_info.value)

    def test_value_proposition_with_parent_type_but_no_id(self):
        """Test ValuePropositionResponse rejects parent_node_type without parent_node_id."""
        with pytest.raises(ValidationError) as exc_info:
            ValuePropositionResponse(
                node_id="vp_test_123",
                account_id="acc_test",
                created_time=datetime.now(),
                last_modified=datetime.now(),
                created_by="user_test",
                last_modified_by="user_test",
                display_name="Test VP",
                description="Test description",
                references=[],
                parent_node_id=None,
                parent_node_type="Product",
            )
        assert "Both fields must be present together" in str(exc_info.value)

    def test_value_proposition_with_empty_parent_id(self):
        """Test ValuePropositionResponse treats empty string parent_node_id as None."""
        vp = ValuePropositionResponse(
            node_id="vp_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            display_name="Test VP",
            description="Test description",
            references=[],
            parent_node_id="   ",
            parent_node_type=None,
        )
        assert vp.parent_node_id is None

    def test_value_proposition_strips_whitespace_from_parent_id(self):
        """Test ValuePropositionResponse strips whitespace from parent_node_id."""
        vp = ValuePropositionResponse(
            node_id="vp_test_123",
            account_id="acc_test",
            created_time=datetime.now(),
            last_modified=datetime.now(),
            created_by="user_test",
            last_modified_by="user_test",
            display_name="Test VP",
            description="Test description",
            references=[],
            parent_node_id="  prod_test_123  ",
            parent_node_type="Product",
        )
        assert vp.parent_node_id == "prod_test_123"
