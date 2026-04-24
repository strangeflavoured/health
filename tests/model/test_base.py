"""Tests for src/model/base.py — HK type hierarchy and registries."""

from __future__ import annotations

import pytest

from src.model.base import (
    HK_GROUPS,
    HKCategoryTypeIdentifier,
    HKIdentifier,
    HKQuantityTypeIdentifier,
    MissingUnit,
)


class TestMissingUnit:
    def test_categorical_value_is_string(self):
        assert MissingUnit.CATEGORICAL.value == "Categorical"

    def test_only_one_member(self):
        assert len(list(MissingUnit)) == 1


class TestHKIdentifierHierarchy:
    def test_quantity_identifier_type(self):
        assert HKQuantityTypeIdentifier.identifier_type == "quantity"

    def test_category_identifier_type(self):
        assert HKCategoryTypeIdentifier.identifier_type == "category"


class TestHKCategoryTypeIdentifier:
    def test_category_values_returns_dict(self):
        from src.model.category_types import HKCategoryTypeIdentifierSleepAnalysis

        d = HKCategoryTypeIdentifierSleepAnalysis.category_values()
        assert isinstance(d, dict)
        assert len(d) > 0

    def test_values_are_integers(self):
        from src.model.category_types import HKCategoryTypeIdentifierSleepAnalysis

        for v in HKCategoryTypeIdentifierSleepAnalysis.category_values().values():
            assert isinstance(v, int)

    def test_values_start_at_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierAppleStandHour

        vals = HKCategoryTypeIdentifierAppleStandHour.category_values()
        assert 0 in vals.values()


class TestHKGroups:
    def test_all_expected_groups_present(self):
        expected = [
            "BodyMeasurements",
            "Fitness",
            "ReproductiveHealth",
            "Hearing",
            "VitalSigns",
            "LabTestResults",
            "Mobility",
            "Nutrition",
            "UVExposure",
            "Diving",
            "Mindfulness",
            "Symptoms",
            "Other",
        ]
        for g in expected:
            assert g in HK_GROUPS

    def test_mapping_is_immutable(self):
        with pytest.raises(TypeError):
            HK_GROUPS["NewGroup"] = object()  # type: ignore[index]


class TestRegistryCompleteness:
    def test_quantity_registry_not_empty(self):
        from src.model.quantity_types import HKQuantityTypeIdentifierRegistry

        assert len(HKQuantityTypeIdentifierRegistry) > 50

    def test_category_registry_not_empty(self):
        from src.model.category_types import HKCategoryTypeIdentifierRegistry

        assert len(HKCategoryTypeIdentifierRegistry) > 20

    def test_category_registry_is_immutable(self):
        from src.model.category_types import HKCategoryTypeIdentifierRegistry

        with pytest.raises(TypeError):
            HKCategoryTypeIdentifierRegistry["NewKey"] = None  # type: ignore[index]

    def test_quantity_registry_keys_match_class_names(self):
        from src.model.quantity_types import HKQuantityTypeIdentifierRegistry

        for k, v in HKQuantityTypeIdentifierRegistry.items():
            assert k.startswith("HKQuantityTypeIdentifier")

    def test_categorical_identifier_maps_built_correctly(self):
        from src.model import CATEGORICAL_IDENTIFIER_MAPS

        assert len(CATEGORICAL_IDENTIFIER_MAPS) > 0
        for k, v in CATEGORICAL_IDENTIFIER_MAPS.items():
            assert isinstance(v, dict)
            assert all(isinstance(i, int) for i in v.values())

    def test_categorical_maps_is_immutable(self):
        from src.model import CATEGORICAL_IDENTIFIER_MAPS

        with pytest.raises(TypeError):
            CATEGORICAL_IDENTIFIER_MAPS["X"] = {}  # type: ignore[index]
