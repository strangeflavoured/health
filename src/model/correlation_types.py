"""Correlation Type model classes.

Provides :data:`HKCorrelationTypeIdentifierRegistry` to the public API.

Each ``HKCorrelationTypeIdentifier*`` class is a thin stub mirroring one Apple
HealthKit ``HKCorrelationTypeIdentifier``.  A correlation bundles several
related quantity records under a single semantic event (e.g. systolic +
diastolic blood pressure readings taken at the same instant).  Per-identifier
semantics follow Apple's official HealthKit documentation; the class name is
the canonical identifier.  See :mod:`model.base` for the shared base class and
grouping definitions.
"""

from types import MappingProxyType
from typing import Any

from .base import HK_GROUPS, HKCorrelationTypeIdentifier


class HKCorrelationTypeIdentifierBloodPressure(
    HKCorrelationTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    """A single blood-pressure reading: bundles systolic + diastolic records."""


class HKCorrelationTypeIdentifierFood(
    HKCorrelationTypeIdentifier, HK_GROUPS["Nutrition"]
):
    """A logged food item: bundles its nutritional component records.

    Deprecated by Apple in HealthKit but may still appear in older exports.
    """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HKCorrelationTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    {subcls.__name__: subcls for subcls in HKCorrelationTypeIdentifier.__subclasses__()}
)
