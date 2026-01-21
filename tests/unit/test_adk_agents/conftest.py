"""Test configuration for ADK agents unit tests.

Sets up environment variables required for agent imports.
"""

import os

# Set required environment variables before any agent imports
os.environ.setdefault("VERTEX_AI_NEWS_DATASTORE_ID", "test-datastore")
