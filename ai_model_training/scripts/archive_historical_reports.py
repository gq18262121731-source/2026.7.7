#!/usr/bin/env python
"""Create an archive manifest and optionally move low-risk archive candidates."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from cleanup_historical_reports_inventory import (
    ARCHIVE_ROOT,
    build_inventory,
    markdown_table,
    write_json,
)


MANIFEST_CSV = Path("reports/report_cleanup_archive_manifest.csv")
MANIFEST_JSON = Path("reports/report_cleanup_archive_manifest.json")
MANIFEST_MD = Path("reports/report_cleanup_archive_manifest.md")


@dataclass
class ManifestRow:
    original_path: str
    archive_path: str
    action: str
    reason: str
    risk_level: str
    file_size: int
    checksum_sha256: str
    moved: bool
    timestamp: str


def checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_bucket(file_path: str, category_guess: str, reason: str) -> str:
    lower = " ".join((file_path, category_guess, reason)).lower()
    if "hotfix" in lower or "startup" in lower or "smoke_display" in lower:
        return "obsolete_hotfix_reports"
    if "frontend" in lower or "review app" in lower or "desktop_review_app" in lower:
        return "old_frontend_review_app"
    if "diagnostic" in lower or "log" in lower or "tmp" in lower:
        return "old_diagnostics"
    if "plan" in lower:
        return "superseded_plans"
    if "round summary" in lower or "_round" in lower:
        return "old_intermediate_summaries"
    return "misc_reviewed_keep_copy"


def make_archive_path(original_path: str, category_guess: str, reason: str) -> Path:
    bucket = archive_bucket(original_path, category_guess, reason)
    return ARCHIVE_ROOT / bucket / original_path


def write_manifest_csv(root: Path, rows: list[ManifestRow]) -> None:
    path = root / MANIFEST_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ManifestRow.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_manifest_markdown(root: Path, rows: list[ManifestRow], execute: bool) -> None:
    path = root / MANIFEST_MD
    path.parent.mkdir(parents=True, exist_ok=True)
    row_dicts = [row.__dict__ for row in rows]
    columns = [
        "original_path",
        "archive_path",
        "action",
        "reason",
        "risk_level",
        "file_size",
        "moved",
    ]
    content = [
        "# Report Cleanup Archive Manifest",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Execute mode: {'yes' if execute else 'no'}",
        f"- Manifest rows: {len(rows)}",
        "- Permanent deletion: no",
        "",
        "Archive paths preserve the original relative path under the selected archive bucket.",
        "",
        markdown_table(row_dicts, columns, limit=250),
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def write_manifest_json(root: Path, rows: list[ManifestRow], execute: bool) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "execute_mode": execute,
        "permanent_deletion": False,
        "archive_root": ARCHIVE_ROOT.as_posix(),
        "rows": [row.__dict__ for row in rows],
    }
    write_json(root / MANIFEST_JSON, payload)


def move_one(root: Path, row: ManifestRow) -> None:
    source = root / row.original_path
    target = root / row.archive_path
    if not source.exists():
        raise FileNotFoundError(f"Source missing before archive move: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Archive target already exists: {target}")
    shutil.move(str(source), str(target))
    if not target.exists():
        raise FileNotFoundError(f"Archive target missing after move: {target}")
    row.moved = True


def rollback(root: Path, rows: list[ManifestRow]) -> None:
    for row in reversed(rows):
        if not row.moved:
            continue
        source = root / row.archive_path
        target = root / row.original_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists() and not target.exists():
            shutil.move(str(source), str(target))
        row.moved = False


def build_manifest(root: Path) -> list[ManifestRow]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[ManifestRow] = []
    for item in build_inventory(root):
        if item.recommended_action != "ARCHIVE_CANDIDATE":
            continue
        archive_path = make_archive_path(item.file_path, item.category_guess, item.archive_reason)
        rows.append(
            ManifestRow(
                original_path=item.file_path,
                archive_path=archive_path.as_posix(),
                action=item.recommended_action,
                reason=item.archive_reason,
                risk_level=item.risk_level,
                file_size=item.size_bytes,
                checksum_sha256=checksum(root / item.file_path),
                moved=False,
                timestamp=timestamp,
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Do not move files. This is the default.")
    mode.add_argument("--execute", action="store_true", help="Move only low-risk ARCHIVE_CANDIDATE files.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    execute = bool(args.execute)
    rows = build_manifest(root)

    if execute:
        movable = [row for row in rows if row.action == "ARCHIVE_CANDIDATE" and row.risk_level == "low"]
        moved_rows: list[ManifestRow] = []
        try:
            for row in movable:
                move_one(root, row)
                moved_rows.append(row)
        except Exception:
            rollback(root, moved_rows)
            raise

    write_manifest_csv(root, rows)
    write_manifest_json(root, rows, execute)
    write_manifest_markdown(root, rows, execute)

    print(f"Manifest rows: {len(rows)}")
    print(f"Execute mode: {'yes' if execute else 'no'}")
    print(f"Wrote {MANIFEST_CSV}, {MANIFEST_JSON}, {MANIFEST_MD}.")
    if not execute:
        print("Dry-run only: no files were moved or deleted.")
    else:
        print("Archive move complete. No files were deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
