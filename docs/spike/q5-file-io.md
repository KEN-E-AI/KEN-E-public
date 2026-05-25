# Question 5 — File I/O with `scripts/` directory

> Live capture from a credentialled workstation (`ken@ken-e.ai`) against the
> spike Agent Engine
> (`projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568`),
> 2026-05-25, post SK-33 harness rework. Single run; six access patterns
> probed in one harness invocation. Direct mode (no `LlmAgent`).
>
> SK-7 will absorb this file verbatim under `## Question 5 — File I/O` in
> `docs/spike-agent-engine-sandbox-findings.md`.

---

## Question 5 — File I/O with `scripts/` directory

### Test

**Probe script:** `scripts/spike/skills/q5_file_io.py` (six access patterns
in a single script, emitting one JSON object on stdout).

**Bundle staged on disk:**
`scripts/spike/skills/q5_skill_bundle/SKILL.md` cites
`scripts/extract.py` (a file containing a `SENTINEL = "..."` assignment).
The bundle exists only on the spike branch as a representative skill
layout — it is **not** transmitted into the sandbox by the harness.

**Access patterns:**

| Block | What it tries | Why |
|---|---|---|
| `runtime_characterization` | `os.getcwd()`, `os.listdir(".")`, `pwd.getpwuid(os.getuid()).pw_name`, `sys.executable`, `socket.gethostname()`, `platform.platform()` | Establish the sandbox's filesystem rooting + identity surface |
| `open_read` | `open("scripts/extract.py").read()` | Plain stdlib open — relative path |
| `pathlib_iterdir` | `pathlib.Path("scripts/").iterdir()` | Verify directory existence |
| `env_bundle_keys` | scan `os.environ` for `SKILL_/BUNDLE_/KENE_/RESOURCE_/AGENT_/VERTEX_/GOOGLE_/ADK_/WORKSPACE_` prefixes | Check whether skill metadata is injected via env vars |
| `exec_run` | `open()` + `exec()` of `scripts/extract.py`, capturing `SENTINEL` from `exec_globals` | Verify code-execution path can reach the file |
| `alt_paths` | `os.path.exists/is_file` on 6 alternative paths (`/tmp/skills/...`, `/workspace/skills/...`, `/mnt/skills/...`, `/var/skills/...`, `~/skills/...`, parent-dir) | Cover every plausible bundle mount point |

**Harness invocation:**

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q5_file_io.py
```

---

### Result

**Live capture (2026-05-25, direct-mode harness):**

```json
{
  "runtime_characterization": {
    "cwd": "/home/bard",
    "ls_cwd": [],
    "username": "root",
    "sys_executable": "/usr/local/bin/python3",
    "hostname": "localhost",
    "platform": "Linux-4.19.0-gvisor-x86_64-with-glibc2.36"
  },
  "open_read": {
    "status": "file_not_found",
    "value": null,
    "error": "FileNotFoundError: [Errno 2] No such file or directory: 'scripts/extract.py'"
  },
  "pathlib_iterdir": {
    "status": "file_not_found",
    "value": null,
    "error": "FileNotFoundError: [Errno 2] No such file or directory: 'scripts'"
  },
  "env_bundle_keys": {
    "status": "ok",
    "value": {},
    "error": null
  },
  "exec_run": {
    "status": "file_not_found",
    "value": null,
    "error": "FileNotFoundError: [Errno 2] No such file or directory: 'scripts/extract.py'"
  },
  "alt_paths": {
    "status": "ok",
    "value": {
      "/tmp/skills/q5_skill_bundle/scripts/extract.py":       {"exists": false, "is_file": false},
      "/workspace/skills/q5_skill_bundle/scripts/extract.py": {"exists": false, "is_file": false},
      "/mnt/skills/q5_skill_bundle/scripts/extract.py":       {"exists": false, "is_file": false},
      "/var/skills/q5_skill_bundle/scripts/extract.py":       {"exists": false, "is_file": false},
      "/root/skills/q5_skill_bundle/scripts/extract.py":      {"exists": false, "is_file": false},
      "/home/scripts/extract.py":                             {"exists": false, "is_file": false}
    },
    "error": null
  }
}
```

Harness trailer:

```
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 3.11
Exit status  : ok
```

**Trustworthiness:** direct mode (no hallucination surface), explicit
`Exit status: ok` from the harness means the executor reported
`OUTCOME_OK` and the script produced one structured JSON object on stdout.
The FileNotFoundError values are real Python exception objects observed
INSIDE the sandbox runtime, not synthetic LLM output.

#### Per-pattern outcome table

| Pattern | Status | Conclusion |
|---|---|---|
| `runtime_characterization` | ok | Sandbox rooted at `/home/bard` (empty); runs as `root`; gVisor-isolated; Python 3 at `/usr/local/bin/python3` |
| `open_read` | file_not_found | `scripts/extract.py` not at the script's cwd |
| `pathlib_iterdir` | file_not_found | `scripts/` directory does not exist at the script's cwd |
| `env_bundle_keys` | ok (empty dict) | **No** skill-metadata env vars (SKILL_/BUNDLE_/KENE_/etc) are injected by the sandbox runtime |
| `exec_run` | file_not_found | The `exec()` path cannot reach the bundle file because the bundle is not present |
| `alt_paths` | ok (all 6 missing) | None of the plausible mount points exists |

#### Sandbox runtime details (from `runtime_characterization`)

- **Kernel:** `Linux-4.19.0-gvisor-x86_64-with-glibc2.36` — Google's
  [gVisor](https://gvisor.dev/) user-space kernel. Provides syscall-level
  isolation between the sandbox process and the host. Container escape via
  kernel vulnerabilities is substantially harder than with a stock Linux
  container.
- **User:** `root` inside the sandbox. Not a security risk because gVisor
  intercepts every syscall — the `root` identity has no privileges
  outside the user-space kernel's policy.
- **CWD:** `/home/bard` (empty directory). Standard Vertex sandbox working
  directory.
- **Python:** `/usr/local/bin/python3` — system Python install on the
  sandbox image.

---

### Implication for Skills

1. **SK-PRD-03 skill-authoring contract — `scripts/` is NOT filesystem-mounted.**
   The SKILL.md design pattern (a `scripts/` directory containing
   `extract.py` that the L3 callable can `open()` and exec) **cannot rely
   on filesystem availability inside the sandbox**. The default sandbox
   working directory is empty; `scripts/extract.py` does not resolve.
   SK-PRD-03 MUST package skill content into the script string itself —
   either by inlining the bundle file contents verbatim or by serialising
   the bundle to base64/JSON and embedding it as a constant the L3 script
   decodes at runtime.

2. **No env-var-based metadata injection.** The sandbox does not surface
   SKILL_, BUNDLE_, KENE_, AGENT_, RESOURCE_, or any other skill-related
   environment variable. Metadata that the L3 callable needs (skill ID,
   account ID, config-version) must travel inside the script body too.

3. **SK-PRD-02 `SandboxPool` bundle delivery is the right abstraction.**
   The pool already constructs script strings per-invocation; this Q5
   result confirms that pattern is the only viable shape. There is no
   "warm the sandbox with bundle X" upload step available via the ADK
   1.27.5 surface — every invocation must self-contain its bundle.

4. **gVisor isolation is a security positive.** Combined with Q1's empty
   default egress, the sandbox security posture is substantially stronger
   than the pre-spike research assumed. The SK-9 security review can
   reference this finding to lower the perceived attack surface of
   user-authored skills (still high in absolute terms, but the lateral
   movement surface is small).

5. **Bundle-size cap implication for SK-PRD-03.** Because every invocation
   must inline its bundle into the script string, very large bundles
   become an LlmAgent token-budget issue in legacy-mode use cases (not a
   concern in default direct mode, where there's no LLM context cost).
   SK-PRD-03 should impose a per-script bundle-size cap when the legacy
   LLM loop is enabled.

> Q5 has no SK-9 escalation triggers — the failure modes observed
> (FileNotFoundError, empty env) are baseline-restrictive, not
> permissive.
