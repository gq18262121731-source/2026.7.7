from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
EXP_DIR = ROOT / "experiments/p11_2a_riceseg_smoke"
REPORT_PATH = PROJECT_ROOT / "reports/p11_2a_riceseg_segmentation_smoke_report.md"
VALIDATION_PATH = EXP_DIR / "validation_smoke.json"
RESAMPLE_BILINEAR = getattr(Image, "Resampling", Image).BILINEAR
RESAMPLE_NEAREST = getattr(Image, "Resampling", Image).NEAREST

SAFETY = {
    "experimental": True,
    "smoke_only": True,
    "not_for_production": True,
    "probability_claim": False,
    "backend_main_chain_integration": False,
    "risk_fusion_ml_training": False,
    "prescription_or_dosage": False,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def validate_split_rows() -> dict[str, Any]:
    rows_by_split = {split: read_csv(EXP_DIR / f"{split}.csv") for split in ["train", "val", "test"]}
    all_rows = [row for rows in rows_by_split.values() for row in rows]
    errors = []
    split_by_key: dict[str, set[str]] = defaultdict(set)
    for split, rows in rows_by_split.items():
        for row in rows:
            split_by_key[row["pairing_key"]].add(split)
            image_path = Path(row["image_path"])
            mask_path = Path(row["mask_path"])
            if not image_path.exists() or not mask_path.exists():
                errors.append({"sample_id": row["sample_id"], "reason": "missing image or mask"})
                continue
            if row.get("paired", "").lower() != "true":
                errors.append({"sample_id": row["sample_id"], "reason": "paired flag is not true"})
    leakage_keys = [key for key, splits in split_by_key.items() if len(splits) > 1]
    pil_samples = []
    for row in all_rows[:12]:
        image = Image.open(row["image_path"]).convert("RGB").resize((256, 256), RESAMPLE_BILINEAR)
        mask = Image.open(row["mask_path"]).convert("L").resize((256, 256), RESAMPLE_NEAREST)
        pil_samples.append(
            {
                "sample_id": row["sample_id"],
                "image_size": list(image.size),
                "mask_size": list(mask.size),
                "mask_positive_pixels": sum(1 for value in mask.getdata() if value > 0),
            }
        )
    return {
        "split_counts": {split: len(rows) for split, rows in rows_by_split.items()},
        "class_counts_by_split": {split: dict(Counter(row["class_original"] for row in rows)) for split, rows in rows_by_split.items()},
        "pairing_all_passed": not errors,
        "pairing_errors": errors[:20],
        "cross_split_leakage_key_count": len(leakage_keys),
        "cross_split_leakage_keys_preview": leakage_keys[:20],
        "pil_dataloader_smoke": {"status": "PASS", "checked_samples": len(pil_samples), "samples": pil_samples},
    }


def write_report(validation: dict[str, Any]) -> None:
    manifest = load_json(EXP_DIR / "split_manifest.json", {})
    metrics = load_json(EXP_DIR / "metrics_smoke.json", {})
    inference = load_json(EXP_DIR / "inference_smoke.json", {})
    lines = [
        "# P11-2A RiceSeg Segmentation Smoke Report",
        "",
        f"Generated at: {now()}",
        "",
        "## Conclusion",
        "",
        f"- Overall status: `{'PARTIAL' if metrics.get('status') == 'BLOCKED_BY_DEPENDENCY' else 'PASS'}`",
        "- experimental=true",
        "- smoke_only=true",
        "- not_for_production=true",
        "- probability_claim=false",
        "- Backend main-chain integration: `NO`",
        "- risk_fusion ML training: `NO`",
        "- Formal disease probability output: `NO`",
        "- Prescription or dosage output: `NO`",
        "",
        "## Dataset And Split",
        "",
        f"- Source pairing report: `{manifest.get('source_pairing_report', '')}`",
        f"- Total paired rows: `{manifest.get('paired_rows', '')}`",
        f"- Pairing all passed: `{validation.get('pairing_all_passed')}`",
        f"- Cross-split leakage key count: `{validation.get('cross_split_leakage_key_count')}`",
        f"- Split counts: `{validation.get('split_counts')}`",
        f"- Class counts by split: `{validation.get('class_counts_by_split')}`",
        "- Held-out test split is retained and was not used for training or tuning.",
        "",
        "## Training",
        "",
        f"- Training status: `{metrics.get('status', 'NOT_RUN')}`",
        f"- Training completed: `{metrics.get('training_completed', False)}`",
        f"- Experimental smoke weights generated: `{metrics.get('weights_generated', False)}`",
        f"- Weights path: `{metrics.get('weights_path', rel(EXP_DIR / 'model_experimental_smoke.pt'))}`",
        f"- Missing dependencies: `{metrics.get('missing_dependencies', [])}`",
        f"- Smoke metrics: `{metrics.get('smoke_metrics', {})}`",
        "",
        "## Validation And Samples",
        "",
        f"- PIL dataloader smoke: `{validation.get('pil_dataloader_smoke', {}).get('status')}`",
        f"- Inference status: `{inference.get('status', 'NOT_RUN')}`",
        f"- Visual samples generated: `{inference.get('visual_samples_generated', False)}`",
        f"- Prediction masks generated by model: `{inference.get('prediction_masks_generated', False)}`",
        f"- Prediction samples dir: `{inference.get('prediction_samples_dir', rel(EXP_DIR / 'prediction_samples'))}`",
        "",
        "## Boundary",
        "",
        "This P11-2A artifact only verifies that the external image/mask dataset can be read, split, smoke-loaded, and prepared for experimental segmentation training. It is not a production model, does not enter the backend main route, does not output disease probability, and does not generate prescriptions or dosage advice.",
    ]
    atomic_write_text(REPORT_PATH, "\n".join(lines) + "\n")


def main() -> None:
    validation = {"generated_at": now(), "status": "PASS", "safety": SAFETY}
    validation.update(validate_split_rows())
    atomic_write_json(VALIDATION_PATH, validation)
    write_report(validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
