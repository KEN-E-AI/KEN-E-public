"""Internal support package for migrate_to_shape_b.py.

Not a public API — do not import from outside the migration script.
"""

from .config import MigrateConfig
from .resources import RESOURCES

__all__ = ["RESOURCES", "MigrateConfig"]
