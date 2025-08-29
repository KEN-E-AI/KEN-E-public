"""Validators for KEN-E API."""

import re

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
                raise ValueError(f"Invalid keyword '{keyword}': {e!s}")

        return validated

    @classmethod
    def field_validator_keyword_list(cls):
        """Create a Pydantic field validator for keyword lists."""

        @field_validator(
            "company_keywords", "customer_keywords", "keywords", mode="before"
        )
        def validate_keywords(v: list[str] | None) -> list[str]:
            if v is None:
                return []
            return cls.validate_keyword_list(v)

        return validate_keywords


class CompetitorValidators:
    """Validators for competitor-related fields."""

    @classmethod
    def validate_website(cls, website: str | None) -> str | None:
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


class ConceptValidators:
    """Validators for concept-related fields."""

    # Allowed domains for concept references
    ALLOWED_REFERENCE_DOMAINS = [
        "wikipedia.org",
        "wikidata.org",
        "britannica.com",
        "reuters.com",
        "bloomberg.com",
        "investopedia.com",
    ]

    @classmethod
    def validate_reference_url(cls, url: str) -> str:
        """Validate reference URL for concepts.
        
        Args:
            url: The URL to validate
            
        Returns:
            Normalized URL
            
        Raises:
            ValueError: If URL is invalid or from untrusted source
        """
        if not url:
            raise ValueError("Reference URL is required")

        url = url.strip()

        # Add https:// if no protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Basic URL structure validation
        url_pattern = re.compile(
            r"^https?://"  # Protocol
            r"(?:[a-zA-Z0-9-]+\.)*"  # Subdomains
            r"[a-zA-Z0-9-]+"  # Domain
            r"(?:\.[a-zA-Z]{2,})"  # TLD
            r"(?:/.*)?$"  # Path (optional)
        )

        if not url_pattern.match(url):
            raise ValueError("Invalid reference URL format")

        # Check if from allowed domain or is a reputable source
        url_lower = url.lower()

        # Check for known trusted domains
        is_trusted = any(domain in url_lower for domain in cls.ALLOWED_REFERENCE_DOMAINS)

        # Allow any .com, .org, .gov, .edu for official websites
        if not is_trusted:
            if not re.search(r"\.(com|org|net|gov|edu)", url_lower):
                raise ValueError(
                    "Reference URL must be from a recognized source (Wikipedia, Wikidata, "
                    "official websites, or other trusted domains)"
                )

        return url

    @classmethod
    def validate_concept_description(cls, description: str) -> str:
        """Validate concept description.
        
        Args:
            description: The description to validate
            
        Returns:
            Validated description
            
        Raises:
            ValueError: If description is invalid
        """
        if not description:
            raise ValueError("Concept description is required")

        description = description.strip()

        if len(description) < 10:
            raise ValueError("Concept description must be at least 10 characters")

        if len(description) > 500:
            raise ValueError("Concept description must not exceed 500 characters")

        return description
