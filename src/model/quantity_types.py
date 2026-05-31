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

from .base import HK_GROUPS, HKQuantityTypeIdentifier


class HKQuantityTypeIdentifierBodyMassIndex(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    unit = "count"


class HKQuantityTypeIdentifierBodyFatPercentage(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    unit = "%"


class HKQuantityTypeIdentifierHeight(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    unit = "cm"


class HKQuantityTypeIdentifierBodyMass(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    unit = "kg"


class HKQuantityTypeIdentifierLeanBodyMass(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    unit = "kg"


class HKQuantityTypeIdentifierWaistCircumference(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    unit = "cm"


class HKQuantityTypeIdentifierStepCount(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    unit = "count"


class HKQuantityTypeIdentifierDistanceWalkingRunning(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceCycling(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceWheelchair(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceSwimming(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "m"


class HKQuantityTypeIdentifierDistanceDownhillSnowSports(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceCrossCountrySkiing(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistancePaddleSports(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceRowing(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierDistanceSkatingSports(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km"


class HKQuantityTypeIdentifierFlightsClimbed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "count"


class HKQuantityTypeIdentifierPushCount(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    unit = "count"


class HKQuantityTypeIdentifierSwimmingStrokeCount(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "count"


class HKQuantityTypeIdentifierBasalEnergyBurned(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "kcal"


class HKQuantityTypeIdentifierActiveEnergyBurned(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "kcal"


class HKQuantityTypeIdentifierAppleExerciseTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "min"


class HKQuantityTypeIdentifierAppleMoveTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "min"


class HKQuantityTypeIdentifierAppleStandTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "min"


class HKQuantityTypeIdentifierVO2Max(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    unit = "mL/min·kg"


class HKQuantityTypeIdentifierRunningSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km/hr"


class HKQuantityTypeIdentifierRunningPower(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "W"


class HKQuantityTypeIdentifierRunningGroundContactTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "ms"


class HKQuantityTypeIdentifierRunningStrideLength(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "m"


class HKQuantityTypeIdentifierRunningVerticalOscillation(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "cm"


class HKQuantityTypeIdentifierCyclingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km/hr"


class HKQuantityTypeIdentifierCyclingPower(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "W"


class HKQuantityTypeIdentifierCyclingCadence(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "rpm"


class HKQuantityTypeIdentifierCyclingFunctionalThresholdPower(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "W"


class HKQuantityTypeIdentifierCrossCountrySkiingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km/hr"


class HKQuantityTypeIdentifierPaddleSportsSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km/hr"


class HKQuantityTypeIdentifierRowingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "km/hr"


class HKQuantityTypeIdentifierPhysicalEffort(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "kcal/hr·kg"


class HKQuantityTypeIdentifierWorkoutEffortScore(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "appleEffortScore"


class HKQuantityTypeIdentifierEstimatedWorkoutEffortScore(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    unit = "appleEffortScore"


class HKQuantityTypeIdentifierBasalBodyTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    unit = "degC"


class HKQuantityTypeIdentifierEnvironmentalAudioExposure(
    HKQuantityTypeIdentifier, HK_GROUPS["Hearing"]
):
    unit = "dBASPL"


class HKQuantityTypeIdentifierHeadphoneAudioExposure(
    HKQuantityTypeIdentifier, HK_GROUPS["Hearing"]
):
    unit = "dBASPL"


class HKQuantityTypeIdentifierEnvironmentalSoundReduction(
    HKQuantityTypeIdentifier, HK_GROUPS["Hearing"]
):
    unit = "dBASPL"


class HKQuantityTypeIdentifierHeartRate(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "count/min"


class HKQuantityTypeIdentifierRestingHeartRate(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "count/min"


class HKQuantityTypeIdentifierWalkingHeartRateAverage(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "count/min"


class HKQuantityTypeIdentifierHeartRateRecoveryOneMinute(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "count/min"


class HKQuantityTypeIdentifierHeartRateVariabilitySDNN(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "ms"


class HKQuantityTypeIdentifierAtrialFibrillationBurden(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "%"


class HKQuantityTypeIdentifierOxygenSaturation(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "%"


class HKQuantityTypeIdentifierBloodPressureSystolic(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "mmHg"


class HKQuantityTypeIdentifierBloodPressureDiastolic(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "mmHg"


class HKQuantityTypeIdentifierRespiratoryRate(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "count/min"


class HKQuantityTypeIdentifierBodyTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "degC"


class HKQuantityTypeIdentifierAppleSleepingWristTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "degC"


class HKQuantityTypeIdentifierAppleSleepingBreathingDisturbances(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    unit = "count"


# Apple Health exports glucose units as the literal string
# "mmol<180.15588...>/L" — the bracketed number is the molar mass
# of glucose, used by HealthKit to convert to/from mg/dL.  We expose the
# clean SI unit here; downstream code that needs the conversion factor
# should reference :data:`MMOL_PER_L_TO_MG_PER_DL_GLUCOSE` below.
MMOL_PER_L_TO_MG_PER_DL_GLUCOSE: float = 18.01558800000541  # 1 mmol/L = 18.02 mg/dL


class HKQuantityTypeIdentifierBloodGlucose(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "mmol/L"


class HKQuantityTypeIdentifierBloodAlcoholContent(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "%"


class HKQuantityTypeIdentifierPeripheralPerfusionIndex(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "%"


class HKQuantityTypeIdentifierForcedVitalCapacity(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "L"


class HKQuantityTypeIdentifierForcedExpiratoryVolume1(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "L"


class HKQuantityTypeIdentifierPeakExpiratoryFlowRate(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "L/min"


class HKQuantityTypeIdentifierInhalerUsage(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "count"


class HKQuantityTypeIdentifierNumberOfTimesFallen(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "count"


class HKQuantityTypeIdentifierElectrodermalActivity(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "mcS"


class HKQuantityTypeIdentifierInsulinDelivery(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "IU"


class HKQuantityTypeIdentifierNumberOfAlcoholicBeverages(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    unit = "count"


class HKQuantityTypeIdentifierWalkingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "km/hr"


class HKQuantityTypeIdentifierWalkingStepLength(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "cm"


class HKQuantityTypeIdentifierWalkingAsymmetryPercentage(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "%"


class HKQuantityTypeIdentifierWalkingDoubleSupportPercentage(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "%"


class HKQuantityTypeIdentifierAppleWalkingSteadiness(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "%"


class HKQuantityTypeIdentifierSixMinuteWalkTestDistance(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "m"


class HKQuantityTypeIdentifierStairAscentSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "m/s"


class HKQuantityTypeIdentifierStairDescentSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    unit = "m/s"


class HKQuantityTypeIdentifierDietaryEnergyConsumed(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "kcal"


class HKQuantityTypeIdentifierDietaryFatTotal(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFatPolyunsaturated(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFatMonounsaturated(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFatSaturated(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryCholesterol(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietarySodium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryCarbohydrates(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryFiber(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietarySugar(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryProtein(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "g"


class HKQuantityTypeIdentifierDietaryVitaminA(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryVitaminB6(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryVitaminB12(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryVitaminC(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryVitaminD(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryVitaminE(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryVitaminK(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryCalcium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryIron(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryThiamin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryRiboflavin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryNiacin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryFolate(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryBiotin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryPantothenicAcid(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryPhosphorus(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryIodine(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryMagnesium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryZinc(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietarySelenium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryCopper(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryManganese(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryChromium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryMolybdenum(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mcg"


class HKQuantityTypeIdentifierDietaryChloride(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryPotassium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryCaffeine(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mg"


class HKQuantityTypeIdentifierDietaryWater(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    unit = "mL"


class HKQuantityTypeIdentifierUVExposure(
    HKQuantityTypeIdentifier, HK_GROUPS["UVExposure"]
):
    unit = "count"


class HKQuantityTypeIdentifierUnderwaterDepth(
    HKQuantityTypeIdentifier, HK_GROUPS["Diving"]
):
    unit = "m"


class HKQuantityTypeIdentifierWaterTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["Diving"]
):
    unit = "degC"


class HKQuantityTypeIdentifierTimeInDaylight(
    HKQuantityTypeIdentifier, HK_GROUPS["Mindfulness"]
):
    unit = "min"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HKQuantityTypeIdentifierRegistry: MappingProxyType[str, Any] = MappingProxyType(
    {subcls.__name__: subcls for subcls in HKQuantityTypeIdentifier.__subclasses__()}
)
