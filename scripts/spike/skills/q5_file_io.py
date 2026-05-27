"""SK-PRD-00 Q5 probe — File I/O with scripts/ directory.

Runs INSIDE the AgentEngineSandboxCodeExecutor sandbox via sandbox_test_harness.py.
Emits a single JSON object on stdout so the harness can capture it deterministically.

Each block produces a tagged-union result:
  {"status": "ok|file_not_found|permission_denied|other_error",
   "value":  "<result or null>",
   "error":  "<ExceptionType: message or null>"}

All six blocks run independently — one failure does not abort the others.

Run locally (smoke test — paths differ from sandbox, structure must parse):
    python scripts/spike/skills/q5_file_io.py
"""

from __future__ import annotations

import getpass
import json
import os
import pathlib
import platform
import re
import socket
import sys

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _classify(exc: Exception) -> str:
    name = type(exc).__name__
    if name in {"FileNotFoundError", "IsADirectoryError"}:
        return "file_not_found"
    if name == "PermissionError":
        return "permission_denied"
    return "other_error"


def _ok(value: object) -> dict:
    return {"status": "ok", "value": value, "error": None}


def _err(exc: Exception) -> dict:
    return {
        "status": _classify(exc),
        "value": None,
        "error": f"{type(exc).__name__}: {exc}",
    }


# ---------------------------------------------------------------------------
# Block A — runtime_characterization
# ---------------------------------------------------------------------------


def _block_runtime() -> dict:
    try:
        import pwd as _pwd

        username = _pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        try:
            username = getpass.getuser()
        except Exception as e:
            username = f"<unavailable: {e}>"

    try:
        cwd = os.getcwd()
    except Exception as e:
        cwd = f"<unavailable: {e}>"

    try:
        ls_cwd = os.listdir(".")
    except Exception as e:
        ls_cwd = f"<unavailable: {e}>"

    try:
        hostname = socket.gethostname()
    except Exception as e:
        hostname = f"<unavailable: {e}>"

    return {
        "cwd": cwd,
        "ls_cwd": ls_cwd,
        "username": username,
        "sys_executable": sys.executable,
        "hostname": hostname,
        "platform": platform.platform(),
    }


# ---------------------------------------------------------------------------
# Block B — open_read
# ---------------------------------------------------------------------------


def _block_open_read() -> dict:
    try:
        with open("scripts/extract.py", encoding="utf-8") as fh:
            content = fh.read()
        return _ok(content)
    except Exception as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Block C — pathlib_iterdir
# ---------------------------------------------------------------------------


def _block_pathlib_iterdir() -> dict:
    try:
        names = [p.name for p in pathlib.Path("scripts/").iterdir()]
        return _ok(names)
    except Exception as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Block D — env_bundle_keys
# ---------------------------------------------------------------------------

_REDACT_PATTERN = re.compile(
    r"KEY|SECRET|TOKEN|CREDENTIALS|CRED|PASSWORD|PASS\b|CERT|PRIVATE",
    re.IGNORECASE,
)
_INTEREST_PATTERN = re.compile(
    r"^(SKILL_|BUNDLE_|KENE_|RESOURCE_|AGENT_|VERTEX_|GOOGLE_|ADK_|WORKSPACE_)",
    re.IGNORECASE,
)


def _block_env_bundle_keys() -> dict:
    try:
        result: dict[str, str] = {}
        for key, val in os.environ.items():
            if not _INTEREST_PATTERN.match(key):
                continue
            if _REDACT_PATTERN.search(key):
                result[key] = "<redacted>"
            elif len(val) > 200:
                result[key] = val[:200] + "...<truncated>"
            else:
                result[key] = val
        return _ok(result)
    except Exception as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Block E — exec_run
# ---------------------------------------------------------------------------


def _block_exec_run() -> dict:
    try:
        with open("scripts/extract.py", encoding="utf-8") as fh:
            source = fh.read()
        # Restrict builtins so exec'd code cannot import, open files, or call subprocess.
        # The probe only needs to capture the SENTINEL constant assignment.
        exec_globals: dict = {"__builtins__": {}}
        exec(source, exec_globals)
        sentinel = exec_globals.get("SENTINEL")
        return _ok({"SENTINEL": sentinel})
    except Exception as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Block F — alt_paths
# ---------------------------------------------------------------------------

_ALT_PATHS = [
    "/tmp/skills/q5_skill_bundle/scripts/extract.py",
    "/workspace/skills/q5_skill_bundle/scripts/extract.py",
    "/mnt/skills/q5_skill_bundle/scripts/extract.py",
    "/var/skills/q5_skill_bundle/scripts/extract.py",
]


def _build_alt_paths() -> list[str]:
    paths = list(_ALT_PATHS)
    try:
        paths.append(
            str(pathlib.Path.home() / "skills/q5_skill_bundle/scripts/extract.py")
        )
    except Exception:
        pass
    try:
        parent = str(pathlib.Path(os.getcwd()).parent / "scripts/extract.py")
        paths.append(parent)
    except Exception:
        pass
    return paths


def _block_alt_paths() -> dict:
    try:
        results: dict[str, dict] = {}
        for path_str in _build_alt_paths():
            try:
                exists = os.path.exists(path_str)
                is_file = os.path.isfile(path_str)
                results[path_str] = {"exists": exists, "is_file": is_file}
            except Exception as exc:
                results[path_str] = {
                    "exists": None,
                    "is_file": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
        return _ok(results)
    except Exception as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    output = {
        "runtime_characterization": _block_runtime(),
        "open_read": _block_open_read(),
        "pathlib_iterdir": _block_pathlib_iterdir(),
        "env_bundle_keys": _block_env_bundle_keys(),
        "exec_run": _block_exec_run(),
        "alt_paths": _block_alt_paths(),
    }
    print(json.dumps(output, default=str))


if __name__ == "__main__":
    main()
