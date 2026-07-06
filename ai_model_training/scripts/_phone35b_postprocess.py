from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(r"F:/学校/病虫害识别/ai_model_training")
REPORTS = ROOT / "reports"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def infer_summary(result_obj: dict) -> dict:
    results = result_obj["results"] if isinstance(result_obj, dict) and "results" in result_obj else result_obj
    total_images = len(results)
    det_counts = [len(item.get("detections", [])) for item in results]
    confs = []
    cls_counter: Counter[str] = Counter()
    for item in results:
        for det in item.get("detections", []):
            confs.append(float(det["confidence"]))
            cls_counter[str(det["class_name"])] += 1
    images_with_detection = sum(1 for n in det_counts if n > 0)
    no_detection_count = total_images - images_with_detection
    total_boxes = sum(det_counts)
    return {
        "total_images": total_images,
        "images_with_detection": images_with_detection,
        "no_detection_count": no_detection_count,
        "no_detection_ratio": round(no_detection_count / total_images, 4) if total_images else None,
        "total_boxes": total_boxes,
        "avg_boxes_per_image": round(total_boxes / total_images, 4) if total_images else None,
        "predicted_class_distribution": dict(cls_counter),
        "avg_confidence": round(statistics.mean(confs), 6) if confs else None,
        "max_confidence": round(max(confs), 6) if confs else None,
    }


def qualitative_risk(avg_boxes_per_image: float | None) -> str:
    if avg_boxes_per_image is None:
        return "unknown"
    if avg_boxes_per_image > 6:
        return "high_noise"
    if avg_boxes_per_image > 2:
        return "moderate"
    return "controlled"


def main() -> None:
    conf_files = {
        "0.25": REPORTS / "phone_riceseg_short_exp_5epoch_infer_demo_conf025_results.json",
        "0.10": REPORTS / "phone_riceseg_short_exp_5epoch_conf_sweep_conf010_results.json",
        "0.05": REPORTS / "phone_riceseg_short_exp_5epoch_conf_sweep_conf005_results.json",
        "0.01": REPORTS / "phone_riceseg_short_exp_5epoch_conf_sweep_conf001_results.json",
    }

    sweep_summary: dict[str, dict] = {}
    for conf, path in conf_files.items():
        summary = infer_summary(load_json(path))
        summary["conf"] = float(conf)
        summary["qualitative_risk"] = qualitative_risk(summary["avg_boxes_per_image"])
        sweep_summary[conf] = summary

    (REPORTS / "phone_riceseg_short_exp_5epoch_conf_sweep_results.json").write_text(
        json.dumps(sweep_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = ["# Phone RiceSeg Short Exp 5epoch Conf Sweep Summary", ""]
    for conf in ("0.25", "0.10", "0.05", "0.01"):
        summary = sweep_summary[conf]
        lines.append(f"## conf={conf}")
        for key in (
            "total_images",
            "images_with_detection",
            "no_detection_count",
            "no_detection_ratio",
            "total_boxes",
            "avg_boxes_per_image",
            "avg_confidence",
            "max_confidence",
            "qualitative_risk",
        ):
            lines.append(f"- {key}: `{summary[key]}`")
        lines.append(f"- predicted_class_distribution: `{summary['predicted_class_distribution']}`")
        lines.append("")
    (REPORTS / "phone_riceseg_short_exp_5epoch_conf_sweep_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    conf025 = sweep_summary["0.25"]
    infer_demo_summary = {
        key: conf025[key]
        for key in (
            "total_images",
            "images_with_detection",
            "no_detection_count",
            "no_detection_ratio",
            "total_boxes",
            "avg_boxes_per_image",
            "predicted_class_distribution",
            "avg_confidence",
            "max_confidence",
        )
    }
    infer_lines = ["# Phone RiceSeg Short Exp 5epoch Infer Demo Summary", ""]
    for key, value in infer_demo_summary.items():
        infer_lines.append(f"- {key}: `{value}`")
    (REPORTS / "phone_riceseg_short_exp_5epoch_infer_demo_conf025_summary.md").write_text(
        "\n".join(infer_lines) + "\n",
        encoding="utf-8",
    )

    sanity = load_json(REPORTS / "phone_riceseg_preview500_sanity_1epoch_validate_summary.json")
    short_exp = load_json(REPORTS / "phone_riceseg_short_exp_5epoch_validate_summary.json")
    comparison = {
        "sanity": {
            "mAP50": sanity["smoke_test_metrics"]["mAP50"],
            "mAP50_95": sanity["smoke_test_metrics"]["mAP50_95"],
            "precision": sanity["smoke_test_metrics"]["precision"],
            "recall": sanity["smoke_test_metrics"]["recall"],
            "infer_no_detection_count": 12,
            "infer_total_images": 12,
            "infer_no_detection_ratio": 1.0,
        },
        "short_exp_5epoch": {
            "mAP50": short_exp["experimental_metrics"]["mAP50"],
            "mAP50_95": short_exp["experimental_metrics"]["mAP50_95"],
            "precision": short_exp["experimental_metrics"]["precision"],
            "recall": short_exp["experimental_metrics"]["recall"],
            "conf025_no_detection_count": conf025["no_detection_count"],
            "conf025_total_images": conf025["total_images"],
            "conf025_no_detection_ratio": conf025["no_detection_ratio"],
        },
    }
    comparison["delta"] = {
        "mAP50": comparison["short_exp_5epoch"]["mAP50"] - comparison["sanity"]["mAP50"],
        "mAP50_95": comparison["short_exp_5epoch"]["mAP50_95"] - comparison["sanity"]["mAP50_95"],
        "precision": comparison["short_exp_5epoch"]["precision"] - comparison["sanity"]["precision"],
        "recall": comparison["short_exp_5epoch"]["recall"] - comparison["sanity"]["recall"],
        "no_detection_ratio_change": comparison["short_exp_5epoch"]["conf025_no_detection_ratio"]
        - comparison["sanity"]["infer_no_detection_ratio"],
    }

    (REPORTS / "phone_riceseg_short_exp_5epoch_vs_sanity_comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    cmp_lines = [
        "# Phone RiceSeg Short Exp 5epoch vs Sanity Comparison",
        "",
        f"- sanity mAP50: `{comparison['sanity']['mAP50']}`",
        f"- short_exp_5epoch mAP50: `{comparison['short_exp_5epoch']['mAP50']}`",
        f"- delta mAP50: `{comparison['delta']['mAP50']}`",
        "- sanity no_detection_ratio: `1.0`",
        f"- short_exp conf025 no_detection_ratio: `{comparison['short_exp_5epoch']['conf025_no_detection_ratio']}`",
        f"- no_detection_ratio_change: `{comparison['delta']['no_detection_ratio_change']}`",
    ]
    (REPORTS / "phone_riceseg_short_exp_5epoch_vs_sanity_comparison.md").write_text(
        "\n".join(cmp_lines) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"comparison": comparison, "sweep": sweep_summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
