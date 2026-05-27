"""Base classes for health data models.

Provides HK_GROUPS registry to public API .
"""

from enum import Enum
from types import MappingProxyType
from typing import Any, Self

# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------


class MissingUnit(Enum):
    """Sentinel unit value assigned to categorical (non-numeric) records.

    Example::

        df.loc[mask, "unit"] = MissingUnit.CATEGORICAL.value  # → "Categorical"
    """

    CATEGORICAL = "Categorical"


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


class HKMiscTypeIdentifier(HKIdentifier):
    """Sentinel miscellaneous identifier values."""

    identifier_type = "miscellaneous"


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


class HKGroup:  # noqa: D101
    group: str

    @classmethod
    def get_members(cls) -> list[type[Self]]:
        """Return subclasses of this class."""
        return cls.__subclasses__()

    @classmethod
    def map_members(cls) -> dict[str, str]:
        """Return a mapping of subclasses names of this class to their group."""
        if hasattr(cls, "group"):
            return {member.__name__: cls.group for member in cls.get_members()}
        else:
            return {
                name: group
                for member in cls.get_members()
                for name, group in member.map_members().items()
            }


class BodyMeasurements(HKGroup):  # noqa: D101
    group = "body_measurements"


class Fitness(HKGroup):  # noqa: D101
    group = "fitness"


class ReproductiveHealth(HKGroup):  # noqa: D101
    group = "reproductive_health"


class Hearing(HKGroup):  # noqa: D101
    group = "hearing"


class VitalSigns(HKGroup):  # noqa: D101
    group = "vital_signs"


class LabTestResults(HKGroup):  # noqa: D101
    group = "lab_test_results"


class Mobility(HKGroup):  # noqa: D101
    group = "mobility"


class Nutrition(HKGroup):  # noqa: D101
    group = "nutrition"


class UVExposure(HKGroup):  # noqa: D101
    group = "uv_exposure"


class Diving(HKGroup):  # noqa: D101
    group = "diving"


class Mindfulness(HKGroup):  # noqa: D101
    group = "mindfulness"


class Symptoms(HKGroup):  # noqa: D101
    group = "symptoms"


class Other(HKGroup):  # noqa: D101
    group = "other"


# ---------------------------------------------------------------------------
# Group Registry
# ---------------------------------------------------------------------------

HK_GROUPS: MappingProxyType[str, Any] = MappingProxyType(
    {group.__name__: group for group in HKGroup.get_members()}
)


# ---------------------------------------------------------------------------
# Misc. data type(s) that don't fit the category/quantity type distinction
# ---------------------------------------------------------------------------


class HKDataTypeSleepDurationGoal(HKMiscTypeIdentifier, Fitness):  # noqa: D101
    pass


# ---------------------------------------------------------------------------
# Misc Registry
# ---------------------------------------------------------------------------


HKMiscTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    {group.__name__: group for group in HKMiscTypeIdentifier.__subclasses__()}
)
