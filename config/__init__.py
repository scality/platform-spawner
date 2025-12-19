"""
Configuration schemas and default values.
"""

from .defaults import (
    DEFAULT_INSTANCE_TYPES,
    DEFAULT_REGIONS,
    DEFAULT_ZONES,
)
from .flavors import (
    get_instance_type,
    list_available_flavors,
    validate_flavor,
    get_flavor_info,
    FLAVOR_MAP,
)

__all__ = [
    "DEFAULT_INSTANCE_TYPES",
    "DEFAULT_REGIONS",
    "DEFAULT_ZONES",
    "get_instance_type",
    "list_available_flavors",
    "validate_flavor",
    "get_flavor_info",
    "FLAVOR_MAP",
]

