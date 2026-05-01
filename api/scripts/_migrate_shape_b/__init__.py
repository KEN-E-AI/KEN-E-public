"""Internal support package for migrate_to_shape_b.py.

Not a public API — do not import from outside the migration script.
"""

from .config import MigrateConfig
from .resources import RESOURCES
from .runner import migrate_resource

__all__ = ["RESOURCES", "MigrateConfig", "migrate_resource"]
