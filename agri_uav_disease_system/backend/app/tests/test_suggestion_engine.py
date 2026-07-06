from __future__ import annotations

from app.services.algorithm.suggestion_engine import AgricultureSuggestionEngine


def test_suggestion_requires_expert_for_disease():
    suggestion = AgricultureSuggestionEngine().generate("\u7a3b\u761f\u75c5", "\u4e2d\u5ea6")
    assert suggestion.need_expert_confirm is True
    assert "\u519c\u6280\u4eba\u5458\u786e\u8ba4" in suggestion.content


def test_suggestion_no_expert_for_no_disease():
    suggestion = AgricultureSuggestionEngine().generate(None, "\u65e0\u75c5")
    assert suggestion.need_expert_confirm is False
