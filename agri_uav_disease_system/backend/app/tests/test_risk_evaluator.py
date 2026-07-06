from __future__ import annotations

from app.services.algorithm.risk_evaluator import RiskLevelEvaluator


def test_risk_level_mapping():
    evaluator = RiskLevelEvaluator()
    assert evaluator.evaluate("\u65e0\u75c5") == "normal"
    assert evaluator.evaluate("\u8f7b\u5ea6") == "low"
    assert evaluator.evaluate("\u4e2d\u5ea6") == "medium"
    assert evaluator.evaluate("\u91cd\u5ea6") == "high"
