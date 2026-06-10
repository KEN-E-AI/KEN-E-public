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

Some newly-released / preview Gemini models 404 on single-region endpoints like
``us-central1``.  ``gemini-3.5-flash`` is served on the ``global`` *and* the
``us`` / ``eu`` *multi-region* endpoints, but ``gemini-3.1-pro-preview`` is
served on the ``global`` endpoint **only** — not on the multi-region endpoints
(Review 51, 2026-06-10).  So until that model reaches the multi-region
endpoints, **every** environment (dev, staging, and prod) must serve from
``GOOGLE_CLOUD_LOCATION=global`` for it to resolve.  Either way the value must
be visible to every ``genai.Client`` constructed after agent startup.

INTERIM residency note: routing staging/prod to ``global`` relaxes design
decision D4 ("never ``global``") for the *model-serving plane only*, and is
safe **only while EU sign-ups are gated** (D6).  When ``gemini-3.1-pro-preview``
is served on the ``us`` / ``eu`` multi-region endpoints, ``resolve_model_location``
must be reverted to in-geography routing (``US → "us"``, ``EU → "eu"``) — this is
the AH-PRD-11 per-account work.  See the REVERT TRIGGER in
``resolve_model_location`` and ``data-residency-architecture.md`` §3.5.

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
#
# ``us`` / ``eu`` are the US / EU *multi-region* locations.  google-genai maps
# them to the multi-region endpoints ``https://aiplatform.us.rep.googleapis.com``
# / ``https://aiplatform.eu.rep.googleapis.com`` (``_MULTI_REGIONAL_LOCATIONS``
# in ``google.genai._api_client``).  They guarantee in-geography (US-wide /
# EU-wide) processing — the in-geography target this resolver will be reverted
# to (see the REVERT TRIGGER below).  Currently UNUSED: ``gemini-3.1-pro-preview``
# is not served on them yet, so all environments serve from ``global`` for now.
# Retained for the future in-geography restoration.
_LOCATION_GLOBAL = "global"
_LOCATION_US = "us"
_LOCATION_EU = "eu"

# Environments that route to the global endpoint for residency reasons even in
# steady state (dev holds no regulated data).  Staging/prod *also* route to
# ``global`` for now — see the REVERT TRIGGER in ``resolve_model_location``.
_GLOBAL_ENVS: frozenset[str] = frozenset({"development", "dev"})


def resolve_model_location(
    environment: str,
    data_region: str | None = None,
) -> str:
    """Return the Vertex AI model-serving location for the given environment.

    Decision table (interim — Review 51, 2026-06-10)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    * **every** environment → ``"global"``

    ``gemini-3.1-pro-preview`` is served on the ``global`` endpoint **only** —
    not on the ``us`` / ``eu`` multi-region endpoints (those serve the older
    preview models, but not this one).  So model serving routes to ``global``
    everywhere until the model reaches the multi-region endpoints.  This relaxes
    D4's "never ``global``" for the model-serving plane and is safe only while
    EU sign-ups stay gated (D6).  ``VERTEX_AI_LOCATION`` (engine / sandbox /
    session) is unaffected and stays single-region.

    ⚠️ REVERT TRIGGER (in-geography restoration)
    --------------------------------------------
    When ``gemini-3.1-pro-preview`` is served on the ``us`` / ``eu`` multi-region
    endpoints, restore in-geography routing — **required before any EU account
    goes live**:

        if env_normalized in _GLOBAL_ENVS:        # dev stays global
            return _LOCATION_GLOBAL
        region_normalized = (data_region or "").strip().lower()
        if region_normalized in {"eu", "europe"}:
            return _LOCATION_EU                    # EU → eu multi-region
        return _LOCATION_US                        # US / default → us multi-region

    This is the AH-PRD-11 per-account work; see
    ``data-residency-architecture.md`` §3.5.

    Args:
        environment: Value of the ``ENVIRONMENT`` env var
            (e.g. ``"development"``, ``"staging"``, ``"production"``).
            Case-insensitive; leading/trailing whitespace is stripped.
        data_region: Optional data-residency region string sourced from the
            account record (e.g. ``"EU"``, ``"Europe"``, ``"US"``,
            ``"United States"``).  Currently **unused** — all environments
            resolve to ``global`` (see the REVERT TRIGGER).  Retained as the
            documented extension hook for per-account EU routing.

    Returns:
        ``"global"`` (every environment, interim).
    """
    # Interim: all environments serve from ``global`` (see the REVERT TRIGGER in
    # the docstring).  ``environment`` / ``data_region`` are intentionally not
    # branched on until in-geography routing is restored.
    return _LOCATION_GLOBAL


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
