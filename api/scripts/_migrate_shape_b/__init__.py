"""Internal support package for migrate_to_shape_b.py.

Not a public API — do not import from outside the migration script.
"""

from _migrate_shape_b.config import MigrateConfig
from _migrate_shape_b.resources import RESOURCES

__all__ = ["RESOURCES", "MigrateConfig"]
