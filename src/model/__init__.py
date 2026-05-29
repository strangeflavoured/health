"""Module for model definition."""

from types import MappingProxyType
from typing import Any

from .base import HK_GROUPS, HKMiscTypeIdentifierRegistry
from .category_types import HKCategoryTypeIdentifierRegistry
from .quantity_types import HKQuantityTypeIdentifierRegistry

CATEGORICAL_IDENTIFIER_MAPS: MappingProxyType[str, dict[str, int]] = MappingProxyType(
    {k: v.category_values() for k, v in HKCategoryTypeIdentifierRegistry.items()}
)

HKTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    HKCategoryTypeIdentifierRegistry
    | HKQuantityTypeIdentifierRegistry
    | HKMiscTypeIdentifierRegistry
)

__all__ = [
    "HK_GROUPS",
    "HKTypeIdentifierRegistry",
    "HKCategoryTypeIdentifierRegistry",
    "HKQuantityTypeIdentifierRegistry",
    "HKMiscTypeIdentifierRegistry",
    "CATEGORICAL_IDENTIFIER_MAPS",
]
