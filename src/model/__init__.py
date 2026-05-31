"""Module for model definition.

Exposes the four type registries used by the importer and Redis-setup
modules, plus the unioned :data:`HKTypeIdentifierRegistry`:

* :data:`HKQuantityTypeIdentifierRegistry` — numeric measurements
* :data:`HKCategoryTypeIdentifierRegistry` — enum-style events
* :data:`HKCorrelationTypeIdentifierRegistry` — bundles of related records
* :data:`HKMiscTypeIdentifierRegistry` — types that do not fit the above

:data:`CATEGORICAL_IDENTIFIER_MAPS` flattens each category type's
``Values`` enum to a ``name → int`` mapping used by
:func:`src.importer.transform._map_categories`.
"""

from types import MappingProxyType
from typing import Any

from .base import HK_GROUPS, HKMiscTypeIdentifierRegistry
from .category_types import HKCategoryTypeIdentifierRegistry
from .correlation_types import HKCorrelationTypeIdentifierRegistry
from .quantity_types import HKQuantityTypeIdentifierRegistry

CATEGORICAL_IDENTIFIER_MAPS: MappingProxyType[str, dict[str, int]] = MappingProxyType(
    {k: v.category_values() for k, v in HKCategoryTypeIdentifierRegistry.items()}
)

HKTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    HKCategoryTypeIdentifierRegistry
    | HKQuantityTypeIdentifierRegistry
    | HKCorrelationTypeIdentifierRegistry
    | HKMiscTypeIdentifierRegistry
)

UNIT_MAP: MappingProxyType[str, dict[str, int]] = MappingProxyType(
    {k: v.unit for k, v in HKTypeIdentifierRegistry.items()}
)

__all__ = [
    "HK_GROUPS",
    "HKTypeIdentifierRegistry",
    "HKCategoryTypeIdentifierRegistry",
    "HKCorrelationTypeIdentifierRegistry",
    "HKQuantityTypeIdentifierRegistry",
    "HKMiscTypeIdentifierRegistry",
    "CATEGORICAL_IDENTIFIER_MAPS",
    "UNIT_MAP",
]
