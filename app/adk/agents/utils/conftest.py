"""Conftest for agents/utils unit tests.

Pre-mocks neo4j before any app imports to prevent the import chain:
  utils/__init__.py → supervisor_utils → context_loader → neo4j_tools → neo4j
from failing in the test environment where neo4j is not installed.

Also sets any environment variables required by agent modules at import time.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

# Set required environment variables before any agent imports.
os.environ.setdefault("VERTEX_AI_NEWS_DATASTORE_ID", "test-datastore")

# Pre-populate sys.modules with neo4j mocks so that the import chain
# supervisor_utils → context_loader → neo4j_tools → neo4j does not fail.
_neo4j_mock = MagicMock()
_neo4j_mock.exceptions = MagicMock()
_neo4j_mock.exceptions.ServiceUnavailable = Exception
_neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", _neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", _neo4j_mock.exceptions)
