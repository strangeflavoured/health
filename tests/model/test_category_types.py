"""Tests for src/model/category_types.py — category type value enums."""

from __future__ import annotations

import pytest

from src.model.category_types import (
    HKCategoryTypeIdentifierRegistry,
    HKCategoryTypeIdentifierSleepAnalysis,
    HKCategoryTypeIdentifierMenstrualFlow,
    HKCategoryTypeIdentifierMoodChanges,
    HKCategoryTypeIdentifierAppleStandHour,
    HKCategoryTypeIdentifierContraceptive,
    HKCategoryTypeIdentifierPregnancyTestResult,
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
