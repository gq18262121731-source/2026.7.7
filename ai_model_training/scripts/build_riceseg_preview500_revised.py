from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont

DEFAULT_CLASSES = ["bacterial_blight", "blast", "brown_spot", "tungro"]
CLASS_DISPLAY = {
    "bacterial_blight": "bacterial_blight",
    "blast": "blast",
    "brown_spot": "brown_spot",
    "tungro": "tungro",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RiceSeg preview_500 revised_v0_1 dataset and audit artifacts.")
    parser.add_argument("--mask-root", default="raw_datasets/rice_seg_5932/extracted/mask-vesrion1")
    parser.add_argument("--image-root", default="raw_datasets/rice_leaf_disease_sethy/extracted/Rice Leaf Disease Images")
    parser.add_argument("--rules-config", default="configs/riceseg_mask_to_bbox_revised_v0_1.yaml")
    parser.add_argument("--output-dataset", default="datasets/rice_phone_rgb_riceseg_preview_500_revised_v0_1")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--preview-size", type=int, default=500)
    parser.add_argument("--train-count", type=int, default=350)
    parser.add_argument("--val-count", type=int, default=100)
    parser.add_argument("--test-count", type=int, default=50)
    parser.add_argument("--visual-per-class", type=int, default=30)
    parser.add_argument("--manual-review-per-class", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def normalize_key(path: Path) -> str:
    return "".join(ch for ch in path.stem.lower() if ch.isalnum())


def infer_class(path: Path) -> str:
    text = "/".join(part.lower() for part in path.parts)
    if "bacterialblight" in text or "bacterial blight" in text:
        return "bacterial_blight"
    if "brownspot" in text or "brown spot" in text:
        return "brown_spot"
    if "tungro" in text:
        return "tungro"
    if "blast" in text:
        return "blast"
    raise ValueError(f"Cannot infer class from path: {path}")


def list_images(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def pair_images_masks(image_root: Path, mask_root: Path) -> list[tuple[Path, Path, str]]:
    images = {normalize_key(p): p for p in list_images(image_root)}
    masks = {normalize_key(p): p for p in list_images(mask_root)}
    pairs = []
    for key in sorted(set(images) & set(masks)):
        image = images[key]
        mask = masks[key]
        class_name = infer_class(image)
        pairs.append((image, mask, class_name))
    return pairs


def binary_morphology(mask: Image.Image, open_kernel: int, close_kernel: int) -> Image.Image:
    out = mask.convert("L").point(lambda p: 255 if p > 0 else 0)
    if open_kernel and open_kernel > 1:
        out = out.filter(ImageFilter.MinFilter(open_kernel)).filter(ImageFilter.MaxFilter(open_kernel))
    if close_kernel and close_kernel > 1:
        out = out.filter(ImageFilter.MaxFilter(close_kernel)).filter(ImageFilter.MinFilter(close_kernel))
    return out


from PIL import ImageFilter


def connected_components(mask: Image.Image) -> list[dict[str, int]]:
    gray = mask.convert("L")
    width, height = gray.size
    pixels = gray.load()
    visited = set()
    components = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0 or (x, y) in visited:
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
            components.append({
                "x1": min_x,
                "y1": min_y,
                "x2": max_x + 1,
                "y2": max_y + 1,
                "area": area,
                "width": max_x - min_x + 1,
                "height": max_y - min_y + 1,
            })
    return components


def boxes_are_close(a: dict[str, int], b: dict[str, int], distance: int) -> bool:
    gap_x = max(0, max(b["x1"] - a["x2"], a["x1"] - b["x2"]))
    gap_y = max(0, max(b["y1"] - a["y2"], a["y1"] - b["y2"]))
    return gap_x <= distance and gap_y <= distance


def merge_boxes(boxes: list[dict[str, int]], distance: int) -> tuple[list[dict[str, int]], int]:
    remaining = [dict(box) for box in boxes]
    merged_boxes = []
    merge_count = 0
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            next_remaining = []
            for candidate in remaining:
                if boxes_are_close(current, candidate, distance):
                    current = {
                        "x1": min(current["x1"], candidate["x1"]),
                        "y1": min(current["y1"], candidate["y1"]),
                        "x2": max(current["x2"], candidate["x2"]),
                        "y2": max(current["y2"], candidate["y2"]),
                        "area": current["area"] + candidate["area"],
                        "width": max(current["x2"], candidate["x2"]) - min(current["x1"], candidate["x1"]),
                        "height": max(current["y2"], candidate["y2"]) - min(current["y1"], candidate["y1"]),
                    }
                    merge_count += 1
                    changed = True
                else:
                    next_remaining.append(candidate)
            remaining = next_remaining
        current["width"] = current["x2"] - current["x1"]
        current["height"] = current["y2"] - current["y1"]
        merged_boxes.append(current)
    return merged_boxes, merge_count


def yolo_line(class_id: int, box: dict[str, int], image_size: tuple[int, int]) -> str:
    width, height = image_size
    x_center = ((box["x1"] + box["x2"]) / 2) / width
    y_center = ((box["y1"] + box["y2"]) / 2) / height
    box_width = (box["x2"] - box["x1"]) / width
    box_height = (box["y2"] - box["y1"]) / height
    return f"{class_id} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"


def sanitize_for_preview_name(value: str) -> str:
    cleaned = []
    for ch in value:
        cleaned.append(ch if ch.isalnum() or ch in {"_", "-"} else "_")
    return "".join(cleaned)


def render_preview(image_path: Path, label_path: Path, output_path: Path, class_names: dict[int, str]) -> int:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    width, height = image.size
    bbox_count = 0
    if label_path.exists():
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            class_id_str, x_str, y_str, w_str, h_str = line.split()
            class_id = int(class_id_str)
            x = float(x_str)
            y = float(y_str)
            w = float(w_str)
            h = float(h_str)
            x1 = (x - w / 2) * width
            y1 = (y - h / 2) * height
            x2 = (x + w / 2) * width
            y2 = (y + h / 2) * height
            draw.rectangle([x1, y1, x2, y2], outline=(255, 40, 40), width=3)
            draw.text((x1 + 2, max(0, y1 - 12)), class_names[class_id], fill=(255, 255, 0), font=font)
            bbox_count += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=92)
    return bbox_count


def main() -> int:
    args = parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run_only", "next_step": "rerun with --execute"}, ensure_ascii=False, indent=2))
        return 0

    rules = load_yaml(resolve_path(args.rules_config))
    if rules.get("rule_version") != "riceseg_mask_to_bbox_revised_v0_1":
        raise RuntimeError("rules_config is not riceseg_mask_to_bbox_revised_v0_1")

    image_root = resolve_path(args.image_root)
    mask_root = resolve_path(args.mask_root)
    output_root = resolve_path(args.output_dataset)
    reports_dir = resolve_path(args.reports_dir)

    pairs = pair_images_masks(image_root, mask_root)
    rng = random.Random(args.seed)
    by_class: dict[str, list[tuple[Path, Path, str]]] = defaultdict(list)
    for pair in pairs:
        by_class[pair[2]].append(pair)
    for class_name in DEFAULT_CLASSES:
        rng.shuffle(by_class[class_name])

    per_class_target = args.preview_size // len(DEFAULT_CLASSES)
    split_targets = {
        "train": args.train_count // len(DEFAULT_CLASSES),
        "val": args.val_count // len(DEFAULT_CLASSES),
        "test": args.test_count // len(DEFAULT_CLASSES),
    }

    selected_rows = []
    index_counter = 0
    for class_name in DEFAULT_CLASSES:
        items = by_class[class_name][:per_class_target]
        if len(items) < per_class_target:
            raise RuntimeError(f"Not enough pairs for {class_name}: need {per_class_target}, got {len(items)}")
        boundaries = [split_targets['train'], split_targets['train'] + split_targets['val']]
        for local_idx, (image_path, mask_path, _) in enumerate(items):
            if local_idx < boundaries[0]:
                split = 'train'
            elif local_idx < boundaries[1]:
                split = 'val'
            else:
                split = 'test'
            stem = f"{class_name}_{index_counter:04d}_{image_path.stem}"
            selected_rows.append({
                "class_name": class_name,
                "class_id": DEFAULT_CLASSES.index(class_name),
                "split": split,
                "source_split": split,
                "dataset_name": "rice_phone_rgb_riceseg_preview_500_revised_v0_1",
                "source_dataset": "RiceSeg-5932 paired with Sethy phone RGB lineage",
                "source_image": str(image_path.resolve()),
                "source_mask": str(mask_path.resolve()),
                "image_name": f"{stem}.jpg",
                "label_name": f"{stem}.txt",
                "relative_image_path": str(Path('images') / split / f"{stem}.jpg"),
                "relative_label_path": str(Path('labels') / split / f"{stem}.txt"),
                "output_stem": stem,
            })
            index_counter += 1

    if output_root.exists():
        shutil.rmtree(output_root)
    visual_root = reports_dir / 'riceseg_preview_500_revised_v0_1_visual_audit'
    if visual_root.exists():
        shutil.rmtree(visual_root)
    for split in ('train', 'val', 'test'):
        (output_root / 'images' / split).mkdir(parents=True, exist_ok=True)
        (output_root / 'labels' / split).mkdir(parents=True, exist_ok=True)
    (output_root / 'metadata').mkdir(parents=True, exist_ok=True)
    visual_root.mkdir(parents=True, exist_ok=True)

    class_names_by_id = {idx: name for idx, name in enumerate(DEFAULT_CLASSES)}
    manifest_rows = []
    conversion_rows = []
    visual_manifest = []
    class_image_counter = Counter()
    class_bbox_counter = Counter()
    split_image_counter = Counter()
    split_bbox_counter = Counter()
    filter_reason_counter = Counter()
    risk_pool: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in selected_rows:
        class_name = row['class_name']
        split = row['split']
        class_id = row['class_id']
        image = Image.open(Path(row['source_image'])).convert('RGB')
        raw_mask = Image.open(Path(row['source_mask']))
        if image.size != raw_mask.size:
            raise RuntimeError(f"Image/mask size mismatch for {row['source_image']}")
        per_class_rules = rules['per_class'][class_name]
        global_rules = rules['global']
        open_kernel = int(per_class_rules.get('morph_open_kernel', global_rules['default_morph_open_kernel']))
        close_kernel = int(per_class_rules.get('morph_close_kernel', global_rules['default_morph_close_kernel']))
        min_area_pixels = int(per_class_rules.get('min_area_pixels', global_rules['default_min_area_pixels']))
        min_area_ratio = float(per_class_rules.get('min_area_ratio', global_rules['default_min_area_ratio']))
        min_box_width = int(per_class_rules.get('min_box_width', global_rules['default_min_box_width']))
        min_box_height = int(per_class_rules.get('min_box_height', global_rules['default_min_box_height']))
        merge_nearby = bool(per_class_rules.get('merge_nearby_boxes', global_rules['default_merge_nearby_boxes']))
        merge_distance = int(per_class_rules.get('merge_distance_pixels', global_rules['default_merge_distance_pixels']))
        min_area_effective = max(min_area_pixels, int(math.ceil(image.size[0] * image.size[1] * min_area_ratio)))

        morphed = binary_morphology(raw_mask, open_kernel, close_kernel)
        components = connected_components(morphed)
        kept = []
        filtered_tiny = 0
        filtered_small_box = 0
        for component in components:
            if component['area'] < min_area_effective:
                filtered_tiny += 1
                continue
            if component['width'] < min_box_width or component['height'] < min_box_height:
                filtered_small_box += 1
                continue
            kept.append(component)
        merged_component_count = 0
        if merge_nearby and kept:
            kept, merged_component_count = merge_boxes(kept, merge_distance)

        image_out = output_root / row['relative_image_path']
        label_out = output_root / row['relative_label_path']
        shutil.copy2(Path(row['source_image']), image_out)
        label_lines = [yolo_line(class_id, box, image.size) for box in kept]
        label_out.write_text(("\n".join(label_lines) + "\n") if label_lines else "", encoding='utf-8')

        review_id = f"{class_name}_{len([m for m in visual_manifest if m['class_name']==class_name]) + 1:03d}"
        preview_name = f"{review_id}_{sanitize_for_preview_name(Path(row['image_name']).stem)}.jpg"
        preview_path = visual_root / preview_name
        bbox_count = render_preview(image_out, label_out, preview_path, class_names_by_id)

        manifest_row = {
            **row,
            'original_preview_dataset': 'datasets/rice_phone_rgb_riceseg_preview_200_revised_v0_1',
            'old_bbox_count': '',
            'new_bbox_count': bbox_count,
            'bbox_count': bbox_count,
            'raw_component_count': len(components),
            'filtered_component_count': filtered_tiny + filtered_small_box,
            'filtered_tiny_component_count': filtered_tiny,
            'filtered_small_box_component_count': filtered_small_box,
            'merged_component_count': merged_component_count,
            'min_area_pixels_effective': min_area_effective,
            'min_box_width': min_box_width,
            'min_box_height': min_box_height,
            'morph_open_kernel': open_kernel,
            'morph_close_kernel': close_kernel,
            'merge_nearby_boxes': merge_nearby,
            'merge_distance_pixels': merge_distance,
            'conversion_rule_version': rules['rule_version'],
        }
        manifest_rows.append(manifest_row)
        conversion_rows.append({
            'image_name': row['image_name'],
            'class_name': class_name,
            'split': split,
            'bbox_count': bbox_count,
            'raw_component_count': len(components),
            'filtered_component_count': filtered_tiny + filtered_small_box,
            'filtered_tiny_component_count': filtered_tiny,
            'filtered_small_box_component_count': filtered_small_box,
            'merged_component_count': merged_component_count,
            'conversion_rule_version': rules['rule_version'],
        })
        visual_manifest.append({
            'review_id': review_id,
            'class_name': class_name,
            'split': split,
            'image_name': row['image_name'],
            'image_path': str(image_out.resolve()),
            'label_path': str(label_out.resolve()),
            'visual_preview_path': str(preview_path.resolve()),
            'bbox_count': bbox_count,
            'raw_component_count': len(components),
            'filtered_tiny_component_count': filtered_tiny,
            'merged_component_count': merged_component_count,
            'selection_reason': '',
            'conversion_rule_version': rules['rule_version'],
        })
        class_image_counter[class_name] += 1
        class_bbox_counter[class_name] += bbox_count
        split_image_counter[split] += 1
        split_bbox_counter[split] += bbox_count
        filter_reason_counter['filtered_tiny_components'] += filtered_tiny
        filter_reason_counter['filtered_small_box_components'] += filtered_small_box
        filter_reason_counter['merged_component_events'] += merged_component_count
        risk_pool[class_name].append({
            'review_id': review_id,
            'class_name': class_name,
            'split': split,
            'image_path': str(image_out.resolve()),
            'label_path': str(label_out.resolve()),
            'visual_preview_path': str(preview_path.resolve()),
            'bbox_count': bbox_count,
            'raw_component_count': len(components),
            'filtered_tiny_component_count': filtered_tiny,
            'merged_component_count': merged_component_count,
            'conversion_rule_version': rules['rule_version'],
        })

    data_yaml_payload = {
        'path': str(output_root.resolve()),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'nc': len(DEFAULT_CLASSES),
        'names': {idx: name for idx, name in enumerate(DEFAULT_CLASSES)},
    }
    write_text(output_root / 'data.yaml', yaml.safe_dump(data_yaml_payload, sort_keys=False, allow_unicode=True))
    write_text(output_root / 'metadata' / 'class_map.yaml', yaml.safe_dump({'classes': [{'id': i, 'name': n} for i, n in enumerate(DEFAULT_CLASSES)]}, sort_keys=False, allow_unicode=True))
    write_text(output_root / 'metadata' / 'revised_rules.yaml', yaml.safe_dump(rules, sort_keys=False, allow_unicode=True))
    write_csv(output_root / 'metadata' / 'conversion_manifest.csv', manifest_rows, list(manifest_rows[0].keys()))
    write_csv(output_root / 'metadata' / 'source_selection_manifest.csv', selected_rows, list(selected_rows[0].keys()))

    conversion_report = {
        'rule_version': rules['rule_version'],
        'source_lineage': 'RiceSeg-5932 + Sethy paired phone RGB lineage',
        'output_dataset': str(output_root.resolve()),
        'image_count': len(manifest_rows),
        'label_count': len(manifest_rows),
        'bbox_count': sum(class_bbox_counter.values()),
        'class_image_distribution': dict(class_image_counter),
        'class_bbox_distribution': dict(class_bbox_counter),
        'split_image_distribution': dict(split_image_counter),
        'split_bbox_distribution': dict(split_bbox_counter),
        'filter_reason_counter': dict(filter_reason_counter),
        'zero_label_images': [row['image_name'] for row in manifest_rows if int(row['new_bbox_count']) == 0],
    }
    write_json(output_root / 'metadata' / 'conversion_report.json', conversion_report)
    write_json(reports_dir / 'riceseg_preview_500_revised_v0_1_conversion_report.json', conversion_report)
    write_text(reports_dir / 'riceseg_preview_500_revised_v0_1_conversion_report.md', '\n'.join([
        '# RiceSeg preview_500 revised_v0_1 Conversion Report',
        '',
        f"- rule_version: `{rules['rule_version']}`",
        f"- output_dataset: `{output_root.resolve()}`",
        f"- image_count: `{len(manifest_rows)}`",
        f"- bbox_count: `{sum(class_bbox_counter.values())}`",
        '',
        '## Class Distribution',
        '',
        *[f"- `{name}`: images=`{class_image_counter[name]}` bbox=`{class_bbox_counter[name]}`" for name in DEFAULT_CLASSES],
        '',
        '## Split Distribution',
        '',
        *[f"- `{split}`: images=`{split_image_counter[split]}` bbox=`{split_bbox_counter[split]}`" for split in ('train','val','test')],
        '',
        '## Filter Summary',
        '',
        *[f"- `{k}`: `{v}`" for k, v in filter_reason_counter.items()],
        '',
    ]))

    quality_summary = {
        'preview_200_revised_gate': 'PASS',
        'preview_500_rule_version': rules['rule_version'],
        'class_bbox_distribution': dict(class_bbox_counter),
        'class_mean_bbox_count': {k: round(class_bbox_counter[k] / class_image_counter[k], 3) for k in DEFAULT_CLASSES},
        'high_bbox_samples': sorted([
            {'image_name': row['image_name'], 'class_name': row['class_name'], 'bbox_count': row['bbox_count']}
            for row in conversion_rows
        ], key=lambda x: (-x['bbox_count'], x['image_name']))[:20],
        'low_bbox_samples': sorted([
            {'image_name': row['image_name'], 'class_name': row['class_name'], 'bbox_count': row['bbox_count']}
            for row in conversion_rows
        ], key=lambda x: (x['bbox_count'], x['image_name']))[:20],
        'zero_label_images': conversion_report['zero_label_images'],
        'filtered_tiny_components': filter_reason_counter['filtered_tiny_components'],
        'merged_component_events': filter_reason_counter['merged_component_events'],
    }
    write_json(reports_dir / 'riceseg_preview_500_revised_v0_1_conversion_quality_summary.json', quality_summary)
    write_text(reports_dir / 'riceseg_preview_500_revised_v0_1_conversion_quality_summary.md', '\n'.join([
        '# RiceSeg preview_500 revised_v0_1 Conversion Quality Summary',
        '',
        '- preview_200_revised_v0_1 gate: `PASS`',
        f"- preview_500 rule_version: `{rules['rule_version']}`",
        f"- filtered_tiny_components: `{filter_reason_counter['filtered_tiny_components']}`",
        f"- merged_component_events: `{filter_reason_counter['merged_component_events']}`",
        f"- zero_label_images: `{len(conversion_report['zero_label_images'])}`",
        '',
        '## Class Mean BBox Count',
        '',
        *[f"- `{k}`: `{quality_summary['class_mean_bbox_count'][k]}`" for k in DEFAULT_CLASSES],
        '',
    ]))

    visual_rows = []
    review_rows = []
    for class_name in DEFAULT_CLASSES:
        ranked = sorted(
            risk_pool[class_name],
            key=lambda row: (
                -1 if class_name in {'bacterial_blight', 'tungro'} else 0,
                -row['merged_component_count'],
                -row['filtered_tiny_component_count'],
                -row['bbox_count'],
                row['image_path'],
            ),
        )
        # visual audit: 30 per class
        visual_pick = ranked[: args.visual_per_class]
        for row in visual_pick:
            visual_rows.append({
                **row,
                'source_image_name': Path(row['image_path']).name,
            })
        # manual review: 30 per class, diversify with low/high bbox and heavy-filter samples
        high = sorted(ranked, key=lambda r: (-r['bbox_count'], r['image_path']))[:10]
        low = sorted(ranked, key=lambda r: (r['bbox_count'], r['image_path']))[:10]
        heavy = sorted(ranked, key=lambda r: (-(r['merged_component_count'] + r['filtered_tiny_component_count']), -r['bbox_count'], r['image_path']))[:15]
        merged = []
        seen = set()
        for bucket, reason in ((high, 'high_bbox_count'), (low, 'low_bbox_count'), (heavy, 'high_filter_merge_risk'), (ranked, 'class_cover')):
            for row in bucket:
                if row['review_id'] in seen:
                    continue
                seen.add(row['review_id'])
                merged.append((row, reason))
                if len(merged) >= args.manual_review_per_class:
                    break
            if len(merged) >= args.manual_review_per_class:
                break
        for row, reason in merged[: args.manual_review_per_class]:
            review_rows.append({
                'review_id': row['review_id'],
                'class_name': row['class_name'],
                'split': row['split'],
                'image_path': row['image_path'],
                'label_path': row['label_path'],
                'visual_preview_path': row['visual_preview_path'],
                'bbox_count': row['bbox_count'],
                'selection_reason': reason,
                'conversion_rule_version': row['conversion_rule_version'],
                'review_status': 'unreviewed',
                'issue_type': '',
                'reviewer_notes': '',
                'reviewed_at': '',
            })

    write_csv(reports_dir / 'riceseg_preview_500_revised_v0_1_visual_audit_manifest.csv', visual_rows, list(visual_rows[0].keys()))
    write_json(reports_dir / 'riceseg_preview_500_revised_v0_1_visual_audit_manifest.json', {'items': visual_rows})
    write_csv(reports_dir / 'riceseg_preview_500_revised_v0_1_manual_review_items.csv', review_rows, list(review_rows[0].keys()))
    write_json(reports_dir / 'riceseg_preview_500_revised_v0_1_manual_review_items.json', {'items': review_rows})
    write_text(visual_root / 'index.md', '\n'.join([
        '# RiceSeg preview_500 revised_v0_1 Visual Audit',
        '',
        *[
            f"- `{row['review_id']}` / `{row['class_name']}` / `{row['split']}` / bbox=`{row['bbox_count']}` / source=`{row['source_image_name']}`"
            for row in visual_rows
        ],
        '',
    ]))

    result = {
        'dataset_root': str(output_root.resolve()),
        'visual_audit_root': str(visual_root.resolve()),
        'manual_review_items_csv': str((reports_dir / 'riceseg_preview_500_revised_v0_1_manual_review_items.csv').resolve()),
        'manual_review_items_json': str((reports_dir / 'riceseg_preview_500_revised_v0_1_manual_review_items.json').resolve()),
        'conversion_report_json': str((reports_dir / 'riceseg_preview_500_revised_v0_1_conversion_report.json').resolve()),
        'conversion_quality_summary_json': str((reports_dir / 'riceseg_preview_500_revised_v0_1_conversion_quality_summary.json').resolve()),
        'status': 'preview_500_generated',
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
