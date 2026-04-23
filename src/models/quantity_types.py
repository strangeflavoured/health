"""Quantity Type model classes."""

from .models import HK_GROUPS, HKQuantityTypeIdentifier


class HKQuantityTypeIdentifierBodyMassIndex(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    pass


class HKQuantityTypeIdentifierBodyFatPercentage(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    pass


class HKQuantityTypeIdentifierHeight(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    pass


class HKQuantityTypeIdentifierBodyMass(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    pass


class HKQuantityTypeIdentifierLeanBodyMass(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    pass


class HKQuantityTypeIdentifierWaistCircumference(
    HKQuantityTypeIdentifier, HK_GROUPS["BodyMeasurements"]
):
    pass


class HKQuantityTypeIdentifierStepCount(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    pass


class HKQuantityTypeIdentifierDistanceWalkingRunning(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceCycling(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceWheelchair(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceSwimming(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceDownhillSnowSports(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceCrossCountrySkiing(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistancePaddleSports(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceRowing(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierDistanceSkatingSports(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierFlightsClimbed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierNikeFuel(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    pass


class HKQuantityTypeIdentifierPushCount(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    pass


class HKQuantityTypeIdentifierSwimmingStrokeCount(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierBasalEnergyBurned(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierActiveEnergyBurned(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierAppleExerciseTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierAppleMoveTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierAppleStandTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierVO2Max(HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]):
    pass


class HKQuantityTypeIdentifierRunningSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierRunningPower(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierRunningGroundContactTime(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierRunningStrideLength(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierRunningVerticalOscillation(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierCyclingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierCyclingPower(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierCyclingCadence(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierCyclingFunctionalThresholdPower(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierCrossCountrySkiingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierPaddleSportsSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierRowingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierPhysicalEffort(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierWorkoutEffortScore(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierEstimatedWorkoutEffortScore(
    HKQuantityTypeIdentifier, HK_GROUPS["Fitness"]
):
    pass


class HKQuantityTypeIdentifierBasalBodyTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["ReproductiveHealth"]
):
    pass


class HKQuantityTypeIdentifierEnvironmentalAudioExposure(
    HKQuantityTypeIdentifier, HK_GROUPS["Hearing"]
):
    pass


class HKQuantityTypeIdentifierHeadphoneAudioExposure(
    HKQuantityTypeIdentifier, HK_GROUPS["Hearing"]
):
    pass


class HKQuantityTypeIdentifierEnvironmentalSoundReduction(
    HKQuantityTypeIdentifier, HK_GROUPS["Hearing"]
):
    pass


class HKQuantityTypeIdentifierHeartRate(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierRestingHeartRate(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierWalkingHeartRateAverage(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierHeartRateVariabilitySdnn(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierHeartRateRecoveryOneMinute(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierAtrialFibrillationBurden(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierOxygenSaturation(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierBloodPressureSystolic(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierBloodPressureDiastolic(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierRespiratoryRate(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierBodyTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierAppleSleepingWristTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierAppleSleepingBreathingDisturbances(
    HKQuantityTypeIdentifier, HK_GROUPS["VitalSigns"]
):
    pass


class HKQuantityTypeIdentifierBloodGlucose(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierBloodAlcoholContent(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierPeripheralPerfusionIndex(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierForcedVitalCapacity(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierForcedExpiratoryVolume1(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierPeakExpiratoryFlowRate(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierInhalerUsage(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierNumberOfTimesFallen(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierElectrodermalActivity(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierInsulinDelivery(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierNumberOfAlcoholicBeverages(
    HKQuantityTypeIdentifier, HK_GROUPS["LabTestResults"]
):
    pass


class HKQuantityTypeIdentifierWalkingSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierWalkingStepLength(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierWalkingAsymmetryPercentage(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierWalkingDoubleSupportPercentage(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierAppleWalkingSteadiness(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierSixMinuteWalkTestDistance(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierStairAscentSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierStairDescentSpeed(
    HKQuantityTypeIdentifier, HK_GROUPS["Mobility"]
):
    pass


class HKQuantityTypeIdentifierDietaryEnergyConsumed(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryFatTotal(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryFatPolyunsaturated(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryFatMonounsaturated(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryFatSaturated(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryCholesterol(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietarySodium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryCarbohydrates(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryFiber(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietarySugar(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryProtein(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminA(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminB6(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminB12(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminC(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminD(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminE(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryVitaminK(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryCalcium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryIron(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryThiamin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryRiboflavin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryNiacin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryFolate(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryBiotin(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryPantothenicAcid(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryPhosphorus(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryIodine(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryMagnesium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryZinc(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietarySelenium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryCopper(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryManganese(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryChromium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryMolybdenum(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryChloride(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryPotassium(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryCaffeine(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierDietaryWater(
    HKQuantityTypeIdentifier, HK_GROUPS["Nutrition"]
):
    pass


class HKQuantityTypeIdentifierUVExposure(
    HKQuantityTypeIdentifier, HK_GROUPS["UVExposure"]
):
    pass


class HKQuantityTypeIdentifierUnderwaterDepth(
    HKQuantityTypeIdentifier, HK_GROUPS["Diving"]
):
    pass


class HKQuantityTypeIdentifierWaterTemperature(
    HKQuantityTypeIdentifier, HK_GROUPS["Diving"]
):
    pass


class HKQuantityTypeIdentifierTimeInDaylight(
    HKQuantityTypeIdentifier, HK_GROUPS["Mindfulness"]
):
    pass
