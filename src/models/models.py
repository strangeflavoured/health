"""Numerical mappings for Apple Health categorical data types.

Each :class:`~enum.Enum` subclass corresponds to one
`HKCategoryTypeIdentifier <https://developer.apple.com/documentation/healthkit/hkcategorytypeidentifier>`_
and maps its string values to signed integers suitable for storage in Redis TimeSeries.

The module-level :data:`categorical_identifier_maps` registry maps each
identifier string to its :class:`HKCategoryTypeIdentifier` member to  value map
"""

from enum import Enum
from types import MappingProxyType

# ---------------------------------------------------------------------------
# Base model classes
# ---------------------------------------------------------------------------


class HKIdentifier:
    """Sentinel identifier base class."""

    group: str
    identifier_type: str


class HKQuantityTypeIdentifier(HKIdentifier):
    """Sentinel quantity identifier values."""

    identifier_type = "quantity"


class HKCategoryTypeIdentifier(HKIdentifier):
    """Sentinel category identifier values."""

    identifier_type = "category"

    class Values:
        """HK category identifier values :class:`Enum` template.

        Subclasses overwrite this class as Enum with their associated values.
        """

        pass

    @classmethod
    def category_values(cls) -> dict[str, int]:
        """Return name: value dict of `HKCategoryTypeIdentifier` values."""
        return {i.name: i.value for i in cls.Values}


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


class BodyMeasurements:  # noqa: D101
    group = "body_measurements"


class Fitness:  # noqa: D101
    group = "body_measurements"


class ReproductiveHealth:  # noqa: D101
    group = "reproductive_health"


class Hearing:  # noqa: D101
    group = "hearing"


class VitalSigns:  # noqa: D101
    group = "vital_signs"


class LabTestResults:  # noqa: D101
    group = "lab_test_results"


class Mobility:  # noqa: D101
    group = "mobility"


class Nutrition:  # noqa: D101
    group = "nutrition"


class UVExposure:  # noqa: D101
    group = "uv_exposure"


class Diving:  # noqa: D101
    group = "diving"


class Mindfulness:  # noqa: D101
    group = "mindfulness"


class Symptoms:  # noqa: D101
    group = "symptoms"


class Other:  # noqa: D101
    group = "other"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HK_GROUPS = MappingProxyType(
    {
        "BodyMeasurements": BodyMeasurements,
        "Fitness": Fitness,
        "ReproductiveHealth": ReproductiveHealth,
        "Hearing": Hearing,
        "VitalSigns": VitalSigns,
        "LabTestResults": LabTestResults,
        "Mobility": Mobility,
        "Nutrition": Nutrition,
        "UVExposure": UVExposure,
        "Diving": Diving,
        "Mindfulness": Mindfulness,
        "Symptoms": Symptoms,
        "Other": Other,
    }
)


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------


class MissingUnit(Enum):
    """Sentinel unit value assigned to categorical (non-numeric) records.

    Example::

        df.loc[mask, "unit"] = MissingUnit.CATEGORICAL.value  # → "Categorical"
    """

    CATEGORICAL = "Categorical"
