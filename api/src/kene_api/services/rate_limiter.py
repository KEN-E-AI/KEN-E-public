"""Rate limiting service for external API calls."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from ..cache import CacheService

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for external API calls using cache service."""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        """Initialize rate limiter.
        
        Args:
            cache_service: Cache service instance. If None, rate limiting is disabled.
        """
        self.cache = cache_service
        self.enabled = cache_service is not None and cache_service.enabled
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60
    ) -> Tuple[bool, Optional[int]]:
        """Check if request is allowed under rate limit.
        
        Args:
            key: Unique key for rate limiting (e.g., "wikipedia:search:apple")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests or seconds_until_reset)
        """
        if not self.enabled:
            # Rate limiting disabled, allow all requests
            return True, None
        
        cache_key = f"rate_limit:{key}"
        
        try:
            # Get current count
            current = self.cache.get(cache_key)
            
            if current is None:
                # First request in window
                success = self.cache.set(cache_key, 1, ttl_seconds=window_seconds)
                if success:
                    return True, max_requests - 1
                else:
                    # Cache error, fail open
                    logger.warning(f"Could not set rate limit for {key}, allowing request")
                    return True, None
            
            current_count = int(current)
            
            if current_count >= max_requests:
                # Rate limit exceeded
                # Try to get TTL to inform user when they can retry
                try:
                    ttl = self.cache.ttl(cache_key)
                    logger.warning(f"Rate limit exceeded for {key}: {current_count}/{max_requests}")
                    return False, ttl
                except Exception:
                    return False, window_seconds
            
            # Increment counter
            new_count = current_count + 1
            success = self.cache.increment(cache_key)
            
            if success:
                return True, max_requests - new_count
            else:
                # Could not increment, but we're under limit, so allow
                return True, max_requests - current_count - 1
                
        except Exception as e:
            # On any error, fail open (allow the request)
            logger.error(f"Rate limiter error for {key}: {e}, allowing request")
            return True, None
    
    async def check_multi_tier_rate_limit(
        self,
        key: str,
        limits: list[Tuple[int, int]]
    ) -> Tuple[bool, Optional[str]]:
        """Check against multiple rate limit tiers.
        
        Args:
            key: Base key for rate limiting
            limits: List of (max_requests, window_seconds) tuples
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        if not self.enabled:
            return True, None
        
        for max_requests, window_seconds in limits:
            tier_key = f"{key}:{window_seconds}"
            allowed, remaining = await self.check_rate_limit(
                tier_key, max_requests, window_seconds
            )
            
            if not allowed:
                if window_seconds >= 3600:
                    window_desc = f"{window_seconds // 3600} hour(s)"
                elif window_seconds >= 60:
                    window_desc = f"{window_seconds // 60} minute(s)"
                else:
                    window_desc = f"{window_seconds} second(s)"
                
                retry_time = remaining if remaining else window_seconds
                if retry_time >= 60:
                    retry_desc = f"{retry_time // 60} minute(s)"
                else:
                    retry_desc = f"{retry_time} second(s)"
                
                error_msg = (
                    f"Rate limit exceeded: {max_requests} requests per {window_desc}. "
                    f"Please retry in {retry_desc}."
                )
                return False, error_msg
        
        return True, None


class APIRateLimiter:
    """Specific rate limiter for external API calls."""
    
    # Default rate limits for different APIs
    WIKIPEDIA_LIMITS = [
        (10, 60),     # 10 requests per minute
        (100, 3600),  # 100 requests per hour
    ]
    
    WIKIDATA_LIMITS = [
        (10, 60),     # 10 requests per minute
        (100, 3600),  # 100 requests per hour
    ]
    
    GEMINI_LIMITS = [
        (5, 60),      # 5 requests per minute
        (50, 3600),   # 50 requests per hour
    ]
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        """Initialize API rate limiter."""
        self.rate_limiter = RateLimiter(cache_service)
    
    async def check_wikipedia_limit(self, term: str) -> Tuple[bool, Optional[str]]:
        """Check Wikipedia API rate limit."""
        key = f"wikipedia:{term.lower()}"
        return await self.rate_limiter.check_multi_tier_rate_limit(
            key, self.WIKIPEDIA_LIMITS
        )
    
    async def check_wikidata_limit(self, term: str) -> Tuple[bool, Optional[str]]:
        """Check Wikidata API rate limit."""
        key = f"wikidata:{term.lower()}"
        return await self.rate_limiter.check_multi_tier_rate_limit(
            key, self.WIKIDATA_LIMITS
        )
    
    async def check_gemini_limit(self, term: str) -> Tuple[bool, Optional[str]]:
        """Check Gemini API rate limit."""
        key = f"gemini:{term.lower()}"
        return await self.rate_limiter.check_multi_tier_rate_limit(
            key, self.GEMINI_LIMITS
        )