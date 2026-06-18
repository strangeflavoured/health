"""Quantity Type model classes.

Provides HKQuantityTypeIdentifierRegistry to public API.

Each ``HKQuantityTypeIdentifier*`` class is a thin, generated stub mirroring one
Apple HealthKit ``HKQuantityTypeIdentifier``. Per-identifier semantics (units,
aggregation style, grouping) follow Apple's official HealthKit documentation and
are encoded as class attributes rather than prose docstrings; the class name is
the canonical identifier. See :mod:`model.base` for the shared base class and
grouping definitions.
"""

from types import MappingProxyType
from typing import Any

from .base import (
    BodyMeasurements,
    Diving,
    Fitness,
    Hearing,
    HKQuantityTypeIdentifier,
    LabTestResults,
    Mindfulness,
    Mobility,
    Nutrition,
    ReproductiveHealth,
    UVExposure,
    VitalSigns,
)


class HKQuantityTypeIdentifierBodyMassIndex(HKQuantityTypeIdentifier, BodyMeasurements):
    unit = "count"


class HKQuantityTypeIdentifierBodyFatPercentage(
    HKQuantityTypeIdentifier, BodyMeasurements
):
    unit = "%"


class HKQuantityTypeIdentifierHeight(HKQuantityTypeIdentifier, BodyMeasurements):
    unit = "cm"


class HKQuantityTypeIdentifierBodyMass(HKQuantityTypeIdentifier, BodyMeasurements):
    unit = "kg"


class HKQuantityTypeIdentifierLeanBodyMass(HKQuantityTypeIdentifier, BodyMeasurements):
    unit = "kg"


class HKQuantityTypeIdentifierWaistCircumference(
    HKQuantityTypeIdentifier, BodyMeasurements
):
    unit = "cm"


class HKQuantityTypeIdentifierStepCount(HKQuantityTypeIdentifier, Fitness):
    unit = "count"


class HKQuantityTypeIdentifierDistanceWalkingRunning(HKQuantityTypeIdentifier, Fitness):
    unit = "km"


class HKQuantityTypeIdentifierDistanceCycling(HKQuantityTypeIdentifier, Fitness):
    unit = "km"


class HKQuantityTypeIdentifierDistanceWheelchair(HKQuantityTypeIdentifier, Fitness):
    unit = "km"


class HKQuantityTypeIdentifierDistanceSwimming(HKQuantityTypeIdentifier, Fitness):
    unit = "m"


class HKQuantityTypeIdentifierDistanceDownhillSnowSports(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceCrossCountrySkiing(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "km"


class HKQuantityTypeIdentifierDistancePaddleSports(HKQuantityTypeIdentifier, Fitness):
    unit = "km"


class HKQuantityTypeIdentifierDistanceRowing(HKQuantityTypeIdentifier, Fitness):
    unit = "km"


class HKQuantityTypeIdentifierDistanceSkatingSports(HKQuantityTypeIdentifier, Fitness):
    unit = "km"


class HKQuantityTypeIdentifierFlightsClimbed(HKQuantityTypeIdentifier, Fitness):
    unit = "count"


class HKQuantityTypeIdentifierPushCount(HKQuantityTypeIdentifier, Fitness):
    unit = "count"


class HKQuantityTypeIdentifierSwimmingStrokeCount(HKQuantityTypeIdentifier, Fitness):
    unit = "count"


class HKQuantityTypeIdentifierBasalEnergyBurned(HKQuantityTypeIdentifier, Fitness):
    unit = "kcal"


class HKQuantityTypeIdentifierActiveEnergyBurned(HKQuantityTypeIdentifier, Fitness):
    unit = "kcal"


class HKQuantityTypeIdentifierAppleExerciseTime(HKQuantityTypeIdentifier, Fitness):
    unit = "min"


class HKQuantityTypeIdentifierAppleMoveTime(HKQuantityTypeIdentifier, Fitness):
    unit = "min"


class HKQuantityTypeIdentifierAppleStandTime(HKQuantityTypeIdentifier, Fitness):
    unit = "min"


class HKQuantityTypeIdentifierVO2Max(HKQuantityTypeIdentifier, Fitness):
    unit = "mL/min·kg"


class HKQuantityTypeIdentifierRunningSpeed(HKQuantityTypeIdentifier, Fitness):
    unit = "km/hr"


class HKQuantityTypeIdentifierRunningPower(HKQuantityTypeIdentifier, Fitness):
    unit = "W"


class HKQuantityTypeIdentifierRunningGroundContactTime(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "ms"


class HKQuantityTypeIdentifierRunningStrideLength(HKQuantityTypeIdentifier, Fitness):
    unit = "m"


class HKQuantityTypeIdentifierRunningVerticalOscillation(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "cm"


class HKQuantityTypeIdentifierCyclingSpeed(HKQuantityTypeIdentifier, Fitness):
    unit = "km/hr"


class HKQuantityTypeIdentifierCyclingPower(HKQuantityTypeIdentifier, Fitness):
    unit = "W"


class HKQuantityTypeIdentifierCyclingCadence(HKQuantityTypeIdentifier, Fitness):
    unit = "rpm"


class HKQuantityTypeIdentifierCyclingFunctionalThresholdPower(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "W"


class HKQuantityTypeIdentifierCrossCountrySkiingSpeed(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "km/hr"


class HKQuantityTypeIdentifierPaddleSportsSpeed(HKQuantityTypeIdentifier, Fitness):
    unit = "km/hr"


class HKQuantityTypeIdentifierRowingSpeed(HKQuantityTypeIdentifier, Fitness):
    unit = "km/hr"


class HKQuantityTypeIdentifierPhysicalEffort(HKQuantityTypeIdentifier, Fitness):
    unit = "kcal/hr·kg"


class HKQuantityTypeIdentifierWorkoutEffortScore(HKQuantityTypeIdentifier, Fitness):
    unit = "appleEffortScore"


class HKQuantityTypeIdentifierEstimatedWorkoutEffortScore(
    HKQuantityTypeIdentifier, Fitness
):
    unit = "appleEffortScore"


class HKQuantityTypeIdentifierBasalBodyTemperature(
    HKQuantityTypeIdentifier, ReproductiveHealth
):
    unit = "degC"


class HKQuantityTypeIdentifierEnvironmentalAudioExposure(
    HKQuantityTypeIdentifier, Hearing
):
    unit = "dBASPL"


class HKQuantityTypeIdentifierHeadphoneAudioExposure(HKQuantityTypeIdentifier, Hearing):
    unit = "dBASPL"


class HKQuantityTypeIdentifierEnvironmentalSoundReduction(
    HKQuantityTypeIdentifier, Hearing
):
    unit = "dBASPL"


class HKQuantityTypeIdentifierHeartRate(HKQuantityTypeIdentifier, VitalSigns):
    unit = "count/min"


class HKQuantityTypeIdentifierRestingHeartRate(HKQuantityTypeIdentifier, VitalSigns):
    unit = "count/min"


class HKQuantityTypeIdentifierWalkingHeartRateAverage(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "count/min"


class HKQuantityTypeIdentifierHeartRateRecoveryOneMinute(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "count/min"


class HKQuantityTypeIdentifierHeartRateVariabilitySDNN(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "ms"


class HKQuantityTypeIdentifierAtrialFibrillationBurden(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "%"


class HKQuantityTypeIdentifierOxygenSaturation(HKQuantityTypeIdentifier, VitalSigns):
    unit = "%"


class HKQuantityTypeIdentifierBloodPressureSystolic(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "mmHg"


class HKQuantityTypeIdentifierBloodPressureDiastolic(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "mmHg"


class HKQuantityTypeIdentifierRespiratoryRate(HKQuantityTypeIdentifier, VitalSigns):
    unit = "count/min"


class HKQuantityTypeIdentifierBodyTemperature(HKQuantityTypeIdentifier, VitalSigns):
    unit = "degC"


class HKQuantityTypeIdentifierAppleSleepingWristTemperature(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "degC"


class HKQuantityTypeIdentifierAppleSleepingBreathingDisturbances(
    HKQuantityTypeIdentifier, VitalSigns
):
    unit = "count"


# Apple Health exports glucose units as the literal string
# "mmol<180.15588...>/L" — the bracketed number is the molar mass
# of glucose, used by HealthKit to convert to/from mg/dL.  We expose the
# clean SI unit here; downstream code that needs the conversion factor
# should reference :data:`MMOL_PER_L_TO_MG_PER_DL_GLUCOSE` below.
MMOL_PER_L_TO_MG_PER_DL_GLUCOSE: float = 18.01558800000541  # 1 mmol/L = 18.02 mg/dL


class HKQuantityTypeIdentifierBloodGlucose(HKQuantityTypeIdentifier, LabTestResults):
    unit = "mmol/L"


class HKQuantityTypeIdentifierBloodAlcoholContent(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "%"


class HKQuantityTypeIdentifierPeripheralPerfusionIndex(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "%"


class HKQuantityTypeIdentifierForcedVitalCapacity(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "L"


class HKQuantityTypeIdentifierForcedExpiratoryVolume1(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "L"


class HKQuantityTypeIdentifierPeakExpiratoryFlowRate(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "L/min"


class HKQuantityTypeIdentifierInhalerUsage(HKQuantityTypeIdentifier, LabTestResults):
    unit = "count"


class HKQuantityTypeIdentifierNumberOfTimesFallen(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "count"


class HKQuantityTypeIdentifierElectrodermalActivity(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "mcS"


class HKQuantityTypeIdentifierInsulinDelivery(HKQuantityTypeIdentifier, LabTestResults):
    unit = "IU"


class HKQuantityTypeIdentifierNumberOfAlcoholicBeverages(
    HKQuantityTypeIdentifier, LabTestResults
):
    unit = "count"


class HKQuantityTypeIdentifierWalkingSpeed(HKQuantityTypeIdentifier, Mobility):
    unit = "km/hr"


class HKQuantityTypeIdentifierWalkingStepLength(HKQuantityTypeIdentifier, Mobility):
    unit = "cm"


class HKQuantityTypeIdentifierWalkingAsymmetryPercentage(
    HKQuantityTypeIdentifier, Mobility
):
    unit = "%"


class HKQuantityTypeIdentifierWalkingDoubleSupportPercentage(
    HKQuantityTypeIdentifier, Mobility
):
    unit = "%"


class HKQuantityTypeIdentifierAppleWalkingSteadiness(
    HKQuantityTypeIdentifier, Mobility
):
    unit = "%"


class HKQuantityTypeIdentifierSixMinuteWalkTestDistance(
    HKQuantityTypeIdentifier, Mobility
):
    unit = "m"


class HKQuantityTypeIdentifierStairAscentSpeed(HKQuantityTypeIdentifier, Mobility):
    unit = "m/s"


class HKQuantityTypeIdentifierStairDescentSpeed(HKQuantityTypeIdentifier, Mobility):
    unit = "m/s"


class HKQuantityTypeIdentifierDietaryEnergyConsumed(
    HKQuantityTypeIdentifier, Nutrition
):
    unit = "kcal"


class HKQuantityTypeIdentifierDietaryFatTotal(HKQuantityTypeIdentifier, Nutrition):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFatPolyunsaturated(
    HKQuantityTypeIdentifier, Nutrition
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFatMonounsaturated(
    HKQuantityTypeIdentifier, Nutrition
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFatSaturated(HKQuantityTypeIdentifier, Nutrition):
    unit = "g"


class HKQuantityTypeIdentifierDietaryCholesterol(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietarySodium(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryCarbohydrates(HKQuantityTypeIdentifier, Nutrition):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFiber(HKQuantityTypeIdentifier, Nutrition):
    unit = "g"


class HKQuantityTypeIdentifierDietarySugar(HKQuantityTypeIdentifier, Nutrition):
    unit = "g"


class HKQuantityTypeIdentifierDietaryProtein(HKQuantityTypeIdentifier, Nutrition):
    unit = "g"


class HKQuantityTypeIdentifierDietaryVitaminA(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryVitaminB6(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryVitaminB12(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryVitaminC(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryVitaminD(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryVitaminE(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryVitaminK(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryCalcium(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryIron(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryThiamin(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryRiboflavin(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryNiacin(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryFolate(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryBiotin(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryPantothenicAcid(
    HKQuantityTypeIdentifier, Nutrition
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryPhosphorus(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryIodine(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryMagnesium(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryZinc(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietarySelenium(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryCopper(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryManganese(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryChromium(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryMolybdenum(HKQuantityTypeIdentifier, Nutrition):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryChloride(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryPotassium(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryCaffeine(HKQuantityTypeIdentifier, Nutrition):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryWater(HKQuantityTypeIdentifier, Nutrition):
    unit = "mL"


class HKQuantityTypeIdentifierUVExposure(HKQuantityTypeIdentifier, UVExposure):
    unit = "count"


class HKQuantityTypeIdentifierUnderwaterDepth(HKQuantityTypeIdentifier, Diving):
    unit = "m"


class HKQuantityTypeIdentifierWaterTemperature(HKQuantityTypeIdentifier, Diving):
    unit = "degC"


class HKQuantityTypeIdentifierTimeInDaylight(HKQuantityTypeIdentifier, Mindfulness):
    unit = "min"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HKQuantityTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    {subcls.__name__: subcls for subcls in HKQuantityTypeIdentifier.__subclasses__()}
)
