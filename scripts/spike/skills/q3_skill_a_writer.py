"""SK-4 Q3 — Cross-skill state contamination: Skill A writer.

Writes a distinct sentinel value to each of four state vectors so that
q3_skill_b_reader.py can probe whether the state crosses the skill boundary
within the same AgentEngineSandboxCodeExecutor session.

State vectors:
  fs      — /tmp/sk4_sentinel.txt (filesystem)
  env     — os.environ["SK4_SENTINEL"] (environment variable)
  mod     — sys.modules["sk4_state"].sentinel (Python module global)
  tmpsub  — tempfile.mkdtemp(prefix="sk4_") + sentinel.txt (tempdir)
             plus /tmp/sk4_pid written via subprocess

Output grammar (one line per vector):
  [A] <vector>: WROTE <sentinel>
"""

import datetime
import os
import subprocess
import sys
import tempfile
import types

_TS = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# ---------------------------------------------------------------------------
# Vector: filesystem (/tmp/sk4_sentinel.txt)
# ---------------------------------------------------------------------------
_FS_PATH = "/tmp/sk4_sentinel.txt"
_FS_SENTINEL = f"SK4_SENT_A_fs_{_TS}"
with open(_FS_PATH, "w") as _f:
    _f.write(_FS_SENTINEL)
print(f"[A] fs: WROTE {_FS_SENTINEL}")

# ---------------------------------------------------------------------------
# Vector: environment variable
# ---------------------------------------------------------------------------
_ENV_SENTINEL = f"SK4_SENT_A_env_{_TS}"
os.environ["SK4_SENTINEL"] = _ENV_SENTINEL
print(f"[A] env: WROTE {_ENV_SENTINEL}")

# ---------------------------------------------------------------------------
# Vector: Python module global (sys.modules injection)
# ---------------------------------------------------------------------------
_MOD_SENTINEL = f"SK4_SENT_A_mod_{_TS}"
_mod = types.ModuleType("sk4_state")
_mod.sentinel = _MOD_SENTINEL  # type: ignore[attr-defined]
sys.modules["sk4_state"] = _mod
print(f"[A] mod: WROTE {_MOD_SENTINEL}")

# ---------------------------------------------------------------------------
# Vector: tempdir + subprocess PID side-channel
# ---------------------------------------------------------------------------
_TMPDIR = tempfile.mkdtemp(prefix="sk4_")
_TMPSUB_SENTINEL = f"SK4_SENT_A_tmpsub_{_TS}"
_TMPSUB_FILE = os.path.join(_TMPDIR, "sentinel.txt")
with open(_TMPSUB_FILE, "w") as _f:
    _f.write(_TMPSUB_SENTINEL)
# Also write the directory path to a known location so the reader can find it.
_TMPDIR_MARKER = "/tmp/sk4_tmpdir_path.txt"
with open(_TMPDIR_MARKER, "w") as _f:
    _f.write(_TMPDIR)
# Write PID via subprocess for the "subprocess state" AC bullet.
subprocess.run(
    ["sh", "-c", "echo $$ > /tmp/sk4_pid"],
    check=False,
)
print(f"[A] tmpsub: WROTE {_TMPSUB_SENTINEL} in {_TMPDIR}")
