"""Module for model definition."""

from types import MappingProxyType

from .base import HK_GROUPS
from .category_types import HKCategoryTypeIdentifierRegistry

CATEGORICAL_IDENTIFIER_MAPS: MappingProxyType[str, dict[str, int]] = MappingProxyType(
    {k: v.category_values() for k, v in HKCategoryTypeIdentifierRegistry.items()}
)

__all__ = [
    "HK_GROUPS",
    "HKCategoryTypeIdentifierRegistry",
    "CATEGORICAL_IDENTIFIER_MAPS",
]
