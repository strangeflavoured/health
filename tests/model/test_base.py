"""Tests for src/model/base.py — HK type hierarchy and registries."""

from __future__ import annotations

import pytest

from src.model.base import (
    HK_GROUPS,
    HKCategoryTypeIdentifier,
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

        for k, _v in HKQuantityTypeIdentifierRegistry.items():
            assert k.startswith("HKQuantityTypeIdentifier")

    def test_categorical_identifier_maps_built_correctly(self):
        from src.model import CATEGORICAL_IDENTIFIER_MAPS

        assert len(CATEGORICAL_IDENTIFIER_MAPS) > 0
        for _k, v in CATEGORICAL_IDENTIFIER_MAPS.items():
            assert isinstance(v, dict)
            assert all(isinstance(i, int) for i in v.values())

    def test_categorical_maps_is_immutable(self):
        from src.model import CATEGORICAL_IDENTIFIER_MAPS

        with pytest.raises(TypeError):
            CATEGORICAL_IDENTIFIER_MAPS["X"] = {}  # type: ignore[index]

    def test_quantity_is_subclass_of_hk_identifier(self):
        from src.model.base import HKIdentifier

        assert issubclass(HKQuantityTypeIdentifier, HKIdentifier)

    def test_category_is_subclass_of_hk_identifier(self):
        from src.model.base import HKIdentifier

        assert issubclass(HKCategoryTypeIdentifier, HKIdentifier)

    def test_category_values_on_bare_base_raises(self):
        """HKCategoryTypeIdentifier.Values is not an Enum; iterating it must raise."""
        with pytest.raises(TypeError):
            HKCategoryTypeIdentifier.category_values()


class TestGroupClasses:
    def test_body_measurements_group(self):
        from src.model.base import BodyMeasurements

        assert BodyMeasurements.group == "body_measurements"

    def test_fitness_group(self):
        from src.model.base import Fitness

        assert Fitness.group == "body_measurements"

    def test_reproductive_health_group(self):
        from src.model.base import ReproductiveHealth

        assert ReproductiveHealth.group == "reproductive_health"

    def test_hearing_group(self):
        from src.model.base import Hearing

        assert Hearing.group == "hearing"

    def test_vital_signs_group(self):
        from src.model.base import VitalSigns

        assert VitalSigns.group == "vital_signs"

    def test_lab_test_results_group(self):
        from src.model.base import LabTestResults

        assert LabTestResults.group == "lab_test_results"

    def test_mobility_group(self):
        from src.model.base import Mobility

        assert Mobility.group == "mobility"

    def test_nutrition_group(self):
        from src.model.base import Nutrition

        assert Nutrition.group == "nutrition"

    def test_uv_exposure_group(self):
        from src.model.base import UVExposure

        assert UVExposure.group == "uv_exposure"

    def test_diving_group(self):
        from src.model.base import Diving

        assert Diving.group == "diving"

    def test_mindfulness_group(self):
        from src.model.base import Mindfulness

        assert Mindfulness.group == "mindfulness"

    def test_symptoms_group(self):
        from src.model.base import Symptoms

        assert Symptoms.group == "symptoms"

    def test_other_group(self):
        from src.model.base import Other

        assert Other.group == "other"

    def test_groups_map_to_correct_classes(self):
        from src.model.base import Fitness, VitalSigns

        assert HK_GROUPS["Fitness"] is Fitness
        assert HK_GROUPS["VitalSigns"] is VitalSigns

    def test_quantity_registry_keys_start_with_prefix(self):
        from src.model.quantity_types import HKQuantityTypeIdentifierRegistry

        for k in HKQuantityTypeIdentifierRegistry:
            assert k.startswith("HKQuantityTypeIdentifier"), k
