from __future__ import annotations

import hashlib
import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.schemas.experimental_uav_blb_segmentation import (
    UavBlbSegmentationDryRunResponse,
    UavBlbSegmentationFieldTrialRecord,
    UavBlbSegmentationFieldTrialResponse,
)

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dry-run dependency
    np = None


MODEL_NAME = "uav_blb_segmentation_408_patch_v2_d2_ndvi_unet_baseline"
MODEL_STAGE = "formal_candidate"
MODEL_WARNING = "experimental_dry_run_only_not_for_production"
MODE = "dry_run_only"
FIELD_TRIAL_MODE = "field_trial_only"
FIELD_TRIAL_WARNING = "field_trial_not_for_production"
INPUT_CONFIG = "D2_5BAND_NDVI"
PATCH_SIZE = 256
STRIDE = 128
THRESHOLD = 0.45
MIN_AREA = 128
POSTPROCESS_MODE = "THRESHOLD_REMOVE_SMALL_COMPONENTS"
EXPECTED_SHA256 = "62e9e88ee8778bdf4fa94547daa1395c6c1d49b4e6270af1b08062117057fb67"


class DryRunError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        detail: dict | None = None,
        *,
        mode: str = MODE,
        backend_integration_allowed: str = "dry_run_only",
        warning: str = MODEL_WARNING,
    ) -> None:
        self.status_code = status_code
        self.payload = {
            "success": False,
            "mode": mode,
            "error_code": error_code,
            "message": message,
            "detail": detail or {},
            "production_ready": False,
            "backend_integration_allowed": backend_integration_allowed,
            "model_stage": MODEL_STAGE,
            "warning": warning,
        }
        super().__init__(message)


class UavBlbSegmentationDryRunService:
    def __init__(self) -> None:
        self.artifact_lock_path = (
            settings.training_dir / "reports" / "uav_blb_segmentation_408_patch_v2_model_artifact_lock.json"
        )
        self.output_root = settings.static_dir / "experimental" / "uav_blb_segmentation_dry_run"
        self.field_trial_output_root = settings.static_dir / "experimental" / "uav_blb_field_trial_outputs"
        self.field_trial_storage_root = settings.backend_dir / "storage" / "experimental"
        self.field_trial_records_path = self.field_trial_storage_root / "uav_blb_field_trial_records.jsonl"

    async def dry_run_upload(
        self,
        file: UploadFile,
        mode: str,
        return_probability_map: bool = True,
        return_overlay: bool = True,
    ) -> UavBlbSegmentationDryRunResponse:
        if mode != MODE:
            raise DryRunError(400, "INVALID_DRY_RUN_MODE", "mode must be dry_run_only", {"mode": mode})
        self._validate_filename(file.filename)
        job_id = f"uav_blb_seg_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        job_dir = self.output_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / f"input{Path(file.filename or '').suffix.lower()}"
        await self._save_upload(file, input_path)
        lock = self._load_and_verify_artifact_lock()
        try:
            probability, binary, preview = self._run_inference(input_path, lock)
        except DryRunError:
            raise
        except Exception as exc:
            raise DryRunError(500, "DRY_RUN_INFERENCE_FAILED", "UAV BLB segmentation dry-run inference failed", {"reason": str(exc)}) from exc

        probability_url = self._save_probability(job_dir, probability) if return_probability_map else ""
        mask_url = self._save_mask(job_dir, binary)
        preview_url, overlay_url = self._save_preview_and_overlay(job_dir, preview, binary, return_overlay)
        return UavBlbSegmentationDryRunResponse(
            model_name=MODEL_NAME,
            weight_sha256=EXPECTED_SHA256,
            disease_area_ratio=float(binary.mean()),
            mask_url=mask_url,
            overlay_url=overlay_url,
            probability_map_url=probability_url,
            original_preview_url=preview_url,
        )

    async def field_trial_upload(
        self,
        file: UploadFile,
        mode: str,
        plot_id: str | None = None,
        plot_name: str | None = None,
        operator_note: str | None = None,
        human_review_status: str = "pending",
        human_review_label: str | None = None,
        issue_tags: str | None = None,
        return_probability_map: bool = True,
        return_overlay: bool = True,
    ) -> UavBlbSegmentationFieldTrialResponse:
        if mode != FIELD_TRIAL_MODE:
            raise self._field_trial_error(
                400,
                "INVALID_FIELD_TRIAL_MODE",
                "mode must be field_trial_only",
                {"mode": mode},
            )
        self._validate_filename(file.filename, mode=FIELD_TRIAL_MODE)
        self._validate_human_review(human_review_status, human_review_label)

        created_at = datetime.now(timezone.utc)
        trial_id = f"uav_blb_field_trial_{created_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        job_dir = self.field_trial_output_root / trial_id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / f"input{Path(file.filename or '').suffix.lower()}"
        await self._save_upload(file, input_path, mode=FIELD_TRIAL_MODE)
        lock = self._load_and_verify_artifact_lock()
        start = time.perf_counter()
        try:
            probability, binary, preview = self._run_inference(input_path, lock)
        except DryRunError as exc:
            raise self._convert_to_field_trial_error(exc) from exc
        except Exception as exc:
            raise self._field_trial_error(
                500,
                "FIELD_TRIAL_INFERENCE_FAILED",
                "UAV BLB segmentation field-trial inference failed",
                {"reason": str(exc)},
            ) from exc
        inference_time_ms = int((time.perf_counter() - start) * 1000)

        probability_url = self._save_probability(job_dir, probability) if return_probability_map else ""
        mask_url = self._save_mask(job_dir, binary)
        preview_url, overlay_url = self._save_preview_and_overlay(job_dir, preview, binary, return_overlay)
        record = UavBlbSegmentationFieldTrialRecord(
            trial_id=trial_id,
            plot_id=plot_id,
            plot_name=plot_name,
            tif_filename=file.filename or input_path.name,
            model_name=MODEL_NAME,
            model_sha256=EXPECTED_SHA256,
            disease_area_ratio=float(binary.mean()),
            mask_url=mask_url,
            overlay_url=overlay_url,
            probability_map_url=probability_url,
            original_preview_url=preview_url,
            inference_time_ms=inference_time_ms,
            created_at=created_at.isoformat(),
            operator_note=operator_note,
            human_review_status=human_review_status,
            human_review_label=human_review_label,
            issue_tags=self._parse_issue_tags(issue_tags),
        )
        self._append_field_trial_record(record)
        return UavBlbSegmentationFieldTrialResponse(
            model_name=MODEL_NAME,
            weight_sha256=EXPECTED_SHA256,
            disease_area_ratio=record.disease_area_ratio,
            mask_url=mask_url,
            overlay_url=overlay_url,
            probability_map_url=probability_url,
            original_preview_url=preview_url,
            trial_record=record,
        )

    def list_field_trial_records(self, limit: int = 100) -> list[UavBlbSegmentationFieldTrialRecord]:
        records = self._read_field_trial_records()
        return records[-limit:][::-1]

    def export_field_trial_records_csv(self) -> str:
        records = [record.model_dump() for record in self._read_field_trial_records()]
        fieldnames = [
            "trial_id",
            "plot_id",
            "plot_name",
            "tif_filename",
            "input_config",
            "model_name",
            "model_sha256",
            "threshold",
            "min_area",
            "disease_area_ratio",
            "mask_url",
            "overlay_url",
            "probability_map_url",
            "inference_time_ms",
            "mode",
            "model_stage",
            "production_ready",
            "warning",
            "created_at",
            "operator_note",
            "human_review_status",
            "human_review_label",
            "issue_tags",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["issue_tags"] = ",".join(row.get("issue_tags") or [])
            writer.writerow(row)
        return output.getvalue()

    def export_field_trial_records_json(self) -> dict:
        records = [record.model_dump() for record in self._read_field_trial_records()]
        return {
            "success": True,
            "mode": FIELD_TRIAL_MODE,
            "production_ready": False,
            "backend_integration_allowed": "field_trial_only",
            "records": records,
            "total": len(records),
        }

    def _validate_filename(self, filename: str | None, mode: str = MODE) -> None:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in {".tif", ".tiff"}:
            detail = {"filename": filename, "reason": "unsupported_extension", "fallback_to_rgb_or_yolo": False}
            if mode == FIELD_TRIAL_MODE:
                raise self._field_trial_error(
                    400,
                    "INVALID_MULTISPECTRAL_TIF",
                    "UAV BLB segmentation field trial requires a readable 5-band multispectral TIF that can produce D2_5BAND_NDVI.",
                    detail,
                )
            raise DryRunError(
                400,
                "INVALID_MULTISPECTRAL_TIF",
                "UAV BLB segmentation dry-run requires a readable 5-band multispectral TIF that can produce D2_5BAND_NDVI.",
                detail,
            )

    async def _save_upload(self, file: UploadFile, target_path: Path, mode: str = MODE) -> None:
        size = 0
        try:
            with target_path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_size_bytes:
                        target_path.unlink(missing_ok=True)
                        if mode == FIELD_TRIAL_MODE:
                            raise self._field_trial_error(
                                400,
                                "FILE_TOO_LARGE",
                                "Uploaded field-trial TIF exceeds backend upload size limit.",
                                {"max_upload_size_mb": settings.max_upload_size_mb},
                            )
                        raise DryRunError(
                            400,
                            "FILE_TOO_LARGE",
                            "Uploaded dry-run TIF exceeds backend upload size limit.",
                            {"max_upload_size_mb": settings.max_upload_size_mb},
                        )
                    output.write(chunk)
            if size <= 0:
                target_path.unlink(missing_ok=True)
                if mode == FIELD_TRIAL_MODE:
                    raise self._field_trial_error(
                        400,
                        "INVALID_MULTISPECTRAL_TIF",
                        "Uploaded field-trial TIF is empty.",
                        {"reason": "empty_file"},
                    )
                raise DryRunError(400, "INVALID_MULTISPECTRAL_TIF", "Uploaded dry-run TIF is empty.", {"reason": "empty_file"})
        finally:
            await file.close()

    def _load_and_verify_artifact_lock(self) -> dict:
        if not self.artifact_lock_path.exists():
            raise DryRunError(
                503,
                "DRY_RUN_MODEL_UNAVAILABLE",
                "UAV BLB segmentation dry-run artifact lock is missing.",
                {"artifact_lock": str(self.artifact_lock_path)},
            )
        lock = json.loads(self.artifact_lock_path.read_text(encoding="utf-8"))
        if lock.get("production_ready") is not False or lock.get("backend_integration_allowed") != "dry_run_only":
            raise DryRunError(503, "DRY_RUN_MODEL_UNAVAILABLE", "Artifact lock is not dry-run-only.", {"artifact_lock": str(self.artifact_lock_path)})
        if lock.get("sha256", "").lower() != EXPECTED_SHA256:
            raise DryRunError(503, "DRY_RUN_MODEL_UNAVAILABLE", "Artifact lock sha256 does not match expected dry-run candidate.", {})
        weight_path = settings.training_dir / lock["weight_path"]
        if not weight_path.exists():
            raise DryRunError(503, "DRY_RUN_MODEL_UNAVAILABLE", "Dry-run model weight is missing.", {"weight_path": str(weight_path)})
        actual_sha = self._sha256_file(weight_path)
        if actual_sha.lower() != EXPECTED_SHA256:
            raise DryRunError(503, "DRY_RUN_MODEL_UNAVAILABLE", "Dry-run model weight sha256 verification failed.", {"actual_sha256": actual_sha})
        return lock

    def _run_inference(self, input_path: Path, lock: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        try:
            import torch
            import tifffile
        except Exception as exc:
            raise DryRunError(
                503,
                "DRY_RUN_MODEL_UNAVAILABLE",
                "Dry-run optional dependencies are unavailable. Install torch, numpy, and tifffile in the dry-run environment.",
                {"reason": str(exc)},
            ) from exc
        if np is None:
            raise DryRunError(
                503,
                "DRY_RUN_MODEL_UNAVAILABLE",
                "Dry-run optional dependency numpy is unavailable.",
                {},
            )

        try:
            raw_tif = tifffile.imread(input_path)
        except Exception as exc:
            raise DryRunError(
                400,
                "INVALID_MULTISPECTRAL_TIF",
                "Uploaded TIF could not be read as a valid multispectral raster.",
                {"reason": "unreadable_tif", "fallback_to_rgb_or_yolo": False},
            ) from exc
        hwc = self._image_to_hwc(raw_tif).astype(np.float32)
        if hwc.shape[-1] < 5:
            raise DryRunError(
                400,
                "INVALID_MULTISPECTRAL_TIF",
                "UAV BLB segmentation dry-run requires at least 5 spectral bands.",
                {"shape": list(hwc.shape), "fallback_to_rgb_or_yolo": False},
            )
        if not np.isfinite(hwc[..., :5]).all():
            raise DryRunError(400, "INVALID_MULTISPECTRAL_TIF", "TIF contains non-finite values in the first 5 bands.", {})
        preview = self._render_rgb_from_tif_hwc(hwc)
        d2 = self._build_d2_5band_ndvi(hwc)
        weight_path = settings.training_dir / lock["weight_path"]
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = self._load_model(weight_path, device, torch)
        probability = self._sliding_window_probability(d2, model, device, torch)
        binary = self._remove_small_components(probability >= THRESHOLD, MIN_AREA)
        return probability.astype(np.float32), binary.astype(bool), preview

    def _load_model(self, weight_path: Path, device, torch_module):
        model = self._build_unet_baseline(torch_module, in_channels=6, base=24)
        checkpoint = torch_module.load(weight_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        model.to(device)
        model.eval()
        return model

    def _build_unet_baseline(self, torch_module, in_channels: int, base: int):
        nn = torch_module.nn

        class ConvBlock(nn.Module):
            def __init__(self, in_ch: int, out_ch: int) -> None:
                super().__init__()
                self.net = nn.Sequential(
                    nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                )

            def forward(self, x):
                return self.net(x)

        class UNetBaseline(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.down1 = ConvBlock(in_channels, base)
                self.down2 = ConvBlock(base, base * 2)
                self.down3 = ConvBlock(base * 2, base * 4)
                self.pool = nn.MaxPool2d(2)
                self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
                self.dec2 = ConvBlock(base * 4, base * 2)
                self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
                self.dec1 = ConvBlock(base * 2, base)
                self.out = nn.Conv2d(base, 1, 1)

            def forward(self, x):
                x1 = self.down1(x)
                x2 = self.down2(self.pool(x1))
                x3 = self.down3(self.pool(x2))
                y = self.up2(x3)
                y = self.dec2(torch_module.cat([y, x2], dim=1))
                y = self.up1(y)
                y = self.dec1(torch_module.cat([y, x1], dim=1))
                return self.out(y)

        return UNetBaseline()

    def _sliding_window_probability(self, d2: np.ndarray, model, device, torch_module) -> np.ndarray:
        h, w = d2.shape[:2]
        prob_sum = np.zeros((h, w), dtype=np.float32)
        count = np.zeros((h, w), dtype=np.float32)
        with torch_module.no_grad():
            for y in self._sliding_positions(h):
                for x in self._sliding_positions(w):
                    patch, valid_h, valid_w = self._pad_patch(d2, y, x)
                    patch = self._normalize_feature(patch)
                    tensor = torch_module.from_numpy(np.moveaxis(patch, -1, 0)[None].astype(np.float32)).to(device)
                    prob = torch_module.sigmoid(model(tensor))[0, 0].cpu().numpy()
                    prob_sum[y : y + valid_h, x : x + valid_w] += prob[:valid_h, :valid_w]
                    count[y : y + valid_h, x : x + valid_w] += 1.0
        return prob_sum / np.maximum(count, 1.0)

    def _save_probability(self, job_dir: Path, probability: np.ndarray) -> str:
        np.save(job_dir / "probability_map.npy", probability.astype(np.float32))
        Image.fromarray(np.clip(probability * 255, 0, 255).astype(np.uint8), mode="L").save(job_dir / "probability_map.png")
        return self._static_url(job_dir / "probability_map.npy")

    def _save_mask(self, job_dir: Path, binary: np.ndarray) -> str:
        Image.fromarray(binary.astype(np.uint8) * 255, mode="L").save(job_dir / "mask.png")
        return self._static_url(job_dir / "mask.png")

    def _save_preview_and_overlay(self, job_dir: Path, preview: np.ndarray, binary: np.ndarray, return_overlay: bool) -> tuple[str, str]:
        preview_path = job_dir / "original_preview.jpg"
        Image.fromarray(preview).save(preview_path, quality=92)
        overlay_path = job_dir / "overlay.jpg"
        if return_overlay:
            overlay = preview.copy()
            overlay[binary] = (0.45 * overlay[binary] + 0.55 * np.array([255, 0, 0])).astype(np.uint8)
            Image.fromarray(overlay).save(overlay_path, quality=92)
        else:
            Image.fromarray(preview).save(overlay_path, quality=92)
        return self._static_url(preview_path), self._static_url(overlay_path)

    def _static_url(self, path: Path) -> str:
        relative = path.resolve().relative_to(settings.static_dir.resolve()).as_posix()
        return f"/static/{relative}"

    def _field_trial_error(
        self,
        status_code: int,
        error_code: str,
        message: str,
        detail: dict | None = None,
    ) -> DryRunError:
        return DryRunError(
            status_code,
            error_code,
            message,
            detail,
            mode=FIELD_TRIAL_MODE,
            backend_integration_allowed="field_trial_only",
            warning=FIELD_TRIAL_WARNING,
        )

    def _convert_to_field_trial_error(self, exc: DryRunError) -> DryRunError:
        return self._field_trial_error(
            exc.status_code,
            exc.payload.get("error_code", "FIELD_TRIAL_INFERENCE_FAILED"),
            exc.payload.get("message", "UAV BLB segmentation field trial failed."),
            exc.payload.get("detail", {}),
        )

    def _append_field_trial_record(self, record: UavBlbSegmentationFieldTrialRecord) -> None:
        self.field_trial_storage_root.mkdir(parents=True, exist_ok=True)
        with self.field_trial_records_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

    def _read_field_trial_records(self) -> list[UavBlbSegmentationFieldTrialRecord]:
        if not self.field_trial_records_path.exists():
            return []
        records: list[UavBlbSegmentationFieldTrialRecord] = []
        for line in self.field_trial_records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(UavBlbSegmentationFieldTrialRecord(**json.loads(line)))
        return records

    def _parse_issue_tags(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _validate_human_review(self, status: str, label: str | None) -> None:
        allowed_status = {"pending", "reviewed", "needs_review"}
        allowed_labels = {
            "acceptable",
            "over_segmentation",
            "under_segmentation",
            "noise_false_positive",
            "background_false_positive",
            "alignment_error",
            "major_failure",
            "uncertain",
        }
        if status not in allowed_status:
            raise self._field_trial_error(
                400,
                "INVALID_HUMAN_REVIEW_STATUS",
                "human_review_status must be pending, reviewed, or needs_review.",
                {"human_review_status": status},
            )
        if label and label not in allowed_labels:
            raise self._field_trial_error(
                400,
                "INVALID_HUMAN_REVIEW_LABEL",
                "human_review_label is not supported for UAV BLB field trial review.",
                {"human_review_label": label, "allowed_labels": sorted(allowed_labels)},
            )

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _image_to_hwc(self, arr: np.ndarray) -> np.ndarray:
        if arr.ndim == 2:
            return arr[..., None]
        if arr.ndim == 3 and arr.shape[-1] <= 16:
            return arr
        if arr.ndim == 3 and arr.shape[0] <= 16:
            return np.moveaxis(arr, 0, -1)
        raise DryRunError(400, "INVALID_MULTISPECTRAL_TIF", "Unsupported TIF shape.", {"shape": list(arr.shape)})

    def _build_d2_5band_ndvi(self, hwc: np.ndarray) -> np.ndarray:
        base5 = np.zeros((hwc.shape[0], hwc.shape[1], 5), dtype=np.float32)
        base5[..., :5] = hwc[..., :5].astype(np.float32)
        red = base5[..., 2]
        nir = base5[..., 4]
        ndvi = ((nir - red) / (nir + red + 1e-6)).astype(np.float32)
        return np.concatenate([base5, ndvi[..., None]], axis=-1).astype(np.float32)

    def _normalize_feature(self, arr: np.ndarray) -> np.ndarray:
        arr = arr.astype(np.float32)
        out = np.zeros_like(arr, dtype=np.float32)
        for idx in range(arr.shape[-1]):
            band = arr[..., idx]
            low = np.percentile(band, 1)
            high = np.percentile(band, 99)
            if high <= low:
                high = low + 1.0
            out[..., idx] = np.clip((band - low) / (high - low), 0, 1)
        return out

    def _render_rgb_from_tif_hwc(self, hwc: np.ndarray) -> np.ndarray:
        if hwc.shape[-1] >= 3:
            rgb = np.stack([self._normalize_band(hwc[..., idx]) for idx in range(3)], axis=-1)
        else:
            one = self._normalize_band(hwc[..., 0])
            rgb = np.stack([one, one, one], axis=-1)
        return (rgb * 255).astype(np.uint8)

    def _normalize_band(self, band: np.ndarray) -> np.ndarray:
        band = band.astype(np.float32)
        low = np.percentile(band, 1)
        high = np.percentile(band, 99)
        if high <= low:
            high = low + 1.0
        return np.clip((band - low) / (high - low), 0, 1)

    def _sliding_positions(self, length: int) -> list[int]:
        if length <= PATCH_SIZE:
            return [0]
        positions = list(range(0, max(1, length - PATCH_SIZE + 1), STRIDE))
        last = length - PATCH_SIZE
        if positions[-1] != last:
            positions.append(last)
        return positions

    def _pad_patch(self, arr: np.ndarray, y: int, x: int) -> tuple[np.ndarray, int, int]:
        patch = arr[y : y + PATCH_SIZE, x : x + PATCH_SIZE, :]
        valid_h, valid_w = patch.shape[:2]
        if valid_h == PATCH_SIZE and valid_w == PATCH_SIZE:
            return patch, valid_h, valid_w
        padded = np.zeros((PATCH_SIZE, PATCH_SIZE, arr.shape[-1]), dtype=arr.dtype)
        padded[:valid_h, :valid_w, :] = patch
        return padded, valid_h, valid_w

    def _remove_small_components(self, binary: np.ndarray, min_area: int) -> np.ndarray:
        try:
            from scipy import ndimage

            labeled, count = ndimage.label(binary)
            if count == 0:
                return np.zeros_like(binary, dtype=bool)
            sizes = np.bincount(labeled.ravel())
            keep = sizes >= min_area
            keep[0] = False
            return keep[labeled]
        except Exception:
            return self._remove_small_components_fallback(binary, min_area)

    def _remove_small_components_fallback(self, binary: np.ndarray, min_area: int) -> np.ndarray:
        h, w = binary.shape
        seen = np.zeros_like(binary, dtype=bool)
        out = np.zeros_like(binary, dtype=bool)
        for start_y in range(h):
            for start_x in range(w):
                if not binary[start_y, start_x] or seen[start_y, start_x]:
                    continue
                stack = [(start_y, start_x)]
                seen[start_y, start_x] = True
                coords = []
                while stack:
                    y, x = stack.pop()
                    coords.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if len(coords) >= min_area:
                    yy, xx = zip(*coords)
                    out[np.array(yy), np.array(xx)] = True
        return out


uav_blb_segmentation_dry_run_service = UavBlbSegmentationDryRunService()
