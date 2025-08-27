"""Shared cache service for progress tracking.

This module provides a shared cache instance for tracking account creation
and strategy generation progress across different parts of the application.
"""

from ..cache import InMemoryCache

# Shared instance for progress tracking
# This ensures both the accounts router and background tasks use the same cache
progress_cache = InMemoryCache()
