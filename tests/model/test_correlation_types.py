"""Tests for src/model/correlation_types.py — HKCorrelation* sentinel classes."""

from __future__ import annotations

from types import MappingProxyType

from src.model import HKCorrelationTypeIdentifierRegistry
from src.model.base import (
    HKCorrelationTypeIdentifier,
    MissingUnit,
)
from src.model.correlation_types import (
    HKCorrelationTypeIdentifierBloodPressure,
    HKCorrelationTypeIdentifierFood,
)


class TestCorrelationRegistry:
    def test_registry_contains_blood_pressure(self):
        assert (
            "HKCorrelationTypeIdentifierBloodPressure"
            in HKCorrelationTypeIdentifierRegistry
        )

    def test_registry_contains_food(self):
        assert "HKCorrelationTypeIdentifierFood" in HKCorrelationTypeIdentifierRegistry

    def test_registry_size_is_at_least_two(self):
        assert len(HKCorrelationTypeIdentifierRegistry) >= 2

    def test_registry_values_are_subclasses(self):
        for cls in HKCorrelationTypeIdentifierRegistry.values():
            assert issubclass(cls, HKCorrelationTypeIdentifier)

    def test_registry_keys_match_class_names(self):
        for name, cls in HKCorrelationTypeIdentifierRegistry.items():
            assert name == cls.__name__


class TestCorrelationIdentifierAttributes:
    def test_identifier_type_is_correlation(self):
        for cls in HKCorrelationTypeIdentifierRegistry.values():
            assert cls.identifier_type == "correlation"

    def test_unit_is_categorical_sentinel(self):
        for cls in HKCorrelationTypeIdentifierRegistry.values():
            assert cls.unit == MissingUnit.CATEGORICAL.value

    def test_blood_pressure_is_in_vital_signs_group(self):
        assert HKCorrelationTypeIdentifierBloodPressure.group == "vital_signs"

    def test_food_is_in_nutrition_group(self):
        assert HKCorrelationTypeIdentifierFood.group == "nutrition"


class TestRegistryImmutability:
    def test_registry_is_mapping_proxy(self):
        assert isinstance(HKCorrelationTypeIdentifierRegistry, MappingProxyType)
