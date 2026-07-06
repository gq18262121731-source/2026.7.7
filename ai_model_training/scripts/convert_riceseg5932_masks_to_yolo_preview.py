"""RiceSeg-5932 mask-to-bbox preview conversion.

This script is intentionally conservative:
- it does not download data;
- it does not train models;
- it only creates a preview dataset when both RiceSeg masks and Sethy images
  are already present locally and can be paired reliably.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Pillow is required: pip install pillow") from exc


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
DEFAULT_CLASSES = ["bacterial_blight", "blast", "brown_spot", "tungro"]
CLASS_ALIASES = {
    "bacterial blight": "bacterial_blight",
    "bacterial_blight": "bacterial_blight",
    "bacterial-blight": "bacterial_blight",
    "bacterialblight": "bacterial_blight",
    "blast": "blast",
    "leaf blast": "blast",
    "leaf_blast": "blast",
    "brown spot": "brown_spot",
    "brown_spot": "brown_spot",
    "brown-spot": "brown_spot",
    "brownspot": "brown_spot",
    "tungro": "tungro",
}


@dataclass
class Pair:
    image: Path
    mask: Path
    class_name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a RiceSeg-5932 mask-to-bbox YOLO preview dataset.")
    parser.add_argument("--mask-root", default="raw_datasets/rice_seg_5932")
    parser.add_argument("--image-root", default="raw_datasets/rice_leaf_disease_sethy")
    parser.add_argument("--output-dataset", default="datasets/rice_phone_rgb_riceseg_preview_200")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--preview-size", type=int, default=200)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-area-pixels", type=int, default=20)
    parser.add_argument("--visual-per-class", type=int, default=20)
    parser.add_argument("--execute", action="store_true", help="Actually write preview dataset. Default audits only.")
    return parser.parse_args()


def normalize_key(path: Path) -> str:
    return "".join(ch for ch in path.stem.lower() if ch.isalnum())


def list_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def infer_class(path: Path) -> str | None:
    parts = [p.lower().replace("_", " ").replace("-", " ") for p in path.parts]
    for part in reversed(parts):
        compact = " ".join(part.split())
        if compact in CLASS_ALIASES:
            return CLASS_ALIASES[compact]
    stem = path.stem.lower().replace("_", " ").replace("-", " ")
    for alias, canonical in CLASS_ALIASES.items():
        if alias in stem:
            return canonical
    return None


def raw_audit(root: Path, expected_kind: str) -> dict[str, Any]:
    files = list(root.rglob("*")) if root.exists() else []
    image_files = [p for p in files if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    suffixes = Counter(p.suffix.lower() or "<none>" for p in files if p.is_file())
    class_counts = Counter(infer_class(p) or "unknown" for p in image_files)
    bad_images: list[str] = []
    for image in image_files[:200]:
        try:
            with Image.open(image) as img:
                img.verify()
        except Exception:
            bad_images.append(str(image))
    return {
        "root": str(root),
        "expected_kind": expected_kind,
        "exists": root.exists(),
        "file_count": sum(1 for p in files if p.is_file()),
        "image_like_count": len(image_files),
        "suffixes": dict(suffixes),
        "class_counts_from_paths": dict(class_counts),
        "bad_images_sample": bad_images,
    }


def pair_images_masks(image_root: Path, mask_root: Path) -> dict[str, Any]:
    images = list_images(image_root)
    masks = list_images(mask_root)
    image_map = {normalize_key(p): p for p in images}
    mask_map = {normalize_key(p): p for p in masks}
    pairs: list[Pair] = []
    for key in sorted(set(image_map) & set(mask_map)):
        image = image_map[key]
        mask = mask_map[key]
        class_name = infer_class(image) or infer_class(mask) or "unknown"
        pairs.append(Pair(image=image, mask=mask, class_name=class_name))
    orphan_images = [str(image_map[k]) for k in sorted(set(image_map) - set(mask_map))]
    orphan_masks = [str(mask_map[k]) for k in sorted(set(mask_map) - set(image_map))]
    return {
        "image_count": len(images),
        "mask_count": len(masks),
        "paired_count": len(pairs),
        "orphan_image_count": len(orphan_images),
        "orphan_mask_count": len(orphan_masks),
        "orphan_images_sample": orphan_images[:50],
        "orphan_masks_sample": orphan_masks[:50],
        "pairs": pairs,
    }


def foreground_bbox(mask: Image.Image) -> tuple[int, int, int, int] | None:
    if mask.mode in {"RGB", "RGBA"}:
        gray = mask.convert("L")
    else:
        gray = mask.convert("L")
    return gray.point(lambda p: 255 if p > 0 else 0).getbbox()


def connected_boxes(mask: Image.Image, min_area: int) -> list[tuple[int, int, int, int, int]]:
    gray = mask.convert("L")
    width, height = gray.size
    pixels = gray.load()
    visited: set[tuple[int, int]] = set()
    boxes: list[tuple[int, int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if (x, y) in visited or pixels[x, y] == 0:
                continue
            queue = deque([(x, y)])
            visited.add((x, y))
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while queue:
                cx, cy = queue.popleft()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or (nx, ny) in visited:
                        continue
                    if pixels[nx, ny] > 0:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            if area >= min_area:
                boxes.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return boxes


def yolo_line(class_id: int, box: tuple[int, int, int, int, int], image_size: tuple[int, int]) -> str:
    x1, y1, x2, y2, _ = box
    width, height = image_size
    xc = ((x1 + x2) / 2) / width
    yc = ((y1 + y2) / 2) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"


def split_name(index: int, total: int, val_ratio: float, test_ratio: float) -> str:
    test_start = int(total * (1 - test_ratio))
    val_start = int(total * (1 - test_ratio - val_ratio))
    if index >= test_start:
        return "test"
    if index >= val_start:
        return "val"
    return "train"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(path: Path, title: str, data: dict[str, Any], blocked_reason: str | None = None) -> None:
    lines = [f"# {title}", ""]
    if blocked_reason:
        lines += [f"Blocked: `{blocked_reason}`", ""]
    for key, value in data.items():
        if key == "pairs":
            continue
        lines.append(f"- `{key}`: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_preview(args: argparse.Namespace, pairs: list[Pair]) -> dict[str, Any]:
    rng = random.Random(args.seed)
    by_class: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        if pair.class_name in DEFAULT_CLASSES:
            by_class[pair.class_name].append(pair)
    selected: list[Pair] = []
    per_class = max(1, args.preview_size // len(DEFAULT_CLASSES))
    for class_name in DEFAULT_CLASSES:
        items = by_class.get(class_name, [])
        rng.shuffle(items)
        selected.extend(items[:per_class])
    if len(selected) < args.preview_size:
        rest = [p for p in pairs if p not in selected and p.class_name in DEFAULT_CLASSES]
        rng.shuffle(rest)
        selected.extend(rest[: args.preview_size - len(selected)])
    selected = selected[: args.preview_size]

    output_root = Path(args.output_dataset)
    class_to_id = {name: idx for idx, name in enumerate(DEFAULT_CLASSES)}
    manifest_rows: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    bbox_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()

    if args.execute:
        for split in ("train", "val", "test"):
            (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
            (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "metadata").mkdir(parents=True, exist_ok=True)

    for idx, pair in enumerate(selected):
        split = split_name(idx, len(selected), args.val_ratio, args.test_ratio)
        class_id = class_to_id[pair.class_name]
        try:
            image = Image.open(pair.image).convert("RGB")
            mask = Image.open(pair.mask)
        except Exception:
            skipped["open_failed"] += 1
            continue
        if image.size != mask.size:
            skipped["image_mask_size_mismatch"] += 1
            continue
        boxes = connected_boxes(mask, args.min_area_pixels)
        if not boxes:
            skipped["empty_or_tiny_mask"] += 1
            continue
        stem = f"{pair.class_name}_{idx:04d}_{pair.image.stem}"
        label_lines = [yolo_line(class_id, box, image.size) for box in boxes]
        if args.execute:
            image_out = output_root / "images" / split / f"{stem}.jpg"
            label_out = output_root / "labels" / split / f"{stem}.txt"
            shutil.copy2(pair.image, image_out)
            label_out.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        else:
            image_out = output_root / "images" / split / f"{stem}.jpg"
            label_out = output_root / "labels" / split / f"{stem}.txt"
        class_counts[pair.class_name] += 1
        bbox_counts[pair.class_name] += len(boxes)
        manifest_rows.append(
            {
                "split": split,
                "class_name": pair.class_name,
                "class_id": class_id,
                "image_name": image_out.name,
                "label_name": label_out.name,
                "relative_image_path": str(Path("images") / split / image_out.name),
                "relative_label_path": str(Path("labels") / split / label_out.name),
                "source_image": str(pair.image),
                "source_mask": str(pair.mask),
                "output_stem": stem,
                "bbox_count": len(boxes),
                "min_area_pixels": args.min_area_pixels,
            }
        )

    if args.execute:
        data_yaml = {
            "path": str(output_root),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(DEFAULT_CLASSES),
            "names": {idx: name for idx, name in enumerate(DEFAULT_CLASSES)},
        }
        import yaml

        (output_root / "data.yaml").write_text(yaml.safe_dump(data_yaml, sort_keys=False, allow_unicode=True), encoding="utf-8")
        (output_root / "metadata" / "class_map.yaml").write_text(
            yaml.safe_dump({"classes": [{"id": i, "name": n} for i, n in enumerate(DEFAULT_CLASSES)]}, sort_keys=False),
            encoding="utf-8",
        )
        with (output_root / "metadata" / "conversion_manifest.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()) if manifest_rows else ["split"])
            writer.writeheader()
            writer.writerows(manifest_rows)

    report = {
        "preview_dataset": str(output_root),
        "execute": args.execute,
        "requested_preview_size": args.preview_size,
        "written_images": len(manifest_rows) if args.execute else 0,
        "preview_candidates": len(manifest_rows),
        "bbox_count": sum(bbox_counts.values()),
        "class_image_distribution": dict(class_counts),
        "class_bbox_distribution": dict(bbox_counts),
        "skipped": dict(skipped),
        "min_area_pixels": args.min_area_pixels,
        "status": "preview_written" if args.execute else "dry_run_preview_only",
    }
    if args.execute:
        write_json(output_root / "metadata" / "conversion_report.json", report)
    return report


def main() -> int:
    args = parse_args()
    mask_root = Path(args.mask_root)
    image_root = Path(args.image_root)
    reports_dir = Path(args.reports_dir)

    rice_audit = raw_audit(mask_root, "riceseg5932_masks")
    sethy_audit = raw_audit(image_root, "sethy_images")
    write_json(reports_dir / "riceseg5932_raw_structure_audit.json", rice_audit)
    write_json(reports_dir / "sethy_raw_structure_audit.json", sethy_audit)
    write_md(reports_dir / "riceseg5932_raw_structure_audit.md", "RiceSeg-5932 Raw Structure Audit", rice_audit)
    write_md(reports_dir / "sethy_raw_structure_audit.md", "Sethy Raw Structure Audit", sethy_audit)

    if not mask_root.exists() or not image_root.exists():
        blocked = {
            "status": "blocked",
            "reason": "required_raw_dataset_directory_missing",
            "mask_root_exists": mask_root.exists(),
            "image_root_exists": image_root.exists(),
            "next_step": "download RiceSeg-5932 masks and Sethy images into the configured raw_datasets directories",
        }
        write_json(reports_dir / "riceseg5932_image_mask_pairing_audit.json", blocked)
        write_md(reports_dir / "riceseg5932_image_mask_pairing_audit.md", "RiceSeg-5932 Image-Mask Pairing Audit", blocked, blocked["reason"])
        print(json.dumps(blocked, ensure_ascii=False, indent=2))
        return 2

    pairing = pair_images_masks(image_root, mask_root)
    pairing_report = {k: v for k, v in pairing.items() if k != "pairs"}
    write_json(reports_dir / "riceseg5932_image_mask_pairing_audit.json", pairing_report)
    write_md(reports_dir / "riceseg5932_image_mask_pairing_audit.md", "RiceSeg-5932 Image-Mask Pairing Audit", pairing_report)
    if pairing["paired_count"] == 0:
        print(json.dumps(pairing_report, ensure_ascii=False, indent=2))
        return 2

    preview_report = build_preview(args, pairing["pairs"])
    write_json(reports_dir / "riceseg5932_mask_quality_audit.json", {"status": "sampled_via_preview", **preview_report})
    write_md(reports_dir / "riceseg5932_mask_quality_audit.md", "RiceSeg-5932 Mask Quality Audit", preview_report)
    write_json(reports_dir / "riceseg_preview_200_dataset_check.json", preview_report)
    write_md(reports_dir / "riceseg_preview_200_dataset_check.md", "RiceSeg Preview Dataset Check", preview_report)
    print(json.dumps(preview_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
