"""Tests for src/model/category_types.py — category type value enums."""

from __future__ import annotations

import pytest

from src.model.category_types import (
    HKCategoryTypeIdentifierMenstrualFlow,
    HKCategoryTypeIdentifierMoodChanges,
    HKCategoryTypeIdentifierRegistry,
    HKCategoryTypeIdentifierSleepAnalysis,
)


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
            HKCategoryTypeIdentifierMenstrualFlow.Values.HKCategoryValueMenstrualFlowNone.value
            == 4
        )

    def test_five_members(self):
        assert len(list(HKCategoryTypeIdentifierMenstrualFlow.Values)) == 5


class TestMoodChangesValues:
    def test_presence_values_present(self):
        vals = {v.value for v in HKCategoryTypeIdentifierMoodChanges.Values}
        assert 0 in vals
        assert 1 in vals


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


class TestAudioExposureEventValues:
    """AudioExposureEvent has TWO members — not one as previously assumed."""

    def test_loud_environment_is_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierAudioExposureEvent

        assert (
            HKCategoryTypeIdentifierAudioExposureEvent.Values.HKCategoryValueAudioExposureEventLoudEnvironment.value
            == 0
        )

    def test_momentary_limit_is_one(self):
        from src.model.category_types import HKCategoryTypeIdentifierAudioExposureEvent

        assert (
            HKCategoryTypeIdentifierAudioExposureEvent.Values.HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit.value
            == 1
        )

    def test_two_members(self):
        from src.model.category_types import HKCategoryTypeIdentifierAudioExposureEvent

        assert len(list(HKCategoryTypeIdentifierAudioExposureEvent.Values)) == 2


class TestSleepChangesValues:
    def test_presence_present_is_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierSleepChanges

        assert (
            HKCategoryTypeIdentifierSleepChanges.Values.HKCategoryValuePresencePresent.value
            == 0
        )

    def test_two_members(self):
        from src.model.category_types import HKCategoryTypeIdentifierSleepChanges

        assert len(list(HKCategoryTypeIdentifierSleepChanges.Values)) == 2


class TestAppetiteChangesValues:
    def test_unspecified_is_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierAppetiteChanges

        assert (
            HKCategoryTypeIdentifierAppetiteChanges.Values.HKCategoryValueAppetiteChangesUnspecified.value
            == 0
        )

    def test_four_members(self):
        from src.model.category_types import HKCategoryTypeIdentifierAppetiteChanges

        assert len(list(HKCategoryTypeIdentifierAppetiteChanges.Values)) == 4


class TestContraceptiveValues:
    def test_unspecified_is_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierContraceptive

        assert (
            HKCategoryTypeIdentifierContraceptive.Values.HKCategoryValueContraceptiveUnspecified.value
            == 0
        )

    def test_patch_is_six(self):
        from src.model.category_types import HKCategoryTypeIdentifierContraceptive

        assert (
            HKCategoryTypeIdentifierContraceptive.Values.HKCategoryValueContraceptivePatch.value
            == 6
        )

    def test_seven_members(self):
        from src.model.category_types import HKCategoryTypeIdentifierContraceptive

        assert len(list(HKCategoryTypeIdentifierContraceptive.Values)) == 7


class TestOvulationTestResultValues:
    def test_negative_is_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierOvulationTestResult

        assert (
            HKCategoryTypeIdentifierOvulationTestResult.Values.HKCategoryValueOvulationTestResultNegative.value
            == 0
        )

    def test_four_members(self):
        from src.model.category_types import HKCategoryTypeIdentifierOvulationTestResult

        assert len(list(HKCategoryTypeIdentifierOvulationTestResult.Values)) == 4


class TestCervicalMucusQualityValues:
    def test_dry_is_zero(self):
        from src.model.category_types import (
            HKCategoryTypeIdentifierCervicalMucusQuality,
        )

        assert (
            HKCategoryTypeIdentifierCervicalMucusQuality.Values.HKCategoryValueCervicalMucusQualityDry.value
            == 0
        )

    def test_five_members(self):
        from src.model.category_types import (
            HKCategoryTypeIdentifierCervicalMucusQuality,
        )

        assert len(list(HKCategoryTypeIdentifierCervicalMucusQuality.Values)) == 5


class TestPregnancyTestResultValues:
    def test_negative_is_zero(self):
        from src.model.category_types import HKCategoryTypeIdentifierPregnancyTestResult

        assert (
            HKCategoryTypeIdentifierPregnancyTestResult.Values.HKCategoryValuePregnancyTestResultNegative.value
            == 0
        )

    def test_three_members(self):
        from src.model.category_types import HKCategoryTypeIdentifierPregnancyTestResult

        assert len(list(HKCategoryTypeIdentifierPregnancyTestResult.Values)) == 3


class TestAppleWalkingSteadinessEventValues:
    def test_initial_low_is_zero(self):
        from src.model.category_types import (
            HKCategoryTypeIdentifierAppleWalkingSteadinessEvent,
        )

        assert (
            HKCategoryTypeIdentifierAppleWalkingSteadinessEvent.Values.HKCategoryValueAppleWalkingSteadinessEventInitialLow.value
            == 0
        )

    def test_four_members(self):
        from src.model.category_types import (
            HKCategoryTypeIdentifierAppleWalkingSteadinessEvent,
        )

        assert (
            len(list(HKCategoryTypeIdentifierAppleWalkingSteadinessEvent.Values)) == 4
        )
