"""Category Type model classes.

Provides HKCategoryTypeIdentifierRegistry to public API.
"""

from enum import Enum
from types import MappingProxyType
from typing import Any

from .base import HK_GROUPS, HKCategoryTypeIdentifier


class HKCategoryTypeIdentifierSleepAnalysis(
    HKCategoryTypeIdentifier, HK_GROUPS["Fitness"]
):
    class Values(Enum):
        HKCategoryValueSleepAnalysisInBed = 0
        HKCategoryValueSleepAnalysisAsleepUnspecified = 1
        HKCategoryValueSleepAnalysisAwake = 2
        HKCategoryValueSleepAnalysisAsleepCore = 3
        HKCategoryValueSleepAnalysisAsleepDeep = 4
        HKCategoryValueSleepAnalysisAsleepREM = 5


class HKCategoryTypeIdentifierAppleStandHour(
    HKCategoryTypeIdentifier, HK_GROUPS["Fitness"]
):
    class Values(Enum):
        HKCategoryValueAppleStandHourIdle = 0
        HKCategoryValueAppleStandHourStood = 1


class HKCategoryTypeIdentifierMindfulSession(
    HKCategoryTypeIdentifier, HK_GROUPS["Fitness"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierLowCardioFitnessEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Fitness"]
):
    class Values(Enum):
        HKCategoryValueLowCardioFitnessEventLowFitness = 0


class HKCategoryTypeIdentifierAppleWalkingSteadinessEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Fitness"]
):
    class Values(Enum):
        HKCategoryValueAppleWalkingSteadinessEventInitialLow = 0
        HKCategoryValueAppleWalkingSteadinessEventInitialVeryLow = 1
        HKCategoryValueAppleWalkingSteadinessEventRepeatLow = 2
        HKCategoryValueAppleWalkingSteadinessEventRepeatVeryLow = 3


class HKCategoryTypeIdentifierMenstrualFlow(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueMenstrualFlowUnspecified = 0
        HKCategoryValueMenstrualFlowLight = 1
        HKCategoryValueMenstrualFlowMedium = 2
        HKCategoryValueMenstrualFlowHeavy = 3
        HKCategoryValueMenstrualFlowNone = 4


class HKCategoryTypeIdentifierIntermenstrualBleeding(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierInfrequentMenstrualCycles(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierIrregularMenstrualCycles(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierPersistentIntermenstrualBleeding(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierProlongedMenstrualPeriods(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierBleedingAfterPregnancy(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierBleedingDuringPregnancy(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierSexualActivity(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierOvulationTestResult(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueOvulationTestResultNegative = 0
        HKCategoryValueOvulationTestResultLuteinizingHormoneSurge = 1
        HKCategoryValueOvulationTestResultIndeterminate = 2
        HKCategoryValueOvulationTestResultEstrogenSurge = 3


class HKCategoryTypeIdentifierCervicalMucusQuality(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueCervicalMucusQualityDry = 0
        HKCategoryValueCervicalMucusQualitySticky = 1
        HKCategoryValueCervicalMucusQualityCreamy = 2
        HKCategoryValueCervicalMucusQualityWatery = 3
        HKCategoryValueCervicalMucusQualityEggWhite = 4


class HKCategoryTypeIdentifierPregnancy(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierLactation(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierContraceptive(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
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
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValuePregnancyTestResultNegative = 0
        HKCategoryValuePregnancyTestResultPositive = 1
        HKCategoryValuePregnancyTestResultIndeterminate = 2


class HKCategoryTypeIdentifierProgesteroneTestResult(
    HKCategoryTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    class Values(Enum):
        HKCategoryValueProgesteroneTestResultNegative = 0
        HKCategoryValueProgesteroneTestResultPositive = 1
        HKCategoryValueProgesteroneTestResultIndeterminate = 2


class HKCategoryTypeIdentifierAudioExposureEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Hearing"]
):
    class Values(Enum):
        HKCategoryValueAudioExposureEventLoudEnvironment = 0
        HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit = 1


class HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Hearing"]
):
    class Values(Enum):
        HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit = 0


class HKCategoryTypeIdentifierHeadphoneAudioExposureEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Hearing"]
):
    class Values(Enum):
        HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit = 0


class HKCategoryTypeIdentifierHighHeartRateEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierLowHeartRateEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierIrregularHeartRhythmEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierSleepApneaEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierHypertensionEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierAbdominalCramps(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierAcne(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierAppetiteChanges(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueAppetiteChangesUnspecified = 0
        HKCategoryValueAppetiteChangesNoChange = 1
        HKCategoryValueAppetiteChangesDecreased = 2
        HKCategoryValueAppetiteChangesIncreased = 3


class HKCategoryTypeIdentifierBladderIncontinence(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierBloating(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierBreastPain(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierChestTightnessOrPain(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierChills(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierConstipation(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierCoughing(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierDiarrhea(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierDizziness(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierDrySkin(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierFainting(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierFatigue(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierFever(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierGeneralizedBodyAche(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHairLoss(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHeadache(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHeartburn(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierHotFlashes(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierLossOfSmell(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierLossOfTaste(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierLowerBackPain(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierMemoryLapse(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierMoodChanges(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValuePresencePresent = 0
        HKCategoryValuePresenceNotPresent = 1


class HKCategoryTypeIdentifierNausea(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierNightSweats(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierPelvicPain(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierRunnyNose(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierShortnessOfBreath(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierSinusCongestion(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierSkippedHeartbeat(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierSleepChanges(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValuePresencePresent = 0
        HKCategoryValuePresenceNotPresent = 1


class HKCategoryTypeIdentifierSoreThroat(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierVaginalDryness(
    HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]
):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierVomiting(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierWheezing(HKCategoryTypeIdentifier, HK_GROUPS["Symptoms"]):
    class Values(Enum):
        HKCategoryValueSeverityUnspecified = 0
        HKCategoryValueSeverityNotPresent = 1
        HKCategoryValueSeverityMild = 2
        HKCategoryValueSeverityModerate = 3
        HKCategoryValueSeveritySevere = 4


class HKCategoryTypeIdentifierToothbrushingEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Other"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


class HKCategoryTypeIdentifierHandwashingEvent(
    HKCategoryTypeIdentifier, HK_GROUPS["Other"]
):
    class Values(Enum):
        HKCategoryValueNotApplicable = 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HKCategoryTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    {
        "HKCategoryTypeIdentifierAbdominalCramps": (
            HKCategoryTypeIdentifierAbdominalCramps
        ),
        "HKCategoryTypeIdentifierAcne": (HKCategoryTypeIdentifierAcne),
        "HKCategoryTypeIdentifierAppetiteChanges": (
            HKCategoryTypeIdentifierAppetiteChanges
        ),
        "HKCategoryTypeIdentifierAppleStandHour": (
            HKCategoryTypeIdentifierAppleStandHour
        ),
        "HKCategoryTypeIdentifierAppleWalkingSteadinessEvent": (
            HKCategoryTypeIdentifierAppleWalkingSteadinessEvent
        ),
        "HKCategoryTypeIdentifierAudioExposureEvent": (
            HKCategoryTypeIdentifierAudioExposureEvent
        ),
        "HKCategoryTypeIdentifierBladderIncontinence": (
            HKCategoryTypeIdentifierBladderIncontinence
        ),
        "HKCategoryTypeIdentifierBleedingAfterPregnancy": (
            HKCategoryTypeIdentifierBleedingAfterPregnancy
        ),
        "HKCategoryTypeIdentifierBleedingDuringPregnancy": (
            HKCategoryTypeIdentifierBleedingDuringPregnancy
        ),
        "HKCategoryTypeIdentifierBloating": (HKCategoryTypeIdentifierBloating),
        "HKCategoryTypeIdentifierBreastPain": (HKCategoryTypeIdentifierBreastPain),
        "HKCategoryTypeIdentifierCervicalMucusQuality": (
            HKCategoryTypeIdentifierCervicalMucusQuality
        ),
        "HKCategoryTypeIdentifierChestTightnessOrPain": (
            HKCategoryTypeIdentifierChestTightnessOrPain
        ),
        "HKCategoryTypeIdentifierChills": (HKCategoryTypeIdentifierChills),
        "HKCategoryTypeIdentifierConstipation": (HKCategoryTypeIdentifierConstipation),
        "HKCategoryTypeIdentifierContraceptive": (
            HKCategoryTypeIdentifierContraceptive
        ),
        "HKCategoryTypeIdentifierCoughing": (HKCategoryTypeIdentifierCoughing),
        "HKCategoryTypeIdentifierDiarrhea": (HKCategoryTypeIdentifierDiarrhea),
        "HKCategoryTypeIdentifierDizziness": (HKCategoryTypeIdentifierDizziness),
        "HKCategoryTypeIdentifierDrySkin": (HKCategoryTypeIdentifierDrySkin),
        "HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent": (
            HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent
        ),
        "HKCategoryTypeIdentifierFainting": (HKCategoryTypeIdentifierFainting),
        "HKCategoryTypeIdentifierFatigue": (HKCategoryTypeIdentifierFatigue),
        "HKCategoryTypeIdentifierFever": (HKCategoryTypeIdentifierFever),
        "HKCategoryTypeIdentifierGeneralizedBodyAche": (
            HKCategoryTypeIdentifierGeneralizedBodyAche
        ),
        "HKCategoryTypeIdentifierHairLoss": (HKCategoryTypeIdentifierHairLoss),
        "HKCategoryTypeIdentifierHandwashingEvent": (
            HKCategoryTypeIdentifierHandwashingEvent
        ),
        "HKCategoryTypeIdentifierHeadache": (HKCategoryTypeIdentifierHeadache),
        "HKCategoryTypeIdentifierHeadphoneAudioExposureEvent": (
            HKCategoryTypeIdentifierHeadphoneAudioExposureEvent
        ),
        "HKCategoryTypeIdentifierHeartburn": (HKCategoryTypeIdentifierHeartburn),
        "HKCategoryTypeIdentifierHighHeartRateEvent": (
            HKCategoryTypeIdentifierHighHeartRateEvent
        ),
        "HKCategoryTypeIdentifierHotFlashes": (HKCategoryTypeIdentifierHotFlashes),
        "HKCategoryTypeIdentifierHypertensionEvent": (
            HKCategoryTypeIdentifierHypertensionEvent
        ),
        "HKCategoryTypeIdentifierInfrequentMenstrualCycles": (
            HKCategoryTypeIdentifierInfrequentMenstrualCycles
        ),
        "HKCategoryTypeIdentifierIntermenstrualBleeding": (
            HKCategoryTypeIdentifierIntermenstrualBleeding
        ),
        "HKCategoryTypeIdentifierIrregularHeartRhythmEvent": (
            HKCategoryTypeIdentifierIrregularHeartRhythmEvent
        ),
        "HKCategoryTypeIdentifierIrregularMenstrualCycles": (
            HKCategoryTypeIdentifierIrregularMenstrualCycles
        ),
        "HKCategoryTypeIdentifierLactation": (HKCategoryTypeIdentifierLactation),
        "HKCategoryTypeIdentifierLossOfSmell": (HKCategoryTypeIdentifierLossOfSmell),
        "HKCategoryTypeIdentifierLossOfTaste": (HKCategoryTypeIdentifierLossOfTaste),
        "HKCategoryTypeIdentifierLowCardioFitnessEvent": (
            HKCategoryTypeIdentifierLowCardioFitnessEvent
        ),
        "HKCategoryTypeIdentifierLowHeartRateEvent": (
            HKCategoryTypeIdentifierLowHeartRateEvent
        ),
        "HKCategoryTypeIdentifierLowerBackPain": (
            HKCategoryTypeIdentifierLowerBackPain
        ),
        "HKCategoryTypeIdentifierMemoryLapse": (HKCategoryTypeIdentifierMemoryLapse),
        "HKCategoryTypeIdentifierMenstrualFlow": (
            HKCategoryTypeIdentifierMenstrualFlow
        ),
        "HKCategoryTypeIdentifierMindfulSession": (
            HKCategoryTypeIdentifierMindfulSession
        ),
        "HKCategoryTypeIdentifierMoodChanges": (HKCategoryTypeIdentifierMoodChanges),
        "HKCategoryTypeIdentifierNausea": (HKCategoryTypeIdentifierNausea),
        "HKCategoryTypeIdentifierNightSweats": (HKCategoryTypeIdentifierNightSweats),
        "HKCategoryTypeIdentifierOvulationTestResult": (
            HKCategoryTypeIdentifierOvulationTestResult
        ),
        "HKCategoryTypeIdentifierPelvicPain": (HKCategoryTypeIdentifierPelvicPain),
        "HKCategoryTypeIdentifierPersistentIntermenstrualBleeding": (
            HKCategoryTypeIdentifierPersistentIntermenstrualBleeding
        ),
        "HKCategoryTypeIdentifierPregnancy": (HKCategoryTypeIdentifierPregnancy),
        "HKCategoryTypeIdentifierPregnancyTestResult": (
            HKCategoryTypeIdentifierPregnancyTestResult
        ),
        "HKCategoryTypeIdentifierProgesteroneTestResult": (
            HKCategoryTypeIdentifierProgesteroneTestResult
        ),
        "HKCategoryTypeIdentifierProlongedMenstrualPeriods": (
            HKCategoryTypeIdentifierProlongedMenstrualPeriods
        ),
        "HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat": (
            HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat
        ),
        "HKCategoryTypeIdentifierRunnyNose": (HKCategoryTypeIdentifierRunnyNose),
        "HKCategoryTypeIdentifierSexualActivity": (
            HKCategoryTypeIdentifierSexualActivity
        ),
        "HKCategoryTypeIdentifierShortnessOfBreath": (
            HKCategoryTypeIdentifierShortnessOfBreath
        ),
        "HKCategoryTypeIdentifierSinusCongestion": (
            HKCategoryTypeIdentifierSinusCongestion
        ),
        "HKCategoryTypeIdentifierSkippedHeartbeat": (
            HKCategoryTypeIdentifierSkippedHeartbeat
        ),
        "HKCategoryTypeIdentifierSleepAnalysis": (
            HKCategoryTypeIdentifierSleepAnalysis
        ),
        "HKCategoryTypeIdentifierSleepApneaEvent": (
            HKCategoryTypeIdentifierSleepApneaEvent
        ),
        "HKCategoryTypeIdentifierSleepChanges": (HKCategoryTypeIdentifierSleepChanges),
        "HKCategoryTypeIdentifierSoreThroat": (HKCategoryTypeIdentifierSoreThroat),
        "HKCategoryTypeIdentifierToothbrushingEvent": (
            HKCategoryTypeIdentifierToothbrushingEvent
        ),
        "HKCategoryTypeIdentifierVaginalDryness": (
            HKCategoryTypeIdentifierVaginalDryness
        ),
        "HKCategoryTypeIdentifierVomiting": (HKCategoryTypeIdentifierVomiting),
        "HKCategoryTypeIdentifierWheezing": (HKCategoryTypeIdentifierWheezing),
    }
)
