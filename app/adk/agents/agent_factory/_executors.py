"""Shared thread-pool executor for pool-checkout call sites (AH-77 Item F).

Both ``specialist_runtime._build_specialist`` and (potentially) ``builder``
pay a ``ThreadPoolExecutor(max_workers=1)`` construction + join on every MCP
pool checkout.  With N specialists x M servers, the per-turn overhead is
non-trivial: each ``with`` statement waits for the worker thread to terminate.

This module provides a single process-lifetime executor shared across all
checkout call sites.  The executor purpose is timeout enforcement
(``future.result(timeout=...)``), not parallelism; 8 workers covers the
warm-up burst on a Cloud Run instance without committing excessive thread
inventory.

The executor is **not explicitly shut down** on process exit: its threads are
daemons (Python 3.9+, ``ThreadPoolExecutor`` default), so they are collected
by the interpreter on shutdown without blocking the Cloud Run lifecycle.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

# One executor per process, shared across all pool-checkout call sites.
# Sized for MCP pool checkouts (N specialists x M servers per cold turn).
_POOL_CHECKOUT_EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="kene-pool-checkout",
)


def get_pool_checkout_executor() -> ThreadPoolExecutor:
    """Return the process-wide pool-checkout executor."""
    return _POOL_CHECKOUT_EXECUTOR
