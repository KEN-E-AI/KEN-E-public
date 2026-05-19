"""Unit tests for KEN-E root-agent tool-wrapper signatures.

Regression guard for AH-PRD-01 §7 AC#6: acceptance_criteria must be
exposed on both root-agent tool wrappers so the LLM can populate it
(AH-6 will instruct it to do so).
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock neo4j before any agent imports
neo4j_mock = MagicMock()
neo4j_mock.exceptions = MagicMock()
neo4j_mock.exceptions.ServiceUnavailable = Exception
neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", neo4j_mock.exceptions)

# Add app directory to path (matches the pattern in sibling test files)
app_dir = Path(__file__).parents[3] / "app"
sys.path.insert(0, str(app_dir))

from adk.agents.ken_e_agent import create_ken_e_agent  # noqa: E402


def test_tool_wrappers_accept_acceptance_criteria():
    """Both tool wrappers expose acceptance_criteria with empty-string default.

    Verifies AH-PRD-01 §6 API contract and §7 AC#6:
    - Parameter is present on both search_company_news and query_google_analytics
    - Default is "" (empty string), not None, for Gemini tool-call compatibility
    - Annotation is str
    - Parameter order: query, acceptance_criteria, tool_context
    """
    agent = create_ken_e_agent()
    tools_by_name = {tool.__name__: tool for tool in agent.tools}

    for tool_name in ("search_company_news", "query_google_analytics"):
        tool = tools_by_name[tool_name]
        params = inspect.signature(tool).parameters

        assert "acceptance_criteria" in params, (
            f"{tool_name} must have acceptance_criteria parameter"
        )

        ac_param = params["acceptance_criteria"]
        assert ac_param.default == "", (
            f"{tool_name}.acceptance_criteria default must be '' (empty string), "
            f"got {ac_param.default!r}"
        )
        assert ac_param.annotation is str, (
            f"{tool_name}.acceptance_criteria annotation must be str"
        )

        param_order = list(params.keys())
        assert param_order.index("query") < param_order.index("acceptance_criteria"), (
            f"In {tool_name}, 'query' must come before 'acceptance_criteria'"
        )
        assert param_order.index("acceptance_criteria") < param_order.index(
            "tool_context"
        ), f"In {tool_name}, 'acceptance_criteria' must come before 'tool_context'"
