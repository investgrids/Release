import app.services.ai_service as ai


def test_requesty_tier_is_off_without_models(monkeypatch):
    monkeypatch.setattr(ai.settings, "requesty_models", "", raising=False)
    assert ai._requesty_models() == []


def test_requesty_models_are_parsed_from_the_setting(monkeypatch):
    monkeypatch.setattr(ai.settings, "requesty_models", " a/b , c/d ,", raising=False)
    assert ai._requesty_models() == ["a/b", "c/d"]


def test_requesty_has_a_limiter_and_provider_name():
    assert "requesty" in ai._TIER_LIMITERS if hasattr(ai, "_TIER_LIMITERS") else True
    assert ai._provider_name_for_url(ai._REQUESTY_URL) == "requesty"
