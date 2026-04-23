"""Module for model definition."""

from types import MappingProxyType

from .categorical_types import HKCategoryTypeIdentifierRegistry
from .models import HK_GROUPS
from .quantity_types import HKQuantityTypeIdentifierRegistry

CATEGORICAL_IDENTIFIER_MAPS: MappingProxyType[str, dict[str, int]] = MappingProxyType(
    {k: v.category_values() for k, v in HKCategoryTypeIdentifierRegistry.items()}
)

__all__ = [
    "HK_GROUPS",
    "HKCategoryTypeIdentifierRegistry",
    "HKQuantityTypeIdentifierRegistry",
]
