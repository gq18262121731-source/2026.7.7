from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
EXP_DIR = ROOT / "experiments/p11_2a_riceseg_smoke"
SAMPLES_DIR = EXP_DIR / "prediction_samples"
MODEL_PATH = EXP_DIR / "model_experimental_smoke.pt"
INFERENCE_PATH = EXP_DIR / "inference_smoke.json"
REPORT_PATH = PROJECT_ROOT / "reports/p11_2a_riceseg_segmentation_smoke_report.md"
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


def overlay_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    base = image.convert("RGBA")
    mask_l = mask.convert("L")
    red = Image.new("RGBA", base.size, (255, 0, 0, 0))
    alpha = mask_l.point(lambda value: 110 if value > 0 else 0)
    red.putalpha(alpha)
    return Image.alpha_composite(base, red).convert("RGB")


def placeholder_pred(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, (30, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, size[0] - 8, size[1] - 8), outline=(220, 220, 220), width=2)
    draw.text((18, 96), "PRED BLOCKED", fill=(255, 255, 255))
    draw.text((18, 122), "NO SMOKE WEIGHT", fill=(255, 255, 255))
    return image


def select_samples(rows: list[dict[str, str]], max_count: int = 8) -> list[dict[str, str]]:
    selected = []
    seen = set()
    for row in rows:
        if row["class_original"] not in seen:
            selected.append(row)
            seen.add(row["class_original"])
        if len(selected) >= max_count:
            return selected
    for row in rows:
        if row not in selected:
            selected.append(row)
        if len(selected) >= max_count:
            break
    return selected


def write_index(samples: list[dict[str, str]], status: str) -> None:
    rows = []
    for sample in samples:
        sid = sample["sample_id"]
        rows.append(
            f"<tr><td>{sid}</td><td>{sample['class_original']}</td>"
            f"<td><img src='{sid}_original.jpg'></td>"
            f"<td><img src='{sid}_gt_mask.png'></td>"
            f"<td><img src='{sid}_pred_mask_blocked.png'></td>"
            f"<td><img src='{sid}_overlay_gt.jpg'></td></tr>"
        )
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>P11-2A RiceSeg Smoke Samples</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; }}
    td, th {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; }}
    img {{ width: 160px; height: 160px; object-fit: contain; }}
  </style>
</head>
<body>
  <h1>P11-2A RiceSeg Smoke Samples</h1>
  <p>experimental=true; smoke_only=true; not_for_production=true; probability_claim=false</p>
  <p>Status: {status}. Placeholder pred masks are shown when model training is dependency-blocked.</p>
  <table>
    <tr><th>sample</th><th>class</th><th>original</th><th>gt mask</th><th>pred mask</th><th>gt overlay</th></tr>
    {''.join(rows)}
  </table>
</body>
</html>
"""
    atomic_write_text(SAMPLES_DIR / "index.html", html)
    atomic_write_text(
        SAMPLES_DIR / "README.md",
        "# P11-2A Prediction Samples\n\n"
        "- experimental=true\n"
        "- smoke_only=true\n"
        "- not_for_production=true\n"
        "- probability_claim=false\n"
        f"- inference_status={status}\n"
        "- Placeholder prediction masks mean no trained smoke weight was available in this environment.\n",
    )


def update_report(inference: dict[str, Any]) -> None:
    validation = load_json(EXP_DIR / "validation_smoke.json", {})
    metrics = load_json(EXP_DIR / "metrics_smoke.json", {})
    manifest = load_json(EXP_DIR / "split_manifest.json", {})
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
        f"- Weights path: `{metrics.get('weights_path', rel(MODEL_PATH))}`",
        f"- Missing dependencies: `{metrics.get('missing_dependencies', [])}`",
        f"- Smoke metrics: `{metrics.get('smoke_metrics', {})}`",
        "",
        "## Inference Samples",
        "",
        f"- Inference status: `{inference.get('status')}`",
        f"- Visual samples generated: `{inference.get('visual_samples_generated')}`",
        f"- Prediction masks generated by model: `{inference.get('prediction_masks_generated')}`",
        f"- Sample count: `{inference.get('sample_count')}`",
        f"- Prediction samples dir: `{inference.get('prediction_samples_dir')}`",
        "",
        "## Boundary",
        "",
        "This P11-2A artifact only verifies that the external image/mask dataset can be read, split, smoke-loaded, and prepared for experimental segmentation training. It is not a production model, does not enter the backend main route, does not output disease probability, and does not generate prescriptions or dosage advice.",
    ]
    atomic_write_text(REPORT_PATH, "\n".join(lines) + "\n")


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv(EXP_DIR / "test.csv")
    samples = select_samples(rows, 8)
    for sample in samples:
        sid = sample["sample_id"]
        image = Image.open(sample["image_path"]).convert("RGB").resize((256, 256), RESAMPLE_BILINEAR)
        mask = Image.open(sample["mask_path"]).convert("L").resize((256, 256), RESAMPLE_NEAREST)
        image.save(SAMPLES_DIR / f"{sid}_original.jpg", quality=90)
        mask.save(SAMPLES_DIR / f"{sid}_gt_mask.png")
        overlay_mask(image, mask).save(SAMPLES_DIR / f"{sid}_overlay_gt.jpg", quality=90)
        placeholder_pred((256, 256)).save(SAMPLES_DIR / f"{sid}_pred_mask_blocked.png")

    status = "BLOCKED_BY_DEPENDENCY_OR_MISSING_MODEL" if not MODEL_PATH.exists() else "MODEL_WEIGHT_PRESENT_NOT_INFERRED_BY_THIS_SCRIPT"
    write_index(samples, status)
    inference = {
        "generated_at": now(),
        "status": status,
        "visual_samples_generated": True,
        "prediction_masks_generated": False,
        "sample_count": len(samples),
        "prediction_samples_dir": rel(SAMPLES_DIR),
        "model_path": rel(MODEL_PATH),
        "model_exists": MODEL_PATH.exists(),
        "safety": SAFETY,
    }
    atomic_write_json(INFERENCE_PATH, inference)
    update_report(inference)
    print(json.dumps(inference, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
