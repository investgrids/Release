"""
Article V2 Phase P5 — ARTICLE_PIPELINE_MODE fail-closed parsing tests.
Pure, no DB. Covers the owner's own explicit requirement: default is
always v1, and unknown/malformed/missing configuration also falls back
to v1, never silently activating V2.
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.article_v2.mode import (
    ArticlePipelineMode, get_article_pipeline_mode, v2_may_persist_publicly, v2_should_execute,
)


@pytest.fixture(autouse=True)
def _restore_setting():
    original = settings.article_pipeline_mode
    yield
    settings.article_pipeline_mode = original


@pytest.mark.parametrize("raw,expected", [
    ("v1", ArticlePipelineMode.V1),
    ("shadow_v2", ArticlePipelineMode.SHADOW_V2),
    ("canary_v2", ArticlePipelineMode.CANARY_V2),
    ("v2", ArticlePipelineMode.V2),
    ("SHADOW_V2", ArticlePipelineMode.SHADOW_V2),  # case-insensitive
    ("  v2  ", ArticlePipelineMode.V2),  # whitespace-tolerant
])
def test_recognized_values_parse_correctly(raw, expected):
    settings.article_pipeline_mode = raw
    assert get_article_pipeline_mode() == expected


@pytest.mark.parametrize("raw", [
    "", None, "v3", "V1 ", "shadow", "canary", "true", "1", "production", "V2_CANARY", "yaml: v2",
])
def test_unknown_malformed_or_missing_always_falls_back_to_v1(raw):
    settings.article_pipeline_mode = raw
    assert get_article_pipeline_mode() == ArticlePipelineMode.V1


def test_default_is_v1_without_any_override():
    settings.article_pipeline_mode = "v1"
    assert get_article_pipeline_mode() == ArticlePipelineMode.V1


class TestV2ShouldExecute:
    def test_v1_never_executes(self):
        assert v2_should_execute(ArticlePipelineMode.V1) is False

    @pytest.mark.parametrize("mode", [ArticlePipelineMode.SHADOW_V2, ArticlePipelineMode.CANARY_V2, ArticlePipelineMode.V2])
    def test_every_other_mode_executes(self, mode):
        assert v2_should_execute(mode) is True


class TestV2MayPersistPublicly:
    @pytest.mark.parametrize("mode", list(ArticlePipelineMode))
    def test_locked_false_for_every_mode_until_p7(self, mode):
        # P7 (evidence-quality-gated canary eligibility) is not built yet --
        # this must stay False for every mode, including canary_v2/v2,
        # until that phase is separately authorized and this function is
        # deliberately changed.
        assert v2_may_persist_publicly(mode) is False
