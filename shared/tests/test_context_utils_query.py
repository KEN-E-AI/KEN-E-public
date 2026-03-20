"""Tests for ORG_CONTEXT_QUERY and extract_context_from_result."""

import pytest

from shared.context_utils import (
    ORG_CONTEXT_QUERY,
    extract_context_from_result,
    format_context_markdown,
)

ACCOUNT_FIELDS = [
    "account_id",
    "company_name",
    "company_overview",
    "industry",
    "websites",
    "customer_regions",
]

BRAND_FIELDS = [
    "voice_tone",
    "do_list",
    "dont_list",
    "personality_traits",
    "mission",
    "values",
]


class TestOrgContextQuery:

    @pytest.mark.parametrize("field", ACCOUNT_FIELDS)
    def test_query_contains_account_field(self, field: str):
        assert field in ORG_CONTEXT_QUERY

    @pytest.mark.parametrize("field", BRAND_FIELDS)
    def test_query_contains_brand_field(self, field: str):
        assert field in ORG_CONTEXT_QUERY


class TestExtractContextFromResult:

    def test_valid_result(self):
        result = [{"context": {"account": {"company_name": "Acme"}, "brand": {}}}]
        assert extract_context_from_result(result) == {
            "account": {"company_name": "Acme"},
            "brand": {},
        }

    def test_empty_list(self):
        assert extract_context_from_result([]) is None

    def test_none_first_element(self):
        assert extract_context_from_result([None]) is None

    def test_empty_dict_first_element(self):
        assert extract_context_from_result([{}]) is None


class TestFormatConsistency:

    def test_full_context_contains_all_sections(self):
        context = {
            "account": {
                "account_id": "acc_123",
                "company_name": "TestCo",
                "company_overview": "A test company",
                "industry": "Technology",
                "websites": ["https://testco.com"],
                "customer_regions": ["US", "EU"],
            },
            "brand": {
                "voice_tone": ["Professional", "Friendly"],
                "do_list": ["Be clear", "Be concise"],
                "dont_list": ["Use jargon"],
                "personality_traits": ["Innovative"],
                "mission": "Make testing great",
                "values": ["Quality", "Speed"],
            },
        }
        md = format_context_markdown(context)

        assert "TestCo" in md
        assert "Technology" in md
        assert "Company Context" in md
        assert "Brand Voice" in md
        assert "Professional" in md
        assert "Be clear" in md
        assert "Use jargon" in md
        assert "Innovative" in md
        assert "Make testing great" in md
        assert "Quality" in md
