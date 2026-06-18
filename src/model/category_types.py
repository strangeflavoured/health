"""Category Type model classes.

Provides HKCategoryTypeIdentifierRegistry to public API.

Each ``HKCategoryTypeIdentifier*`` class is a thin, generated stub mirroring one
Apple HealthKit ``HKCategoryTypeIdentifier``. The nested ``Values`` enum encodes
the categorical values Apple defines for that identifier; the class name is the
canonical identifier and per-identifier semantics follow Apple's official
HealthKit documentation. See :mod:`model.base` for the shared base class and
grouping definitions.
"""

from enum import Enum
from types import MappingProxyType
from typing import Any

from .base import (
    Fitness,
    Hearing,
    HKCategoryTypeIdentifier,
    Other,
    ReproductiveHealth,
    Symptoms,
    VitalSigns,
)


class HKCategoryTypeIdentifierSleepAnalysis(HKCategoryTypeIdentifier, Fitness):
    class Values(Enum):
        HKCategoryValueSleepAnalysisInBed = 0
        HKCategoryValueSleepAnalysisAsleepUnspecified = 1
        HKCategoryValueSleepAnalysisAwake = 2
        HKCategoryValueSleepAnalysisAsleepCore = 3
        HKCategoryValueSleepAnalysisAsleepDeep = 4
        HKCategoryValueSleepAnalysisAsleepREM = 5


class HKCategoryTypeIdentifierAppleStandHour(HKCategoryTypeIdentifier, Fitness):
    class Values(Enum):
        HKCategoryValueAppleStandHourIdle = 0
        HKCategoryValueAppleStandHourStood = 1


class HKCategoryTypeIdentifierMindfulSession(HKCategoryTypeIdentifier, Fitness):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierLowCardioFitnessEvent(HKCategoryTypeIdentifier, Fitness):
    class Values(Enum):
        HKCategoryValueLowCardioFitnessEventLowFitness = 0


class HKCategoryTypeIdentifierAppleWalkingSteadinessEvent(
    HKCategoryTypeIdentifier, Fitness
):
    class Values(Enum):
        HKCategoryValueAppleWalkingSteadinessEventInitialLow = 0
        HKCategoryValueAppleWalkingSteadinessEventInitialVeryLow = 1
        HKCategoryValueAppleWalkingSteadinessEventRepeatLow = 2
        HKCategoryValueAppleWalkingSteadinessEventRepeatVeryLow = 3


class HKCategoryTypeIdentifierMenstrualFlow(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueMenstrualFlowUnspecified = 0
        HKCategoryValueMenstrualFlowLight = 1
        HKCategoryValueMenstrualFlowMedium = 2
        HKCategoryValueMenstrualFlowHeavy = 3
        HKCategoryValueMenstrualFlowNone = 4


class HKCategoryTypeIdentifierIntermenstrualBleeding(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierInfrequentMenstrualCycles(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierIrregularMenstrualCycles(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierPersistentIntermenstrualBleeding(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierProlongedMenstrualPeriods(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierBleedingAfterPregnancy(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierBleedingDuringPregnancy(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierSexualActivity(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierOvulationTestResult(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueOvulationTestResultNegative = 0
        HKCategoryValueOvulationTestResultLuteinizingHormoneSurge = 1
        HKCategoryValueOvulationTestResultIndeterminate = 2
        HKCategoryValueOvulationTestResultEstrogenSurge = 3


class HKCategoryTypeIdentifierCervicalMucusQuality(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueCervicalMucusQualityDry = 0
        HKCategoryValueCervicalMucusQualitySticky = 1
        HKCategoryValueCervicalMucusQualityCreamy = 2
        HKCategoryValueCervicalMucusQualityWatery = 3
        HKCategoryValueCervicalMucusQualityEggWhite = 4


class HKCategoryTypeIdentifierPregnancy(HKCategoryTypeIdentifier, ReproductiveHealth):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierLactation(HKCategoryTypeIdentifier, ReproductiveHealth):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierContraceptive(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueContraceptiveUnspecified = 0
        HKCategoryValueContraceptiveImplant = 1
        HKCategoryValueContraceptiveInjection = 2
        HKCategoryValueContraceptiveIntrauterineDevice = 3
        HKCategoryValueContraceptiveIntravaginalRingOrPatch = 4
        HKCategoryValueContraceptiveOral = 5
        HKCategoryValueContraceptivePatch = 6


class HKCategoryTypeIdentifierPregnancyTestResult(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValuePregnancyTestResultNegative = 0
        HKCategoryValuePregnancyTestResultPositive = 1
        HKCategoryValuePregnancyTestResultIndeterminate = 2


class HKCategoryTypeIdentifierProgesteroneTestResult(
    HKCategoryTypeIdentifier, ReproductiveHealth
):
    class Values(Enum):
        HKCategoryValueProgesteroneTestResultNegative = 0
        HKCategoryValueProgesteroneTestResultPositive = 1
        HKCategoryValueProgesteroneTestResultIndeterminate = 2


class HKCategoryTypeIdentifierAudioExposureEvent(HKCategoryTypeIdentifier, Hearing):
    class Values(Enum):
        HKCategoryValueAudioExposureEventLoudEnvironment = 0


class HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent(
    HKCategoryTypeIdentifier, Hearing
):
    class Values(Enum):
        HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit = 0


class HKCategoryTypeIdentifierHeadphoneAudioExposureEvent(
    HKCategoryTypeIdentifier, Hearing
):
    class Values(Enum):
        HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit = 0


class HKCategoryTypeIdentifierHighHeartRateEvent(HKCategoryTypeIdentifier, VitalSigns):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierLowHeartRateEvent(HKCategoryTypeIdentifier, VitalSigns):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierIrregularHeartRhythmEvent(
    HKCategoryTypeIdentifier, VitalSigns
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierSleepApneaEvent(HKCategoryTypeIdentifier, VitalSigns):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierHypertensionEvent(HKCategoryTypeIdentifier, VitalSigns):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierAbdominalCramps(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierAcne(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierAppetiteChanges(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueAppetiteChangesUnspecified = 0
        HKCategoryValueAppetiteChangesNoChange = 1
        HKCategoryValueAppetiteChangesDecreased = 2
        HKCategoryValueAppetiteChangesIncreased = 3


class HKCategoryTypeIdentifierBladderIncontinence(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierBloating(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierBreastPain(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierChestTightnessOrPain(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierChills(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierConstipation(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierCoughing(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierDiarrhea(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierDizziness(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierDrySkin(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierFainting(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierFatigue(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierFever(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierGeneralizedBodyAche(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHairLoss(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHeadache(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHeartburn(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHotFlashes(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierLossOfSmell(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierLossOfTaste(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierLowerBackPain(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierMemoryLapse(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierMoodChanges(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValuePresencePresent = 0
        HKCategoryValuePresenceNotPresent = 1


class HKCategoryTypeIdentifierNausea(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierNightSweats(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierPelvicPain(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat(
    HKCategoryTypeIdentifier, Symptoms
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierRunnyNose(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierShortnessOfBreath(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierSinusCongestion(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierSkippedHeartbeat(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierSleepChanges(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValuePresencePresent = 0
        HKCategoryValuePresenceNotPresent = 1


class HKCategoryTypeIdentifierSoreThroat(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierVaginalDryness(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierVomiting(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierWheezing(HKCategoryTypeIdentifier, Symptoms):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierToothbrushingEvent(HKCategoryTypeIdentifier, Other):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierHandwashingEvent(HKCategoryTypeIdentifier, Other):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HKCategoryTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    {subcls.__name__: subcls for subcls in HKCategoryTypeIdentifier.__subclasses__()}
)
