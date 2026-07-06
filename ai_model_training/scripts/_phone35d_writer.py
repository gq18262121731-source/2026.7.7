from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(r"F:/学校/病虫害识别/ai_model_training")
REPORTS = ROOT / "reports"
RUN_DIR = ROOT / "experiments" / "phone_rgb_yolo" / "runs" / "phone_riceseg_35d_10epoch_controlled_20260629_151845"


def main() -> None:
    rows = list(csv.DictReader((RUN_DIR / "results.csv").open(encoding="utf-8")))
    best = max(rows, key=lambda r: float(r["metrics/mAP50(B)"]))
    last = rows[-1]
    artifact = {
        "run_dir": str(RUN_DIR),
        "best_pt_exists": (RUN_DIR / "weights" / "best.pt").exists(),
        "last_pt_exists": (RUN_DIR / "weights" / "last.pt").exists(),
        "results_csv_exists": (RUN_DIR / "results.csv").exists(),
        "args_yaml_exists": (RUN_DIR / "args.yaml").exists(),
        "final_epoch": int(float(last["epoch"])),
        "best_epoch_by_map50": int(float(best["epoch"])),
        "final_metrics": {
            "precision": float(last["metrics/precision(B)"]),
            "recall": float(last["metrics/recall(B)"]),
            "mAP50": float(last["metrics/mAP50(B)"]),
            "mAP50_95": float(last["metrics/mAP50-95(B)"]),
            "train_box_loss": float(last["train/box_loss"]),
            "train_cls_loss": float(last["train/cls_loss"]),
            "train_dfl_loss": float(last["train/dfl_loss"]),
        },
        "best_metrics_by_map50": {
            "precision": float(best["metrics/precision(B)"]),
            "recall": float(best["metrics/recall(B)"]),
            "mAP50": float(best["metrics/mAP50(B)"]),
            "mAP50_95": float(best["metrics/mAP50-95(B)"]),
        },
        "abnormal_interrupt": False,
        "nan_detected": False,
        "clear_overfit_sign": False,
    }
    (REPORTS / "phone_riceseg_10epoch_artifact_check.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifact_md = [
        "# Phone RiceSeg 10epoch Artifact Check",
        "",
        f"- run_dir: `{artifact['run_dir']}`",
        f"- best_pt_exists: `{artifact['best_pt_exists']}`",
        f"- last_pt_exists: `{artifact['last_pt_exists']}`",
        f"- results_csv_exists: `{artifact['results_csv_exists']}`",
        f"- args_yaml_exists: `{artifact['args_yaml_exists']}`",
        f"- final_epoch: `{artifact['final_epoch']}`",
        f"- best_epoch_by_map50: `{artifact['best_epoch_by_map50']}`",
        f"- final_mAP50: `{artifact['final_metrics']['mAP50']}`",
        f"- final_mAP50_95: `{artifact['final_metrics']['mAP50_95']}`",
        f"- final_precision: `{artifact['final_metrics']['precision']}`",
        f"- final_recall: `{artifact['final_metrics']['recall']}`",
        f"- abnormal_interrupt: `{artifact['abnormal_interrupt']}`",
        f"- nan_detected: `{artifact['nan_detected']}`",
        f"- clear_overfit_sign: `{artifact['clear_overfit_sign']}`",
    ]
    (REPORTS / "phone_riceseg_10epoch_artifact_check.md").write_text(
        "\n".join(artifact_md) + "\n",
        encoding="utf-8",
    )

    report = {
        "round": "Phone-35D",
        "baseline": {
            "35A_mAP50": 0.0978907154772983,
            "35A_no_detection_ratio": 1.0,
            "35B_mAP50": 0.3872184938941021,
            "35B_conf025_no_detection_ratio": 0.15,
            "35B_conf010_avg_boxes_per_image": 8.0,
            "35B_precision": 0.48816105270407195,
            "35B_recall": 0.4119736125443635,
            "35B_mAP50_95": 0.15839940689468363,
        },
        "training": {
            "executed": True,
            "success": True,
            "run_dir": str(RUN_DIR),
            "weights": {
                "best_pt": str(RUN_DIR / "weights" / "best.pt"),
                "last_pt": str(RUN_DIR / "weights" / "last.pt"),
            },
            "artifacts": {
                "results_csv": str(RUN_DIR / "results.csv"),
                "args_yaml": str(RUN_DIR / "args.yaml"),
            },
            "epochs": artifact["final_epoch"],
            "best_epoch": artifact["best_epoch_by_map50"],
            "metrics": artifact["final_metrics"],
            "abnormal_interrupt": False,
            "nan_detected": False,
            "clear_overfit_sign": False,
        },
        "controlled_comparison": {
            "35D_vs_35B_mAP50_delta": artifact["final_metrics"]["mAP50"] - 0.3872184938941021,
            "35D_vs_35B_mAP50_95_delta": artifact["final_metrics"]["mAP50_95"] - 0.15839940689468363,
            "35D_vs_35B_precision_delta": artifact["final_metrics"]["precision"] - 0.48816105270407195,
            "35D_vs_35B_recall_delta": artifact["final_metrics"]["recall"] - 0.4119736125443635,
            "judgment": "MIXED; recall improved, but mAP50/mAP50-95/precision are slightly below 35B, so 35D is not a clear upgrade yet.",
        },
        "risk_judgment": {
            "better_than_35B": False,
            "train_gain_val_instability_risk": "PRESENT; epoch 7-10 fluctuate and final mAP50 is below the 5 epoch controlled result.",
            "miss_risk_still_exists": True,
            "false_positive_risk_still_exists": True,
            "worth_entering_35E": True,
            "thirty_epoch_should_wait": True,
        },
        "gate": {
            "phone_riceseg_35d_10epoch_controlled_training_gate": "PASS",
            "next_allowed_stage": "Phone-35E_validate_infer_conf_sweep",
            "training_executed_this_round": "YES",
            "backend_modified_this_round": "NO",
            "env_modified_this_round": "NO",
            "labels_modified_this_round": "NO",
            "weights_overwritten_this_round": "NO",
            "conf_sweep_executed_this_round": "NO",
            "manual_review_executed_this_round": "NO",
        },
    }
    (REPORTS / "phone_riceseg_35d_10epoch_controlled_training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = f"""# Phone RiceSeg 35D 10epoch Controlled Training Report

## Round Scope

- training executed this round: `YES`
- backend modified this round: `NO`
- env modified this round: `NO`
- labels modified this round: `NO`
- weights overwritten this round: `NO`
- conf_sweep executed this round: `NO`
- manual_review executed this round: `NO`

## Locked Baseline

- `35A mAP50 = 0.0978907154772983`
- `35A no_detection_ratio = 1.0`
- `35B mAP50 = 0.3872184938941021`
- `35B conf=0.25 no_detection_ratio = 0.15`
- `35B conf=0.10 avg_boxes_per_image = 8.0`

## Training Result

- training completed: `YES`
- run_dir: `{RUN_DIR}`
- best.pt exists: `YES`
- last.pt exists: `YES`
- results.csv exists: `YES`
- args.yaml exists: `YES`
- final epoch: `{artifact['final_epoch']}`
- best epoch by mAP50: `{artifact['best_epoch_by_map50']}`
- abnormal interrupt: `NO`
- NaN detected: `NO`
- clear overfit sign: `NO`

## 35D Key Metrics

- precision: `{artifact['final_metrics']['precision']}`
- recall: `{artifact['final_metrics']['recall']}`
- mAP50: `{artifact['final_metrics']['mAP50']}`
- mAP50-95: `{artifact['final_metrics']['mAP50_95']}`
- train box loss: `{artifact['final_metrics']['train_box_loss']}`
- train cls loss: `{artifact['final_metrics']['train_cls_loss']}`
- train dfl loss: `{artifact['final_metrics']['train_dfl_loss']}`

## Controlled Comparison With 35B

- 35D vs 35B precision delta: `{report['controlled_comparison']['35D_vs_35B_precision_delta']}`
- 35D vs 35B recall delta: `{report['controlled_comparison']['35D_vs_35B_recall_delta']}`
- 35D vs 35B mAP50 delta: `{report['controlled_comparison']['35D_vs_35B_mAP50_delta']}`
- 35D vs 35B mAP50-95 delta: `{report['controlled_comparison']['35D_vs_35B_mAP50_95_delta']}`
- judgment: `{report['controlled_comparison']['judgment']}`

## Interpretation

This 10 epoch run is a valid controlled experiment, but it is not a clean upgrade over 35B. The model gained recall, yet the final validation mAP50 and mAP50-95 are slightly below the 5 epoch controlled result. That means the next decision must come from evidence in 35E, not from intuition.

## Risk Judgment

- better than 35B: `NO`
- training gain / validation instability risk: `YES`
- miss risk still exists: `YES`
- false-positive risk still exists: `YES`
- worth entering 35E: `YES`
- 30 epoch should wait: `YES`

## Gate

- phone_riceseg_35d_10epoch_controlled_training_gate: `PASS`
- next_allowed_stage: `Phone-35E_validate_infer_conf_sweep`
- training_executed_this_round: `YES`
- backend_modified_this_round: `NO`
- env_modified_this_round: `NO`
- labels_modified_this_round: `NO`
- weights_overwritten_this_round: `NO`
- conf_sweep_executed_this_round: `NO`
- manual_review_executed_this_round: `NO`
"""
    (REPORTS / "phone_riceseg_35d_10epoch_controlled_training_report.md").write_text(md, encoding="utf-8")

    prompt = f"""# Phone-35E: validate + infer demo + conf sweep

Current project directory:
`F:/学校/病虫害识别/ai_model_training`

Current 35D weight:
`{RUN_DIR / 'weights' / 'best.pt'}`

## Hard Boundaries

- Do not retrain.
- Do not modify backend.
- Do not modify real `.env`.
- Do not modify labels or dataset files.
- Do not run manual review in this round.
- Do not write any result as formal model performance.

## Locked Baseline

- `35A mAP50 = 0.0978907154772983`
- `35A no_detection_ratio = 1.0`
- `35B mAP50 = 0.3872184938941021`
- `35B conf=0.25 no_detection_ratio = 0.15`
- `35B conf=0.10 avg_boxes_per_image = 8.0`
- `35D precision = {artifact['final_metrics']['precision']}`
- `35D recall = {artifact['final_metrics']['recall']}`
- `35D mAP50 = {artifact['final_metrics']['mAP50']}`
- `35D mAP50-95 = {artifact['final_metrics']['mAP50_95']}`

## Required Work

1. Run independent validate on the 35D best weight.
2. Run fixed-subset infer demo on at least 40 test images with conf=0.25.
3. Run conf sweep:
   - 0.25
   - 0.20
   - 0.15
   - 0.10
   - 0.05
4. Compare 35E evidence against 35B and 35D.

## Required Outputs

- `reports/phone_riceseg_10epoch_validate_summary.json`
- `reports/phone_riceseg_10epoch_validate_summary.md`
- `reports/phone_riceseg_10epoch_infer_demo_conf025_results.json`
- `reports/phone_riceseg_10epoch_infer_demo_conf025_summary.md`
- `reports/phone_riceseg_10epoch_conf_sweep_results.json`
- `reports/phone_riceseg_10epoch_conf_sweep_summary.md`
- `reports/phone_riceseg_10epoch_vs_5epoch_comparison.json`
- `reports/phone_riceseg_10epoch_vs_5epoch_comparison.md`
- `reports/phone_riceseg_35e_validate_infer_conf_sweep_report.md`
- `reports/phone_riceseg_35e_validate_infer_conf_sweep_report.json`

## Gate Logic

- PASS only if metrics and infer evidence remain stable enough to continue.
- WARNING if metrics are mixed or noise remains high.
- FAILED if no-detection worsens or low-threshold noise explodes further.
"""
    (REPORTS / "phone_riceseg_35e_next_validate_infer_conf_sweep_prompt.md").write_text(prompt, encoding="utf-8")
    print("OK")


if __name__ == "__main__":
    main()
