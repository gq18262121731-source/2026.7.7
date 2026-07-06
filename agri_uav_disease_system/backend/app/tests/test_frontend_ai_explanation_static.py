from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def test_smoke_demo_contains_ai_explanation_entry_and_safety_copy():
    html_path = settings.static_dir / "frontend" / "smoke-demo.html"
    content = html_path.read_text(encoding="utf-8")

    assert "生成 AI 诊断解释" in content
    assert "/api/agent/diagnosis-report" in content
    assert "AI 智能解读" in content
    assert "本 AI 解读基于图像识别结果、知识图谱和本地 RAG 知识库生成，仅用于辅助判断，不替代农业专家现场诊断。" in content
    assert "当前系统处于 mock / smoke / experimental 阶段，结果不应作为正式生产诊断依据。" in content
    assert "具体药剂、浓度和施用时间应以当地农业技术部门建议和产品标签为准。" in content
    assert "正式农学诊断" not in content


def test_smoke_demo_contains_uav_blb_segmentation_dry_run_panel():
    html_path = settings.static_dir / "frontend" / "smoke-demo.html"
    content = html_path.read_text(encoding="utf-8")

    assert "UAV BLB 多光谱分割实验结果" in content
    assert "Experimental" in content
    assert "Dry-run only" in content
    assert "Formal candidate" in content
    assert "Not production" in content
    assert "/api/experimental/uav-blb-segmentation/dry-run" in content
    assert "/api/detect/image" in content
    assert "仅支持 5-band / multispectral TIF" in content
    assert "INVALID_MULTISPECTRAL_TIF" in content
    assert "该结果仅用于实验性 dry-run 展示，不作为正式病害识别结论，不进入统计或告警。" in content
    assert "experimental_dry_run_only_not_for_production" in content
    assert "dryRunForm" in content
    assert "uploadDryRun" in content
