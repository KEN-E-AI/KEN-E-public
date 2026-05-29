"""
KEN-E agent module — minimal lazy stub.

The root agent is built on-demand via the agent factory (build_hierarchy).
This module exists so the agent registry can resolve '.ken_e_agent' module
path + 'ken_e_agent' attribute without triggering a full Firestore read at
import time (PEP 562 module-level __getattr__).
"""

from __future__ import annotations

import threading
from pathlib import Path

# Load environment variables from .env file BEFORE reading any env vars.
# On Agent Engine the .env is deployed alongside the agent code.
try:
    from dotenv import load_dotenv

    base_path = Path(__file__).resolve().parent
    possible_paths = [
        base_path.parent / ".env",
        base_path / ".env",
    ]
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break
except ImportError:
    pass

_ken_e_agent_lock = threading.Lock()
_ken_e_agent_instance = None


def __getattr__(name: str) -> object:
    if name == "ken_e_agent":
        global _ken_e_agent_instance
        with _ken_e_agent_lock:
            if _ken_e_agent_instance is None:
                from app.adk.agents.agent_factory import build_hierarchy

                _ken_e_agent_instance = build_hierarchy()
        return _ken_e_agent_instance
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}. "
        "Note: create_ken_e_agent, _BASE_INSTRUCTION, build_ken_e_instruction, "
        "and _make_instruction_provider were removed in AH-68."
    )
