"""Numerical mappings for Apple Health categorical data types.

Each :class:`~enum.Enum` subclass corresponds to one
``HKCategoryTypeIdentifier`` and maps its string values to signed integers
suitable for storage in Redis TimeSeries.

The module-level :data:`categorical_identifiers` registry maps each
identifier string to its :class:`~enum.Enum` class and is the sole entry
point used by the transform layer.
"""

from enum import Enum

import numpy as np

_NA_VALUE = -9999

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


class HKCategoryTypeIdentifierAppleStandHour(Enum):
    """Stand-hour category: whether the user stood during a given hour."""

    HKCategoryValueAppleStandHourIdle = 0
    HKCategoryValueAppleStandHourStood = 1


class HKCategoryTypeIdentifierAudioExposureEvent(Enum):
    """Environmental audio exposure events."""

    HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit = 1


class HKCategoryTypeIdentifierHeadphoneAudioExposureEvent(Enum):
    """Headphone audio exposure events."""

    HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit = 1


class HKCategoryTypeIdentifierHighHeartRateEvent(Enum):
    """High heart rate event — only legal value is *not applicable*."""

    HKCategoryValueNotApplicable = _NA_VALUE


class HKCategoryTypeIdentifierLowHeartRateEvent(Enum):
    """Low heart rate event — only legal value is *not applicable*."""

    HKCategoryValueNotApplicable = _NA_VALUE


class HKCategoryTypeIdentifierMindfulSession(Enum):
    """Mindful session — only legal value is *not applicable*."""

    HKCategoryValueNotApplicable = _NA_VALUE


class HKCategoryTypeIdentifierSleepAnalysis(Enum):
    """Sleep stage classifications.

    A negative value indicates wakefulness, NaN indicates an unclassified state, so that
    all sleep stages can be distinguished in time-series plots.
    """

    HKCategoryValueSleepAnalysisInBed = 0
    HKCategoryValueSleepAnalysisAsleepUnspecified = np.nan
    HKCategoryValueSleepAnalysisAsleepCore = 2
    HKCategoryValueSleepAnalysisAwake = -1
    HKCategoryValueSleepAnalysisAsleepDeep = 3
    HKCategoryValueSleepAnalysisAsleepREM = 1


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Maps each ``HKCategoryTypeIdentifier`` string to its :class:`~enum.Enum`
#: class.  Used by the transform layer to resolve categorical string values
#: to signed integers before writing to Redis TimeSeries.
categorical_identifiers: dict[str, type[Enum]] = {
    "HKCategoryTypeIdentifierAppleStandHour": HKCategoryTypeIdentifierAppleStandHour,
    "HKCategoryTypeIdentifierAudioExposureEvent": (
        HKCategoryTypeIdentifierAudioExposureEvent
    ),
    "HKCategoryTypeIdentifierHeadphoneAudioExposureEvent": (
        HKCategoryTypeIdentifierHeadphoneAudioExposureEvent
    ),
    "HKCategoryTypeIdentifierHighHeartRateEvent": (
        HKCategoryTypeIdentifierHighHeartRateEvent
    ),
    "HKCategoryTypeIdentifierLowHeartRateEvent": (
        HKCategoryTypeIdentifierLowHeartRateEvent
    ),
    "HKCategoryTypeIdentifierMindfulSession": HKCategoryTypeIdentifierMindfulSession,
    "HKCategoryTypeIdentifierSleepAnalysis": HKCategoryTypeIdentifierSleepAnalysis,
}
