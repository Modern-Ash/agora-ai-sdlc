from agora_ai_sdlc.i18n import normalize_language, resolve_language, t


def test_language_normalization_and_fallback():
    assert normalize_language("es_AR.UTF-8") == "es"
    assert normalize_language("en-US") == "en"
    assert normalize_language("xx") == "en"


def test_explicit_language_wins_over_environment(monkeypatch):
    monkeypatch.setenv("LANG", "es_AR.UTF-8")
    assert resolve_language("en") == "en"
    assert resolve_language() == "es"


def test_spanish_changes_presentation_only():
    assert t("start.title", lang="es") == "Agora Flow | Inicio"
    assert t("start.status", lang="es") == "Estado"
    # Contract values are deliberately not translated by the i18n layer.
    assert "human-review-required" not in {t("start.status", lang="es")}
