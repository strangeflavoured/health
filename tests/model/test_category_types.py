"""Tests for src/model/category_types.py — category type value enums."""

from __future__ import annotations

import pytest
from parameterized import parameterized

from src.model.category_types import (
    HKCategoryTypeIdentifierRegistry,
    HKCategoryTypeIdentifierSleepAnalysis,
)

REGISTRY_ITEMS = set(HKCategoryTypeIdentifierRegistry.keys())
TWO_VALUES = [
    "HKCategoryTypeIdentifierAppleStandHour",
    "HKCategoryTypeIdentifierSleepChanges",
    "HKCategoryTypeIdentifierMoodChanges",
]
THREE_VALUES = [
    "HKCategoryTypeIdentifierPregnancyTestResult",
    "HKCategoryTypeIdentifierProgesteroneTestResult",
]
FOUR_VALUES = [
    "HKCategoryTypeIdentifierAppetiteChanges",
    "HKCategoryTypeIdentifierAppleWalkingSteadinessEvent",
    "HKCategoryTypeIdentifierOvulationTestResult",
]
FIVE_VALUES = [
    "HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat",
    "HKCategoryTypeIdentifierConstipation",
    "HKCategoryTypeIdentifierChestTightnessOrPain",
    "HKCategoryTypeIdentifierCervicalMucusQuality",
    "HKCategoryTypeIdentifierNightSweats",
    "HKCategoryTypeIdentifierHeadache",
    "HKCategoryTypeIdentifierSinusCongestion",
    "HKCategoryTypeIdentifierDrySkin",
    "HKCategoryTypeIdentifierMenstrualFlow",
    "HKCategoryTypeIdentifierGeneralizedBodyAche",
    "HKCategoryTypeIdentifierSoreThroat",
    "HKCategoryTypeIdentifierPelvicPain",
    "HKCategoryTypeIdentifierBladderIncontinence",
    "HKCategoryTypeIdentifierShortnessOfBreath",
    "HKCategoryTypeIdentifierHotFlashes",
    "HKCategoryTypeIdentifierDizziness",
    "HKCategoryTypeIdentifierDiarrhea",
    "HKCategoryTypeIdentifierAbdominalCramps",
    "HKCategoryTypeIdentifierAcne",
    "HKCategoryTypeIdentifierFainting",
    "HKCategoryTypeIdentifierHairLoss",
    "HKCategoryTypeIdentifierLowerBackPain",
    "HKCategoryTypeIdentifierChills",
    "HKCategoryTypeIdentifierSkippedHeartbeat",
    "HKCategoryTypeIdentifierNausea",
    "HKCategoryTypeIdentifierHeartburn",
    "HKCategoryTypeIdentifierRunnyNose",
    "HKCategoryTypeIdentifierLossOfSmell",
    "HKCategoryTypeIdentifierMemoryLapse",
    "HKCategoryTypeIdentifierBloating",
    "HKCategoryTypeIdentifierVaginalDryness",
    "HKCategoryTypeIdentifierLossOfTaste",
    "HKCategoryTypeIdentifierWheezing",
    "HKCategoryTypeIdentifierVomiting",
    "HKCategoryTypeIdentifierFatigue",
    "HKCategoryTypeIdentifierBreastPain",
    "HKCategoryTypeIdentifierFever",
    "HKCategoryTypeIdentifierCoughing",
]
SIX_VALUES = ["HKCategoryTypeIdentifierSleepAnalysis"]
SEVEN_VALUES = ["HKCategoryTypeIdentifierContraceptive"]
ONE_VALUE = REGISTRY_ITEMS.difference(
    TWO_VALUES + THREE_VALUES + FOUR_VALUES + FIVE_VALUES + SIX_VALUES + SEVEN_VALUES
)


class TestRegistryLookup:
    def test_sleep_analysis_in_registry(self):
        assert (
            "HKCategoryTypeIdentifierSleepAnalysis" in HKCategoryTypeIdentifierRegistry
        )

    def test_registry_lookup_returns_correct_class(self):
        cls = HKCategoryTypeIdentifierRegistry["HKCategoryTypeIdentifierSleepAnalysis"]
        assert cls is HKCategoryTypeIdentifierSleepAnalysis

    def test_unknown_key_raises_key_error(self):
        with pytest.raises(KeyError):
            _ = HKCategoryTypeIdentifierRegistry["HKCategoryTypeIdentifierNONEXISTENT"]

    def test_category_values_all_integers(self):
        for name, cls in HKCategoryTypeIdentifierRegistry.items():
            for k, v in cls.category_values().items():
                assert isinstance(v, int), f"{name}.{k} value is not int"

    def test_all_registry_values_start_at_zero(self):
        for name, cls in HKCategoryTypeIdentifierRegistry.items():
            vals = list(cls.category_values().values())
            assert min(vals) == 0, f"{name} min value is not 0"

    def test_registry_is_immutable(self):
        with pytest.raises(TypeError):
            HKCategoryTypeIdentifierRegistry["NewKey"] = None  # type: ignore[index]

    def test_audio_exposure_event_in_registry(self):
        assert (
            "HKCategoryTypeIdentifierAudioExposureEvent"
            in HKCategoryTypeIdentifierRegistry
        )


class TestCategoryType:
    @parameterized.expand(ONE_VALUE)
    def test_one_member(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 1

    @parameterized.expand(TWO_VALUES)
    def test_two_members(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 2

    @parameterized.expand(THREE_VALUES)
    def test_three_members(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 3

    @parameterized.expand(FOUR_VALUES)
    def test_four_members(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 4

    @parameterized.expand(FIVE_VALUES)
    def test_five_members(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 5

    @parameterized.expand(SIX_VALUES)
    def test_six_members(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 6

    @parameterized.expand(SEVEN_VALUES)
    def test_seven_members(self, name):
        category_values = list(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert len(category_values) == 7

    @parameterized.expand(ONE_VALUE)
    def test_one_member_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(1))

    @parameterized.expand(TWO_VALUES)
    def test_two_members_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(2))

    @parameterized.expand(THREE_VALUES)
    def test_three_members_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(3))

    @parameterized.expand(FOUR_VALUES)
    def test_four_members_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(4))

    @parameterized.expand(FIVE_VALUES)
    def test_five_members_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(5))

    @parameterized.expand(SIX_VALUES)
    def test_six_members_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(6))

    @parameterized.expand(SEVEN_VALUES)
    def test_seven_members_values_range(self, name):
        category_values = set(
            HKCategoryTypeIdentifierRegistry[name].category_values().values()
        )
        assert category_values == set(range(7))


class TestSleepAnalysisValues:
    def test_in_bed_is_zero(self):
        v = HKCategoryTypeIdentifierSleepAnalysis.Values
        assert v.HKCategoryValueSleepAnalysisInBed.value == 0

    def test_rem_is_five(self):
        v = HKCategoryTypeIdentifierSleepAnalysis.Values
        assert v.HKCategoryValueSleepAnalysisAsleepREM.value == 5

    def test_six_members(self):
        assert len(list(HKCategoryTypeIdentifierSleepAnalysis.Values)) == 6


class TestMenstrualFlowValues:
    def test_none_is_four(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierMenstrualFlow"
            ].Values.HKCategoryValueMenstrualFlowNone.value
            == 4
        )

    def test_five_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierMenstrualFlow"
                    ].Values
                )
            )
            == 5
        )


class TestMoodChangesValues:
    def test_presence_values_present(self):
        vals = {
            v.value
            for v in HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierMoodChanges"
            ].Values
        }
        assert 0 in vals
        assert 1 in vals


class TestSleepChangesValues:
    def test_presence_present_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierSleepChanges"
            ].Values.HKCategoryValuePresencePresent.value
            == 0
        )

    def test_two_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierSleepChanges"
                    ].Values
                )
            )
            == 2
        )


class TestAppetiteChangesValues:
    def test_unspecified_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierAppetiteChanges"
            ].Values.HKCategoryValueAppetiteChangesUnspecified.value
            == 0
        )

    def test_four_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierAppetiteChanges"
                    ].Values
                )
            )
            == 4
        )


class TestContraceptiveValues:
    def test_unspecified_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierContraceptive"
            ].Values.HKCategoryValueContraceptiveUnspecified.value
            == 0
        )

    def test_patch_is_six(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierContraceptive"
            ].Values.HKCategoryValueContraceptivePatch.value
            == 6
        )

    def test_seven_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierContraceptive"
                    ].Values
                )
            )
            == 7
        )


class TestOvulationTestResultValues:
    def test_negative_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierOvulationTestResult"
            ].Values.HKCategoryValueOvulationTestResultNegative.value
            == 0
        )

    def test_four_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierOvulationTestResult"
                    ].Values
                )
            )
            == 4
        )


class TestCervicalMucusQualityValues:
    def test_dry_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierCervicalMucusQuality"
            ].Values.HKCategoryValueCervicalMucusQualityDry.value
            == 0
        )

    def test_five_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierCervicalMucusQuality"
                    ].Values
                )
            )
            == 5
        )


class TestPregnancyTestResultValues:
    def test_negative_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierPregnancyTestResult"
            ].Values.HKCategoryValuePregnancyTestResultNegative.value
            == 0
        )

    def test_three_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierPregnancyTestResult"
                    ].Values
                )
            )
            == 3
        )


class TestAppleWalkingSteadinessEventValues:
    def test_initial_low_is_zero(self):
        assert (
            HKCategoryTypeIdentifierRegistry[
                "HKCategoryTypeIdentifierAppleWalkingSteadinessEvent"
            ].Values.HKCategoryValueAppleWalkingSteadinessEventInitialLow.value
            == 0
        )

    def test_four_members(self):
        assert (
            len(
                list(
                    HKCategoryTypeIdentifierRegistry[
                        "HKCategoryTypeIdentifierAppleWalkingSteadinessEvent"
                    ].Values
                )
            )
            == 4
        )
