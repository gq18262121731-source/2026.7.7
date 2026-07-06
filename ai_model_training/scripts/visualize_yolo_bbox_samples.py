"""Create visual audit samples for a YOLO dataset."""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required: pip install pyyaml") from exc


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize YOLO bbox samples.")
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--data-yaml", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def load_names(data_yaml: Path) -> dict[int, str]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = data.get("names", {})
    if isinstance(names, list):
        return {i: name for i, name in enumerate(names)}
    return {int(k): str(v) for k, v in names.items()}


def read_label(path: Path) -> list[tuple[int, float, float, float, float]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        class_id, x, y, w, h = line.split()
        rows.append((int(class_id), float(x), float(y), float(w), float(h)))
    return rows


def draw_boxes(image_path: Path, label_path: Path, output_path: Path, names: dict[int, str]) -> int:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    labels = read_label(label_path)
    for class_id, x, y, w, h in labels:
        x1 = (x - w / 2) * width
        y1 = (y - h / 2) * height
        x2 = (x + w / 2) * width
        y2 = (y + h / 2) * height
        draw.rectangle([x1, y1, x2, y2], outline=(255, 40, 40), width=3)
        draw.text((x1 + 3, max(0, y1 - 14)), names.get(class_id, str(class_id)), fill=(255, 255, 0), font=ImageFont.load_default())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=92)
    return len(labels)


def main() -> int:
    args = parse_args()
    root = Path(args.dataset_root)
    output_dir = Path(args.output_dir)
    names = load_names(Path(args.data_yaml))
    rng = random.Random(args.seed)

    by_class: dict[int, list[tuple[Path, Path, str]]] = defaultdict(list)
    for split in ("train", "val", "test"):
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        for image_path in sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES):
            label_path = label_dir / f"{image_path.stem}.txt"
            labels = read_label(label_path)
            for class_id, *_ in labels:
                by_class[class_id].append((image_path, label_path, split))
                break

    rows = []
    for class_id, items in sorted(by_class.items()):
        rng.shuffle(items)
        for index, (image_path, label_path, split) in enumerate(items[: args.per_class], start=1):
            out_name = f"{names.get(class_id, class_id)}_{index:03d}_{image_path.name}"
            out_path = output_dir / out_name
            bbox_count = draw_boxes(image_path, label_path, out_path, names)
            rows.append({"class_id": class_id, "class_name": names.get(class_id, str(class_id)), "split": split, "bbox_count": bbox_count, "preview": out_name})

    with (output_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["class_id", "class_name", "split", "bbox_count", "preview"])
        writer.writeheader()
        writer.writerows(rows)

    lines = ["# RiceSeg Preview 200 Visual Audit", ""]
    for row in rows:
        lines.append(f"- {row['class_name']} / {row['split']} / bbox={row['bbox_count']}: ![]({row['preview']})")
    (output_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} visual samples to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
