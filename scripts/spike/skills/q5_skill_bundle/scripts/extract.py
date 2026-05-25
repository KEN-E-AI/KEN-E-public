"""Fake skill script for SK-PRD-00 Q5 spike.

If the sandbox has access to this file, any of the following signals confirms it:
  - open("scripts/extract.py").read()  contains the string SENTINEL
  - exec(<content>, namespace); namespace["SENTINEL"] == "q5-sentinel-v1"
  - pathlib.Path("scripts/").iterdir() yields "extract.py"
"""

SENTINEL = "q5-sentinel-v1"


def extract() -> str:
    """Return the sentinel value. Callable if exec() succeeds."""
    return SENTINEL
