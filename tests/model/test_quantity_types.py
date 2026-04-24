"""Tests for src/model/quantity_types.py — previously empty file."""

from __future__ import annotations

import pytest

from src.model.base import (
    BodyMeasurements,
    Diving,
    Fitness,
    HKIdentifier,
    HKQuantityTypeIdentifier,
    LabTestResults,
    Mindfulness,
    VitalSigns,
)
from src.model.quantity_types import (
    HKQuantityTypeIdentifierActiveEnergyBurned,
    HKQuantityTypeIdentifierBloodGlucose,
    HKQuantityTypeIdentifierBodyMass,
    HKQuantityTypeIdentifierHeartRate,
    HKQuantityTypeIdentifierOxygenSaturation,
    HKQuantityTypeIdentifierRegistry,
    HKQuantityTypeIdentifierStepCount,
    HKQuantityTypeIdentifierTimeInDaylight,
    HKQuantityTypeIdentifierUnderwaterDepth,
    HKQuantityTypeIdentifierVO2Max,
)


class TestRegistry:
    def test_registry_is_not_empty(self):
        assert len(HKQuantityTypeIdentifierRegistry) > 50

    def test_registry_is_immutable(self):
        with pytest.raises(TypeError):
            HKQuantityTypeIdentifierRegistry["NewKey"] = None  # type: ignore[index]

    def test_all_keys_start_with_correct_prefix(self):
        for k in HKQuantityTypeIdentifierRegistry:
            assert k.startswith("HKQuantityTypeIdentifier"), k

    def test_lookup_returns_correct_class(self):
        assert (
            HKQuantityTypeIdentifierRegistry["HKQuantityTypeIdentifierHeartRate"]
            is HKQuantityTypeIdentifierHeartRate
        )

    def test_unknown_key_raises_key_error(self):
        with pytest.raises(KeyError):
            _ = HKQuantityTypeIdentifierRegistry["HKQuantityTypeIdentifierNONEXISTENT"]

    def test_all_values_are_hk_quantity_subclasses(self):
        for name, cls in HKQuantityTypeIdentifierRegistry.items():
            assert issubclass(cls, HKQuantityTypeIdentifier), (
                f"{name} is not a subclass of HKQuantityTypeIdentifier"
            )

    def test_all_values_are_hk_identifier_subclasses(self):
        for name, cls in HKQuantityTypeIdentifierRegistry.items():
            assert issubclass(cls, HKIdentifier), (
                f"{name} is not a subclass of HKIdentifier"
            )


class TestIdentifierType:
    def test_heart_rate_identifier_type(self):
        assert HKQuantityTypeIdentifierHeartRate.identifier_type == "quantity"

    def test_step_count_identifier_type(self):
        assert HKQuantityTypeIdentifierStepCount.identifier_type == "quantity"

    def test_all_registry_classes_have_quantity_identifier_type(self):
        for name, cls in HKQuantityTypeIdentifierRegistry.items():
            assert cls.identifier_type == "quantity", (
                f"{name}.identifier_type != 'quantity'"
            )


class TestGroupAttribute:
    def test_heart_rate_is_vital_signs(self):
        assert issubclass(HKQuantityTypeIdentifierHeartRate, VitalSigns)

    def test_step_count_is_fitness(self):
        assert issubclass(HKQuantityTypeIdentifierStepCount, Fitness)

    def test_body_mass_is_body_measurements(self):
        assert issubclass(HKQuantityTypeIdentifierBodyMass, BodyMeasurements)

    def test_blood_glucose_is_lab_test_results(self):
        assert issubclass(HKQuantityTypeIdentifierBloodGlucose, LabTestResults)

    def test_oxygen_saturation_is_vital_signs(self):
        assert issubclass(HKQuantityTypeIdentifierOxygenSaturation, VitalSigns)

    def test_active_energy_burned_is_fitness(self):
        assert issubclass(HKQuantityTypeIdentifierActiveEnergyBurned, Fitness)

    def test_underwater_depth_is_diving(self):
        assert issubclass(HKQuantityTypeIdentifierUnderwaterDepth, Diving)

    def test_time_in_daylight_is_mindfulness(self):
        assert issubclass(HKQuantityTypeIdentifierTimeInDaylight, Mindfulness)

    def test_vo2_max_is_fitness(self):
        assert issubclass(HKQuantityTypeIdentifierVO2Max, Fitness)


class TestNoValuesEnum:
    def test_heart_rate_has_no_values_attribute(self):
        assert not hasattr(HKQuantityTypeIdentifierHeartRate, "Values")

    def test_no_quantity_type_has_values_attribute(self):
        for name, cls in HKQuantityTypeIdentifierRegistry.items():
            assert not hasattr(cls, "Values"), (
                f"{name} unexpectedly has a Values attribute"
            )
