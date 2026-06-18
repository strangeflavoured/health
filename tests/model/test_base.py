"""Tests for src/model/base.py — HK type hierarchy and registries."""

from __future__ import annotations

import pytest

from src.model import (
    CATEGORICAL_IDENTIFIER_MAPS,
    HKCategoryTypeIdentifierRegistry,
    HKCorrelationTypeIdentifierRegistry,
    HKMiscTypeIdentifierRegistry,
    HKQuantityTypeIdentifierRegistry,
    HKTypeIdentifierRegistry,
)
from src.model.base import (
    HK_GROUPS,
    BodyMeasurements,
    Diving,
    Fitness,
    Hearing,
    HKCategoryTypeIdentifier,
    HKGroup,
    HKIdentifier,
    HKQuantityTypeIdentifier,
    LabTestResults,
    Mindfulness,
    MissingUnit,
    Mobility,
    Nutrition,
    Other,
    ReproductiveHealth,
    Symptoms,
    UVExposure,
    VitalSigns,
)
from src.model.category_types import (
    HKCategoryTypeIdentifierAppleStandHour,
    HKCategoryTypeIdentifierHandwashingEvent,
    HKCategoryTypeIdentifierSleepAnalysis,
    HKCategoryTypeIdentifierToothbrushingEvent,
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
        d = HKCategoryTypeIdentifierSleepAnalysis.category_values()
        assert isinstance(d, dict)
        assert len(d) > 0

    def test_values_are_integers(self):
        for v in HKCategoryTypeIdentifierSleepAnalysis.category_values().values():
            assert isinstance(v, int)

    def test_values_start_at_zero(self):
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
            HK_GROUPS["NewGroup"] = object()  # type: ignore[ty:invalid-assignment]

    def test_get_members(self):
        expected = {
            BodyMeasurements,
            Fitness,
            ReproductiveHealth,
            Hearing,
            VitalSigns,
            LabTestResults,
            Mobility,
            Nutrition,
            UVExposure,
            Diving,
            Mindfulness,
            Symptoms,
            Other,
        }
        actual = HKGroup.get_members()
        assert expected == set(actual)

    def test_get_members_works_for_subclasses(self):
        expected = {
            HKCategoryTypeIdentifierHandwashingEvent,
            HKCategoryTypeIdentifierToothbrushingEvent,
        }
        actual = Other.get_members()
        assert expected == set(actual)

    def test_map_members(self):
        # The exact total grows as new types are added to the model; derive
        # it from the registries instead of pinning a magic number.
        expected_total = (
            len(HKCategoryTypeIdentifierRegistry)
            + len(HKQuantityTypeIdentifierRegistry)
            + len(HKCorrelationTypeIdentifierRegistry)
            + len(HKMiscTypeIdentifierRegistry)
        )

        out = HKGroup.map_members()
        assert isinstance(out, dict)
        assert len(out) == expected_total
        for k, v in out.items():
            assert isinstance(k, str)
            assert isinstance(v, str)

    def test_map_members_works_for_subclasses(self):
        expected = {
            "HKCategoryTypeIdentifierHandwashingEvent": "other",
            "HKCategoryTypeIdentifierToothbrushingEvent": "other",
        }
        actual = Other.map_members()
        assert expected == actual


class TestRegistryCompleteness:
    def test_quantity_registry_len(self):
        assert len(HKQuantityTypeIdentifierRegistry) > 50

    def test_category_registry_len(self):
        assert len(HKCategoryTypeIdentifierRegistry) > 20

    def test_category_registry_is_immutable(self):
        with pytest.raises(TypeError):
            HKCategoryTypeIdentifierRegistry["NewKey"] = None  # type: ignore[ty:invalid-assignment]

    def test_quantity_registry_keys_match_class_names(self):
        for k, _v in HKQuantityTypeIdentifierRegistry.items():
            assert k.startswith("HKQuantityTypeIdentifier")

    def test_categorical_identifier_maps_built_correctly(self):
        assert len(CATEGORICAL_IDENTIFIER_MAPS) > 0
        for _k, v in CATEGORICAL_IDENTIFIER_MAPS.items():
            assert isinstance(v, dict)
            assert all(isinstance(i, int) for i in v.values())

    def test_categorical_maps_is_immutable(self):
        with pytest.raises(TypeError):
            CATEGORICAL_IDENTIFIER_MAPS["X"] = {}  # type: ignore[ty:invalid-assignment]

    def test_quantity_is_subclass_of_hk_identifier(self):
        assert issubclass(HKQuantityTypeIdentifier, HKIdentifier)

    def test_category_is_subclass_of_hk_identifier(self):
        assert issubclass(HKCategoryTypeIdentifier, HKIdentifier)


class TestGroupClasses:
    def test_body_measurements_group(self):
        assert BodyMeasurements.group == "body_measurements"

    def test_fitness_group(self):
        assert Fitness.group == "fitness"

    def test_reproductive_health_group(self):
        assert ReproductiveHealth.group == "reproductive_health"

    def test_hearing_group(self):
        assert Hearing.group == "hearing"

    def test_vital_signs_group(self):
        assert VitalSigns.group == "vital_signs"

    def test_lab_test_results_group(self):
        assert LabTestResults.group == "lab_test_results"

    def test_mobility_group(self):
        assert Mobility.group == "mobility"

    def test_nutrition_group(self):
        assert Nutrition.group == "nutrition"

    def test_uv_exposure_group(self):
        assert UVExposure.group == "uv_exposure"

    def test_diving_group(self):
        assert Diving.group == "diving"

    def test_mindfulness_group(self):
        assert Mindfulness.group == "mindfulness"

    def test_symptoms_group(self):
        assert Symptoms.group == "symptoms"

    def test_other_group(self):
        assert Other.group == "other"

    def test_groups_map_to_correct_classes(self):
        assert HK_GROUPS["Fitness"] is Fitness
        assert HK_GROUPS["VitalSigns"] is VitalSigns

    def test_quantity_registry_keys_start_with_prefix(self):
        for k in HKQuantityTypeIdentifierRegistry:
            assert k.startswith("HKQuantityTypeIdentifier"), k


class TestHKTypeIdentifierRegistryUnitAttribute:
    def test_all_identifiers_have_unit(self):
        for _, cls in HKTypeIdentifierRegistry.items():
            assert hasattr(cls, "unit")
