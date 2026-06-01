"""Feature Flags package — security-critical side-effects registry (AH-79).

The evaluation primitives live in ``services/feature_flag_service.py``.
This package is the home for side-effect hooks that fire on mutating operations
(create / update / delete) for flags classified as security-critical.
"""
