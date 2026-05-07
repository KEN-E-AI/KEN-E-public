"""conftest.py for api/scripts/tests.

Adds the workspace root to sys.path so that ``api.scripts.*`` imports
resolve correctly when pytest's rootdir is ``api/`` (due to api/pytest.ini).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Workspace root is three levels up: api/scripts/tests/ -> api/scripts/ -> api/ -> workspace/
_workspace_root = Path(__file__).parent.parent.parent.parent
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))
