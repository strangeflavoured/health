"""Numerical mappings for Apple Health categorical data types.

Each :class:`~enum.Enum` subclass corresponds to one
``HKCategoryTypeIdentifier`` and maps its string values to signed integers
suitable for storage in Redis TimeSeries.

The module-level :data:`categorical_identifier_maps` registry maps each
identifier string to its :class:`HKCategoryTypeIdentifier` member to  value map
"""

from enum import Enum

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
# Category type enums
# ---------------------------------------------------------------------------


class HKCategoryTypeIdentifier(Enum):
    """Sentinel categorical identifier values."""

    @classmethod
    def items(cls) -> dict[str, int]:
        """Return a dictionary of categorical identifier names and int values."""
        return {i.name: i.value for i in cls}


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
