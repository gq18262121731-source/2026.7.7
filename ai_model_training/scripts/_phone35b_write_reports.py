from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"F:/学校/病虫害识别/ai_model_training")
REPORTS = ROOT / "reports"


def load_json(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def main() -> None:
    validate = load_json("phone_riceseg_short_exp_5epoch_validate_summary.json")
    sweep = load_json("phone_riceseg_short_exp_5epoch_conf_sweep_results.json")
    compare = load_json("phone_riceseg_short_exp_5epoch_vs_sanity_comparison.json")

    card = {
        "model_name": "phone_riceseg_preview500_short_exp_5epoch",
        "model_type": "YOLOv8n short experimental",
        "dataset": "rice_phone_rgb_riceseg_preview_500_revised_v0_1",
        "epochs": 5,
        "purpose": "short_experimental_learning_signal_check",
        "not_formal": True,
        "not_for_backend_deployment": True,
        "not_for_pesticide_recommendation": True,
        "not_a_production_model": True,
        "generated_weights": {
            "best_pt": "ai_model_training/experiments/phone_rgb_yolo/runs/short_exp_phone_riceseg_preview500_revised_v0_1_5epoch/weights/best.pt",
            "last_pt": "ai_model_training/experiments/phone_rgb_yolo/runs/short_exp_phone_riceseg_preview500_revised_v0_1_5epoch/weights/last.pt",
        },
        "validate_summary": validate["experimental_metrics"],
        "infer_demo_summary": sweep["0.25"],
        "conf_sweep_summary": sweep,
        "comparison_with_1epoch_sanity": compare,
        "known_limitations": [
            "experimental only",
            "not backend ready",
            "conf=0.25 still has 3/20 no-detection",
            "lower-threshold sweep becomes noisy",
        ],
    }
    (REPORTS / "phone_riceseg_short_exp_5epoch_model_card.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Phone RiceSeg Short Exp 5epoch Model Card",
        "",
        "- model_name: `phone_riceseg_preview500_short_exp_5epoch`",
        "- model_type: `YOLOv8n short experimental`",
        "- dataset: `rice_phone_rgb_riceseg_preview_500_revised_v0_1`",
        "- epochs: `5`",
        "- purpose: `short_experimental_learning_signal_check`",
        "- not_formal: `true`",
        "- not_for_backend_deployment: `true`",
        "- not_for_pesticide_recommendation: `true`",
        "- best_pt: `ai_model_training/experiments/phone_rgb_yolo/runs/short_exp_phone_riceseg_preview500_revised_v0_1_5epoch/weights/best.pt`",
        "- last_pt: `ai_model_training/experiments/phone_rgb_yolo/runs/short_exp_phone_riceseg_preview500_revised_v0_1_5epoch/weights/last.pt`",
        f"- validate_mAP50: `{validate['experimental_metrics']['mAP50']}`",
        f"- conf025_no_detection_ratio: `{sweep['0.25']['no_detection_ratio']}`",
        f"- sanity_to_shortexp_delta_mAP50: `{compare['delta']['mAP50']}`",
        "- known_limitations: `experimental_only / lower_threshold_noise / not_backend_ready`",
    ]
    (REPORTS / "phone_riceseg_short_exp_5epoch_model_card.md").write_text(
        "\n".join(md) + "\n",
        encoding="utf-8",
    )

    report = f"""# Thirty-Fifth Round B Report: Phone RiceSeg preview_500 revised_v0_1 Short Experimental 5epoch Training

## Goal

This round runs a controlled `5 epoch` short experimental training on `rice_phone_rgb_riceseg_preview_500_revised_v0_1` after the 1 epoch sanity run verified the training pipeline.

## Why This Round Was Allowed

Phone-35A already proved the training / validate / infer chain could run end to end. The next question was whether a small controlled increase from `1 epoch` to `5 epoch` could recover useful detection signal from the prior `12/12 no detection` sanity outcome.

## Data Gate Status

- machine_check: `PASS`
- manual_gate: `PASS`
- images: `500`
- labels: `500`
- bbox: `1707`
- reviewed_count: `120 / 120`
- obvious_error_ratio: `0.016666666666666666`
- systemic_flags: `[]`

## Environment Status

- env: `torchgpu`
- status: `READY_GPU`
- python: `3.11.15`
- torch: `2.6.0+cu124`
- ultralytics: `8.4.52`
- opencv-python: `4.13.0`
- CUDA: `available`
- GPU: `NVIDIA GeForce RTX 4060 Laptop GPU`

## Actual Training Command

`C:/Users/13010/anaconda3/envs/torchgpu/python.exe scripts/train_yolo.py --config configs/phone_riceseg_preview500_revised_readiness.yaml --epochs 5 --imgsz 640 --batch 8 --device 0 --name short_exp_phone_riceseg_preview500_revised_v0_1_5epoch --execute`

## Actual Run Directory

- run_dir: `experiments/phone_rgb_yolo/runs/short_exp_phone_riceseg_preview500_revised_v0_1_5epoch`

## Training Result

- training completed: `YES`
- actual epochs: `5`
- exceeded 5 epoch: `NO`
- training duration: about `0.039397 hours`
- best.pt generated: `YES`
- last.pt generated: `YES`
- NaN detected: `NO`
- class id error detected: `NO`
- label out-of-range detected: `NO`

## Validate Result

- validate completed: `YES`
- precision: `{validate['experimental_metrics']['precision']}`
- recall: `{validate['experimental_metrics']['recall']}`
- mAP50: `{validate['experimental_metrics']['mAP50']}`
- mAP50-95: `{validate['experimental_metrics']['mAP50_95']}`
- per-class AP:
  - `bacterial_blight`: `{validate['experimental_metrics']['per_class_ap']['bacterial_blight']}`
  - `blast`: `{validate['experimental_metrics']['per_class_ap']['blast']}`
  - `brown_spot`: `{validate['experimental_metrics']['per_class_ap']['brown_spot']}`
  - `tungro`: `{validate['experimental_metrics']['per_class_ap']['tungro']}`

These remain experimental metrics, not formal model metrics.

## Comparison With 1 Epoch Sanity

- sanity mAP50: `{compare['sanity']['mAP50']}`
- short_exp mAP50: `{compare['short_exp_5epoch']['mAP50']}`
- delta mAP50: `{compare['delta']['mAP50']}`
- sanity mAP50-95: `{compare['sanity']['mAP50_95']}`
- short_exp mAP50-95: `{compare['short_exp_5epoch']['mAP50_95']}`
- delta mAP50-95: `{compare['delta']['mAP50_95']}`
- sanity infer no_detection_ratio: `1.0`
- short_exp infer conf=0.25 no_detection_ratio: `{compare['short_exp_5epoch']['conf025_no_detection_ratio']}`

## Infer Demo Result

- infer demo completed: `YES`
- sampled images: `{sweep['0.25']['total_images']}`
- images_with_detection at conf=0.25: `{sweep['0.25']['images_with_detection']}`
- no_detection_count at conf=0.25: `{sweep['0.25']['no_detection_count']}`
- no_detection_ratio at conf=0.25: `{sweep['0.25']['no_detection_ratio']}`
- total_boxes at conf=0.25: `{sweep['0.25']['total_boxes']}`
- avg_boxes_per_image at conf=0.25: `{sweep['0.25']['avg_boxes_per_image']}`

## Conf Threshold Sweep

- conf=0.25: no_detection_ratio=`{sweep['0.25']['no_detection_ratio']}`, avg_boxes_per_image=`{sweep['0.25']['avg_boxes_per_image']}`, risk=`{sweep['0.25']['qualitative_risk']}`
- conf=0.10: no_detection_ratio=`{sweep['0.10']['no_detection_ratio']}`, avg_boxes_per_image=`{sweep['0.10']['avg_boxes_per_image']}`, risk=`{sweep['0.10']['qualitative_risk']}`
- conf=0.05: no_detection_ratio=`{sweep['0.05']['no_detection_ratio']}`, avg_boxes_per_image=`{sweep['0.05']['avg_boxes_per_image']}`, risk=`{sweep['0.05']['qualitative_risk']}`
- conf=0.01: no_detection_ratio=`{sweep['0.01']['no_detection_ratio']}`, avg_boxes_per_image=`{sweep['0.01']['avg_boxes_per_image']}`, risk=`{sweep['0.01']['qualitative_risk']}`

## Interpretation

The short experimental run clearly improved over the 1 epoch sanity baseline. The model is no longer trapped in universal no-detection behavior, and conf=`0.25` already yields many detections on the held-out demo subset. However, the threshold sweep shows that lowering confidence quickly explodes into noisy multi-box behavior, so this remains an experimental learning-signal checkpoint rather than a deployment-ready phone model.

## Boundary

- generated new weights: `YES`, but short experimental weights only
- backend integration: `NO`
- modified real `.env`: `NO`
- modified backend: `NO`
- modified raw image/mask: `NO`
- modified labels: `NO`
- overwrote historical weights: `NO`
- git add/commit: `NO`

## Current Gate

- short_exp gate: `PASS`

## Next Recommendation

This round supports entering `10 epoch planning`, not direct long training and not backend integration. The next decision should focus on whether the team prefers a controlled 10 epoch follow-up or a configuration / threshold analysis pass first.
"""
    (REPORTS / "thirty_fifth_round_b_phone_riceseg_short_exp_5epoch_training_report.md").write_text(
        report,
        encoding="utf-8",
    )

    print("OK")


if __name__ == "__main__":
    main()
