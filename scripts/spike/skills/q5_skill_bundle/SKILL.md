---
name: q5-file-io-spike
description: Fake skill bundle for SK-PRD-00 Q5 — tests whether a skill's scripts/ directory is reachable from within the AgentEngineSandboxCodeExecutor sandbox.
compatibility: SK-PRD-00 spike environment only — not for production use.
---

# Q5 File I/O Spike Skill

This is a fake skill bundle used by the SK-PRD-00 sandbox spike to answer Question 5:
does the `AgentEngineSandboxCodeExecutor` sandbox have access to files cited from
`scripts/` in a skill bundle?

The probe script (`q5_file_io.py`) attempts to read `scripts/extract.py` via several
access patterns to determine whether the sandbox file-system has auto-mounted this
bundle's `scripts/` directory.
