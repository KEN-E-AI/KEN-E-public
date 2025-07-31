"""Tests for validators."""

import pytest

from src.kene_api.validators import CompetitorValidators, KeywordValidators


class TestKeywordValidators:
    """Test keyword validation functions."""
    
    def test_validate_keyword_valid(self):
        """Test validation of valid keywords."""
        valid_keywords = [
            "AI",
            "artificial intelligence",
            "machine-learning",
            "ML.AI",
            "R&D",
            "research & development",
            "2024",
            "GPT-4",
            "Test 123",
        ]
        
        for keyword in valid_keywords:
            result = KeywordValidators.validate_keyword(keyword)
            assert result == keyword.strip()
    
    def test_validate_keyword_strips_whitespace(self):
        """Test that validation strips whitespace."""
        assert KeywordValidators.validate_keyword("  test  ") == "test"
        assert KeywordValidators.validate_keyword("\ttest\n") == "test"
    
    def test_validate_keyword_too_short(self):
        """Test validation rejects short keywords."""
        with pytest.raises(ValueError, match="at least 2 characters"):
            KeywordValidators.validate_keyword("a")
        
        with pytest.raises(ValueError, match="at least 2 characters"):
            KeywordValidators.validate_keyword(" a ")
    
    def test_validate_keyword_too_long(self):
        """Test validation rejects long keywords."""
        long_keyword = "a" * 101
        with pytest.raises(ValueError, match="must not exceed 100 characters"):
            KeywordValidators.validate_keyword(long_keyword)
    
    def test_validate_keyword_invalid_characters(self):
        """Test validation rejects invalid characters."""
        invalid_keywords = [
            "test@email",
            "keyword#tag",
            "test!",
            "keyword?",
            "test/slash",
            "keyword\\backslash",
            "test<>",
            "keyword[]",
            "test{code}",
            "keyword|pipe",
        ]
        
        for keyword in invalid_keywords:
            with pytest.raises(ValueError, match="invalid characters"):
                KeywordValidators.validate_keyword(keyword)
    
    def test_validate_keyword_excessive_whitespace(self):
        """Test validation rejects excessive whitespace."""
        with pytest.raises(ValueError, match="excessive whitespace"):
            KeywordValidators.validate_keyword("test  keyword")
        
        with pytest.raises(ValueError, match="excessive whitespace"):
            KeywordValidators.validate_keyword("test   multiple   spaces")
    
    def test_validate_keyword_list_empty(self):
        """Test validation of empty keyword list."""
        assert KeywordValidators.validate_keyword_list([]) == []
    
    def test_validate_keyword_list_valid(self):
        """Test validation of valid keyword list."""
        keywords = ["AI", "Machine Learning", "deep-learning"]
        result = KeywordValidators.validate_keyword_list(keywords)
        assert result == keywords
    
    def test_validate_keyword_list_removes_duplicates(self):
        """Test validation removes case-insensitive duplicates."""
        keywords = ["AI", "ai", "Machine Learning", "MACHINE LEARNING", "deep-learning"]
        result = KeywordValidators.validate_keyword_list(keywords)
        assert len(result) == 3
        assert "AI" in result
        assert "Machine Learning" in result
        assert "deep-learning" in result
    
    def test_validate_keyword_list_preserves_case(self):
        """Test validation preserves original case of first occurrence."""
        keywords = ["Machine Learning", "machine learning", "MACHINE LEARNING"]
        result = KeywordValidators.validate_keyword_list(keywords)
        assert result == ["Machine Learning"]
    
    def test_validate_keyword_list_invalid_keyword(self):
        """Test validation fails with invalid keyword in list."""
        keywords = ["valid", "invalid@keyword", "another"]
        with pytest.raises(ValueError, match="Invalid keyword 'invalid@keyword'"):
            KeywordValidators.validate_keyword_list(keywords)


class TestCompetitorValidators:
    """Test competitor validation functions."""
    
    def test_validate_website_valid(self):
        """Test validation of valid websites."""
        valid_urls = [
            ("https://example.com", "https://example.com"),
            ("http://example.com", "http://example.com"),
            ("example.com", "https://example.com"),
            ("www.example.com", "https://www.example.com"),
            ("https://sub.example.com/path", "https://sub.example.com/path"),
        ]
        
        for input_url, expected in valid_urls:
            result = CompetitorValidators.validate_website(input_url)
            assert result == expected
    
    def test_validate_website_none_or_empty(self):
        """Test validation handles None and empty strings."""
        assert CompetitorValidators.validate_website(None) is None
        assert CompetitorValidators.validate_website("") is None
        assert CompetitorValidators.validate_website("  ") is None
    
    def test_validate_website_invalid(self):
        """Test validation rejects invalid URLs."""
        invalid_urls = [
            "not a url",
            "javascript:alert(1)",
            "ftp://example.com",
            "example",
            "http://",
            "https://",
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid website URL"):
                CompetitorValidators.validate_website(url)
    
    def test_validate_competitor_name_valid(self):
        """Test validation of valid competitor names."""
        valid_names = [
            "Google",
            "Microsoft Corporation",
            "Tesla, Inc.",
            "AT&T",
            "Johnson & Johnson",
            "O'Reilly Media",
            'Company "ABC"',
            "Test's Company",
        ]
        
        for name in valid_names:
            result = CompetitorValidators.validate_competitor_name(name)
            assert result == name.strip()
    
    def test_validate_competitor_name_too_short(self):
        """Test validation rejects short names."""
        with pytest.raises(ValueError, match="at least 2 characters"):
            CompetitorValidators.validate_competitor_name("A")
    
    def test_validate_competitor_name_too_long(self):
        """Test validation rejects long names."""
        long_name = "A" * 201
        with pytest.raises(ValueError, match="must not exceed 200 characters"):
            CompetitorValidators.validate_competitor_name(long_name)
    
    def test_validate_competitor_name_invalid_characters(self):
        """Test validation rejects invalid characters in names."""
        invalid_names = [
            "Company@email",
            "Test#Corp",
            "Company!",
            "Test?Inc",
            "Company<>",
            "Test[]Corp",
        ]
        
        for name in invalid_names:
            with pytest.raises(ValueError, match="invalid characters"):
                CompetitorValidators.validate_competitor_name(name)