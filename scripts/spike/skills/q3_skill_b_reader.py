"""SK-4 Q3 — Cross-skill state contamination: Skill B reader.

Probes each of the four state vectors that q3_skill_a_writer.py targets and
reports whether the writer's sentinel is visible ("LEAK") or absent
("ISOLATED").

Resilient: does not raise if the writer never ran — all missing-state cases
produce ISOLATED output, not exceptions.

Output grammar (one line per vector):
  [B] <vector>: LEAK (<observed>) | ISOLATED
"""

import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Vector: filesystem (/tmp/sk4_sentinel.txt)
# ---------------------------------------------------------------------------
_FS_PATH = "/tmp/sk4_sentinel.txt"
try:
    with open(_FS_PATH) as _f:
        _fs_val = _f.read().strip()
    if _fs_val.startswith("SK4_SENT_A_fs_"):
        print(f"[B] fs: LEAK ({_fs_val})")
    else:
        print(f"[B] fs: ISOLATED (found unexpected content: {_fs_val!r})")
except FileNotFoundError:
    print("[B] fs: ISOLATED")

# ---------------------------------------------------------------------------
# Vector: environment variable
# ---------------------------------------------------------------------------
_env_val = os.environ.get("SK4_SENTINEL", "")
if _env_val.startswith("SK4_SENT_A_env_"):
    print(f"[B] env: LEAK ({_env_val})")
else:
    print("[B] env: ISOLATED")

# ---------------------------------------------------------------------------
# Vector: Python module global (sys.modules injection)
# ---------------------------------------------------------------------------
_sk4_mod = sys.modules.get("sk4_state")
if _sk4_mod is not None:
    _mod_val = getattr(_sk4_mod, "sentinel", None)
    if isinstance(_mod_val, str) and _mod_val.startswith("SK4_SENT_A_mod_"):
        print(f"[B] mod: LEAK ({_mod_val})")
    else:
        print(
            f"[B] mod: ISOLATED (module present but sentinel not recognised: {_mod_val!r})"
        )
else:
    print("[B] mod: ISOLATED")

# ---------------------------------------------------------------------------
# Vector: tempdir + subprocess PID side-channel
# ---------------------------------------------------------------------------
_TMPDIR_MARKER = "/tmp/sk4_tmpdir_path.txt"
_tmpsub_result = "ISOLATED"  # default; set inside try on LEAK or unexpected content
try:
    with open(_TMPDIR_MARKER) as _f:
        _tmpdir = _f.read().strip()
    _sentinel_file = os.path.join(_tmpdir, "sentinel.txt")
    with open(_sentinel_file) as _f:
        _tmpsub_val = _f.read().strip()
    if _tmpsub_val.startswith("SK4_SENT_A_tmpsub_"):
        _tmpsub_result = f"LEAK ({_tmpsub_val})"
    else:
        _tmpsub_result = f"ISOLATED (unexpected content: {_tmpsub_val!r})"
except FileNotFoundError:
    _tmpsub_result = "ISOLATED"
print(f"[B] tmpsub: {_tmpsub_result}")

# Subprocess PID side-channel — read writer's PID record from /tmp/sk4_pid.
_pid_result_proc = subprocess.run(
    ["sh", "-c", "cat /tmp/sk4_pid 2>/dev/null"],
    capture_output=True,
    text=True,
    check=False,
)
_pid_val = _pid_result_proc.stdout.strip()
if _pid_val:
    print(f"[B] subprocess-pid: LEAK (writer PID record: {_pid_val})")
else:
    print("[B] subprocess-pid: ISOLATED")
