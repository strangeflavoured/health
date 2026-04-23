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


class HKCategoryTypeIdentifier(HKIdentifier, Enum):
    """Sentinel categorical identifier values."""

    identifier_type = "category"

    @classmethod
    def items(cls) -> dict[str, int]:
        """Return a dictionary of categorical identifier names and int values."""
        return {i.name: i.value for i in cls}


# ---------------------------------------------------------------------------
# Category type enums
# ---------------------------------------------------------------------------


class HKCategoryTypeIdentifierAppleStandHour(HKCategoryTypeIdentifier):
    """Stand-hour category: whether the user stood during a given hour."""

    HKCategoryValueAppleStandHourIdle = 0
    HKCategoryValueAppleStandHourStood = 1


class HKCategoryTypeIdentifierAudioExposureEvent(HKCategoryTypeIdentifier):
    """Environmental audio exposure events."""

    HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit = 1


class HKCategoryTypeIdentifierHeadphoneAudioExposureEvent(HKCategoryTypeIdentifier):
    """Headphone audio exposure events."""

    HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit = 1


class HKCategoryTypeIdentifierHighHeartRateEvent(HKCategoryTypeIdentifier):
    """High heart rate events."""

    HKCategoryValueNotApplicable = 1


class HKCategoryTypeIdentifierLowHeartRateEvent(HKCategoryTypeIdentifier):
    """Low heart rate events."""

    HKCategoryValueNotApplicable = 1


class HKCategoryTypeIdentifierMindfulSession(HKCategoryTypeIdentifier):
    """Mindful sessions."""

    HKCategoryValueNotApplicable = 1


class HKCategoryTypeIdentifierSleepAnalysis(HKCategoryTypeIdentifier):
    """Sleep stage classifications.

    A negative value indicates wakefulness, and increasing values indicate
    deeper sleep.
    """

    HKCategoryValueSleepAnalysisAwake = -1
    HKCategoryValueSleepAnalysisInBed = 0
    HKCategoryValueSleepAnalysisAsleepUnspecified = 1
    HKCategoryValueSleepAnalysisAsleepREM = 2
    HKCategoryValueSleepAnalysisAsleepCore = 3
    HKCategoryValueSleepAnalysisAsleepDeep = 4


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Maps each ``HKCategoryTypeIdentifier`` string to a map of its
# :class:`HKCategoryTypeIdentifier` members to their int values.
categorical_identifier_maps: dict[str, dict[str, int]] = {
    "HKCategoryTypeIdentifierAppleStandHour": (
        HKCategoryTypeIdentifierAppleStandHour.items()
    ),
    "HKCategoryTypeIdentifierAudioExposureEvent": (
        HKCategoryTypeIdentifierAudioExposureEvent.items()
    ),
    "HKCategoryTypeIdentifierHeadphoneAudioExposureEvent": (
        HKCategoryTypeIdentifierHeadphoneAudioExposureEvent.items()
    ),
    "HKCategoryTypeIdentifierHighHeartRateEvent": (
        HKCategoryTypeIdentifierHighHeartRateEvent.items()
    ),
    "HKCategoryTypeIdentifierLowHeartRateEvent": (
        HKCategoryTypeIdentifierLowHeartRateEvent.items()
    ),
    "HKCategoryTypeIdentifierMindfulSession": (
        HKCategoryTypeIdentifierMindfulSession.items()
    ),
    "HKCategoryTypeIdentifierSleepAnalysis": (
        HKCategoryTypeIdentifierSleepAnalysis.items()
    ),
}

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
