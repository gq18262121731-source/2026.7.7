from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.constants import ERROR_STORAGE, SEVERITY_HEAVY, SEVERITY_LIGHT, SEVERITY_MEDIUM, SEVERITY_NONE
from app.core.exceptions import AppException
from app.schemas.detection_result import Detection


class ResultRenderer:
    label_map = {
        "\u7a3b\u761f\u75c5": "rice_blast",
        "\u7eb9\u67af\u75c5": "sheath_blight",
        "\u7a3b\u66f2\u75c5": "false_smut",
        "\u7a3b\u98de\u8671": "planthopper",
        "\u7a3b\u7eb5\u5377\u53f6\u879f": "leaf_folder",
    }
    severity_map = {
        SEVERITY_NONE: "none",
        SEVERITY_LIGHT: "light",
        SEVERITY_MEDIUM: "medium",
        SEVERITY_HEAVY: "heavy",
    }

    def render(
        self,
        image_path: str,
        output_path: str,
        detections: list[Detection],
        severity: str,
    ) -> None:
        try:
            with Image.open(image_path).convert("RGB") as image:
                draw = ImageDraw.Draw(image)
                font = ImageFont.load_default()
                for detection in detections:
                    x1, y1, x2, y2 = detection.bbox
                    draw.rectangle([x1, y1, x2, y2], outline=(255, 64, 64), width=3)
                    label = self.label_map.get(detection.label, "disease")
                    severity_text = self.severity_map.get(severity, "risk")
                    text = f"{label} {detection.confidence:.2f} {severity_text}"
                    text_box = draw.textbbox((x1, y1), text, font=font)
                    draw.rectangle(
                        [text_box[0], max(0, text_box[1] - 2), text_box[2] + 4, text_box[3] + 2],
                        fill=(255, 64, 64),
                    )
                    draw.text((x1 + 2, max(0, y1 - 1)), text, fill=(255, 255, 255), font=font)
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path)
        except Exception as exc:
            raise AppException(ERROR_STORAGE, "\u7ed3\u679c\u56fe\u751f\u6210\u5931\u8d25", {"reason": str(exc)}) from exc
