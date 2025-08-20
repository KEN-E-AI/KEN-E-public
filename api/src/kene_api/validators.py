"""Validators for KEN-E API."""

import re
from typing import Optional

from pydantic import field_validator


class KeywordValidators:
    """Validators for keyword-related fields."""

    # Keyword constraints
    MIN_LENGTH = 2
    MAX_LENGTH = 100
    VALID_PATTERN = re.compile(r"^[\w\s\-\.&]+$", re.UNICODE)

    @classmethod
    def validate_keyword(cls, keyword: str) -> str:
        """Validate a single keyword.

        Args:
            keyword: The keyword to validate

        Returns:
            Normalized keyword

        Raises:
            ValueError: If keyword is invalid
        """
        # Trim whitespace
        keyword = keyword.strip()

        # Check length
        if len(keyword) < cls.MIN_LENGTH:
            raise ValueError(
                f"Keyword must be at least {cls.MIN_LENGTH} characters long"
            )
        if len(keyword) > cls.MAX_LENGTH:
            raise ValueError(f"Keyword must not exceed {cls.MAX_LENGTH} characters")

        # Check pattern (alphanumeric, spaces, hyphens, dots, ampersands)
        if not cls.VALID_PATTERN.match(keyword):
            raise ValueError(
                "Keyword contains invalid characters. "
                "Only letters, numbers, spaces, hyphens, dots, and ampersands are allowed"
            )

        # Check for excessive whitespace
        if "  " in keyword:
            raise ValueError("Keyword contains excessive whitespace")

        return keyword

    @classmethod
    def validate_keyword_list(cls, keywords: list[str]) -> list[str]:
        """Validate a list of keywords.

        Args:
            keywords: List of keywords to validate

        Returns:
            List of validated, unique keywords

        Raises:
            ValueError: If any keyword is invalid
        """
        if not keywords:
            return []

        # Validate each keyword
        validated = []
        seen_lower = set()

        for keyword in keywords:
            try:
                validated_keyword = cls.validate_keyword(keyword)
                # Check for duplicates (case-insensitive)
                keyword_lower = validated_keyword.lower()
                if keyword_lower not in seen_lower:
                    validated.append(validated_keyword)
                    seen_lower.add(keyword_lower)
            except ValueError as e:
                raise ValueError(f"Invalid keyword '{keyword}': {str(e)}")

        return validated

    @classmethod
    def field_validator_keyword_list(cls):
        """Create a Pydantic field validator for keyword lists."""

        @field_validator(
            "company_keywords", "customer_keywords", "keywords", mode="before"
        )
        def validate_keywords(v: Optional[list[str]]) -> list[str]:
            if v is None:
                return []
            return cls.validate_keyword_list(v)

        return validate_keywords


class CompetitorValidators:
    """Validators for competitor-related fields."""

    @classmethod
    def validate_website(cls, website: Optional[str]) -> Optional[str]:
        """Validate a website URL.

        Args:
            website: The website URL to validate

        Returns:
            Normalized website URL or None

        Raises:
            ValueError: If website is invalid
        """
        if not website:
            return None

        website = website.strip()

        # Return None for empty string after stripping
        if not website:
            return None

        # Basic URL validation
        if not website.startswith(("http://", "https://")):
            # Add https:// if no protocol specified
            website = f"https://{website}"

        # Check for basic URL structure
        url_pattern = re.compile(
            r"^https?://"  # Protocol
            r"(?:[a-zA-Z0-9-]+\.)*"  # Subdomains
            r"[a-zA-Z0-9-]+"  # Domain
            r"(?:\.[a-zA-Z]{2,})"  # TLD
            r"(?:/.*)?$"  # Path (optional)
        )

        if not url_pattern.match(website):
            raise ValueError("Invalid website URL format")

        return website

    @classmethod
    def validate_competitor_name(cls, name: str) -> str:
        """Validate a competitor name.

        Args:
            name: The competitor name to validate

        Returns:
            Normalized name

        Raises:
            ValueError: If name is invalid
        """
        name = name.strip()

        if len(name) < 2:
            raise ValueError("Competitor name must be at least 2 characters long")
        if len(name) > 200:
            raise ValueError("Competitor name must not exceed 200 characters")

        # Allow more characters in names than keywords
        name_pattern = re.compile(r"^[\w\s\-\.&,\'\"]+$", re.UNICODE)
        if not name_pattern.match(name):
            raise ValueError("Competitor name contains invalid characters")

        return name
