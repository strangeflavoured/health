"""Module for model definition.

Exposes the four type registries used by the importer and Redis-setup
modules, plus the unioned :data:`HKTypeIdentifierRegistry`:

* :data:`HKQuantityTypeIdentifierRegistry` — numeric measurements
* :data:`HKCategoryTypeIdentifierRegistry` — enum-style events
* :data:`HKCorrelationTypeIdentifierRegistry` — bundles of related records
* :data:`HKMiscTypeIdentifierRegistry` — types that do not fit the above

:data:`CATEGORY_MAP` flattens each category type's
``Values`` enum to a ``(type_name, value_name) → int`` mapping used by
:func:`src.importer.transform._map_categories`.
"""

from types import MappingProxyType
from typing import Any

from .base import HK_GROUPS, HKMiscTypeIdentifierRegistry
from .category_types import HKCategoryTypeIdentifierRegistry
from .correlation_types import HKCorrelationTypeIdentifierRegistry
from .quantity_types import HKQuantityTypeIdentifierRegistry

CATEGORY_MAP: MappingProxyType[tuple[str, str], int] = MappingProxyType(
    {
        (type_name, value_name): int_val
        for type_name, entry in HKCategoryTypeIdentifierRegistry.items()
        for value_name, int_val in entry.category_values().items()
    }
)

HKTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    HKCategoryTypeIdentifierRegistry
    | HKQuantityTypeIdentifierRegistry
    | HKCorrelationTypeIdentifierRegistry
    | HKMiscTypeIdentifierRegistry
)

UNIT_MAP: MappingProxyType[str, str] = MappingProxyType(
    {k: v.unit for k, v in HKTypeIdentifierRegistry.items()}
)

__all__ = [
    "HK_GROUPS",
    "HKTypeIdentifierRegistry",
    "HKCategoryTypeIdentifierRegistry",
    "HKCorrelationTypeIdentifierRegistry",
    "HKQuantityTypeIdentifierRegistry",
    "HKMiscTypeIdentifierRegistry",
    "CATEGORY_MAP",
    "UNIT_MAP",
]
