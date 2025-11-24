"""Reusable validators for API models."""

import re


class KeywordValidators:
    """Validators for keyword-related fields."""

    # Keyword constraints
    MIN_LENGTH = 2
    MAX_LENGTH = 50
    MAX_COUNT = 20
    VALID_PATTERN = re.compile(r"^[\w\s\-\.&]+$", re.UNICODE)

    @classmethod
    def validate_keyword(cls, keyword: str) -> str:
        """Validate a single keyword.

        Args:
            keyword: The keyword to validate

        Returns:
            The validated and normalized keyword

        Raises:
            ValueError: If the keyword is invalid
        """
        keyword = keyword.strip()

        if len(keyword) < cls.MIN_LENGTH:
            raise ValueError(
                f"Keyword must be at least {cls.MIN_LENGTH} characters long"
            )
        if len(keyword) > cls.MAX_LENGTH:
            raise ValueError(f"Keyword must not exceed {cls.MAX_LENGTH} characters")

        if not cls.VALID_PATTERN.match(keyword):
            raise ValueError(
                "Keyword contains invalid characters. "
                "Only letters, numbers, spaces, hyphens, dots, and ampersands are allowed"
            )

        if "  " in keyword:
            raise ValueError("Keyword contains excessive whitespace")

        return keyword

    @classmethod
    def validate_keyword_list(cls, keywords: list[str]) -> list[str]:
        """Validate a list of keywords.

        Args:
            keywords: List of keywords to validate

        Returns:
            List of validated keywords with duplicates removed

        Raises:
            ValueError: If any keyword is invalid or list exceeds max count
        """
        if not keywords:
            return []

        if len(keywords) > cls.MAX_COUNT:
            raise ValueError(f"Cannot have more than {cls.MAX_COUNT} keywords")

        validated = []
        seen_lower = set()

        for keyword in keywords:
            try:
                validated_keyword = cls.validate_keyword(keyword)
                keyword_lower = validated_keyword.lower()
                if keyword_lower not in seen_lower:
                    validated.append(validated_keyword)
                    seen_lower.add(keyword_lower)
            except ValueError as e:
                raise ValueError(f"Invalid keyword '{keyword}': {e!s}") from e

        return validated


class URLValidators:
    """Validators for URL-related fields."""

    @classmethod
    def validate_website_url(cls, url: str | None) -> str | None:
        """Validate a website URL.

        Args:
            url: The URL to validate (optional)

        Returns:
            The validated URL with protocol added if needed, or None

        Raises:
            ValueError: If the URL format is invalid
        """
        if not url:
            return None

        url = url.strip()

        if not url:
            return None

        # Add https:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Basic URL structure validation
        url_pattern = re.compile(
            r"^https?://"
            r"(?:[a-zA-Z0-9-]+\.)*"
            r"[a-zA-Z0-9-]+"
            r"(?:\.[a-zA-Z]{2,})"
            r"(?:/.*)?$"
        )

        if not url_pattern.match(url):
            raise ValueError("Invalid website URL format")

        return url


class CompetitorValidators:
    """Validators for competitor-related fields."""

    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 200

    @classmethod
    def validate_competitor_name(cls, name: str) -> str:
        """Validate a competitor name.

        Args:
            name: The competitor name to validate

        Returns:
            The validated and normalized name

        Raises:
            ValueError: If the name is invalid
        """
        name = name.strip()

        if len(name) < cls.MIN_NAME_LENGTH:
            raise ValueError(
                f"Competitor name must be at least {cls.MIN_NAME_LENGTH} characters long"
            )
        if len(name) > cls.MAX_NAME_LENGTH:
            raise ValueError(
                f"Competitor name must not exceed {cls.MAX_NAME_LENGTH} characters"
            )

        name_pattern = re.compile(r"^[\w\s\-\.&,\'\"]+$", re.UNICODE)
        if not name_pattern.match(name):
            raise ValueError("Competitor name contains invalid characters")

        return name
