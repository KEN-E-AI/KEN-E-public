"""Prometheus metrics for the rate-limiter subsystem (AH-79).

Exposes the ``ratelimit_backend_override_flips_total`` counter that is
incremented every time the ``rate_limit_backend_override`` feature flag is
written.  Cloud Monitoring scrapes this counter; the alert policy lives in
Terraform (AH-73 scope).

Follows the ``oauth_metrics.py`` pattern: uses ``_get_or_create_counter`` to
survive the ``pytest_configure`` REGISTRY clear and avoid duplicate-registration
errors across test-session import cycles.
"""

from .oauth_metrics import _get_or_create_counter

ratelimit_backend_override_flips_total = _get_or_create_counter(
    "ratelimit_backend_override_flips_total",
    "Total writes to rate_limit_backend_override feature flag "
    "(create / update / delete). Labels carry the before/after default_enabled "
    "state so Cloud Monitoring alert policies can discriminate direction.",
    ["previous_enabled", "new_enabled"],
)
