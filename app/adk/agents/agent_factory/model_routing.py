"""Per-environment Vertex AI model-serving location resolver (AH-86).

Problem
-------
ADK's ``google.adk.models.Gemini`` builds its ``genai.Client`` as a
``@cached_property`` that reads ``GOOGLE_CLOUD_LOCATION`` from the environment
at *construction* time (see ``google.genai._api_client``, line 598).  On
Vertex AI Agent Engine the platform injects ``GOOGLE_CLOUD_LOCATION`` equal to
the *engine's deploy region* (e.g. ``us-central1``).  The ``.env`` baked into
the deploy artifact is loaded with ``load_dotenv(..., override=False)``, so the
platform value wins and any ``GOOGLE_CLOUD_LOCATION=global`` in the baked file
is silently ignored.

Some newly-released Gemini models (e.g. ``gemini-3.5-flash``) are only served
on the ``global`` endpoint and 404 on regional endpoints.  For the development
environment we therefore need ``GOOGLE_CLOUD_LOCATION=global`` to be visible
to every ``genai.Client`` constructed after agent startup.

Solution
--------
``apply_model_location_env()`` performs an explicit ``os.environ[...]``
assignment *in-process*, which overrides the platform-injected value.  It must
be called **before** any ``LlmAgent`` (or ``Gemini`` model object) is
constructed.  In the live deploy path the call site is
``hierarchy.build_hierarchy()``; in the ``adk run .`` / ``adk web`` path it is
``ken_e_agent.__getattr__("ken_e_agent")`` which also calls
``build_hierarchy()``.

Model-serving vs. Agent Engine resource location
-------------------------------------------------
``GOOGLE_CLOUD_LOCATION`` controls only the Vertex AI *model-serving* endpoint.
``VERTEX_AI_LOCATION`` is a separate variable consumed by ``vertexai.init()``,
``sandbox_pool.py``, and the Agent Engine control plane.  This module never
reads or writes ``VERTEX_AI_LOCATION``.

Extension point
---------------
``resolve_model_location`` accepts a ``data_region`` parameter as the planned
hook for per-account EU routing (needed before production multi-region
rollout).  It is intentionally unused in the dev slice — only ``environment``
matters now.
"""

from __future__ import annotations

import os

from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

# Canonical location strings — match the strings accepted by the Vertex AI
# model-serving endpoint.
_LOCATION_GLOBAL = "global"
_LOCATION_US_CENTRAL1 = "us-central1"
_LOCATION_EUROPE_WEST1 = "europe-west1"

# Environments that should route to the global endpoint.
_GLOBAL_ENVS: frozenset[str] = frozenset({"development", "dev"})


def resolve_model_location(
    environment: str,
    data_region: str | None = None,
) -> str:
    """Return the Vertex AI model-serving location for the given environment.

    Decision table
    ~~~~~~~~~~~~~~
    * ``development`` / ``dev``  → ``"global"``   (global-only models, dev only)
    * anything else, EU region   → ``"europe-west1"``
    * anything else, US / None   → ``"us-central1"``  (default)

    Args:
        environment: Value of the ``ENVIRONMENT`` env var
            (e.g. ``"development"``, ``"staging"``, ``"production"``).
            Case-insensitive; leading/trailing whitespace is stripped.
        data_region: Optional data-residency region string sourced from the
            account record (e.g. ``"EU"``, ``"Europe"``, ``"US"``,
            ``"United States"``).  Currently only consulted for
            non-development environments.  ``None`` / unknown → US default.

    Returns:
        One of ``"global"``, ``"europe-west1"``, or ``"us-central1"``.
    """
    env_normalized = (environment or "").strip().lower()

    if env_normalized in _GLOBAL_ENVS:
        return _LOCATION_GLOBAL

    region_normalized = (data_region or "").strip().lower()
    if region_normalized in {"eu", "europe"}:
        return _LOCATION_EUROPE_WEST1

    return _LOCATION_US_CENTRAL1


def apply_model_location_env(
    environment: str | None = None,
    data_region: str | None = None,
) -> str:
    """Set ``GOOGLE_CLOUD_LOCATION`` in the process environment and return it.

    This is an **explicit** ``os.environ`` assignment — it overrides any value
    previously injected by the Agent Engine platform (which arrives via the
    managed runtime before Python starts, but after our ``load_dotenv(
    ..., override=False)`` call which cannot win against it).

    Must be called before any ``LlmAgent`` or ``google.adk.models.Gemini``
    instance is constructed in this process.

    Args:
        environment: Override for the ``ENVIRONMENT`` env var.  When ``None``
            the value is read from ``os.environ`` (default ``"development"``).
        data_region: Optional data-residency region.  See
            ``resolve_model_location`` for accepted values.

    Returns:
        The resolved location string that was written to the environment.
    """
    env: str = environment or os.environ.get("ENVIRONMENT") or "development"
    location = resolve_model_location(env, data_region=data_region)

    previous = os.environ.get("GOOGLE_CLOUD_LOCATION", "<unset>")
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    if previous != location:
        logger.info(
            "Model-serving location set.",
            extra={
                "google_cloud_location": location,
                "previous_value": previous,
                "environment": env,
            },
        )
    else:
        logger.debug(
            "Model-serving location unchanged.",
            extra={
                "google_cloud_location": location,
                "environment": env,
            },
        )

    return location
