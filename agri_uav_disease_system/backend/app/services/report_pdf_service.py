from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class ReportPdfService:
    def __init__(self) -> None:
        self.template_dir = Path(__file__).resolve().parents[1] / "templates" / "reports"
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(("html", "xml")),
        )

    def render_html(self, data: dict[str, Any], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("farm_analysis_report.html")
        css_path = self.template_dir / "farm_analysis_report.css"
        payload = {**data, "report_css": css_path.read_text(encoding="utf-8")}
        output_path.write_text(template.render(**payload), encoding="utf-8")
        return output_path

    def generate_pdf(self, html_path: Path, pdf_path: Path, data: dict[str, Any]) -> bool:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        if self._try_playwright_pdf(html_path, pdf_path):
            return False
        self._write_simple_pdf(pdf_path, self._plain_lines(data))
        return True

    def _try_playwright_pdf(self, html_path: Path, pdf_path: Path) -> bool:
        script = (
            "from pathlib import Path\n"
            "from playwright.sync_api import sync_playwright\n"
            f"html_path = Path(r'{html_path}')\n"
            f"pdf_path = Path(r'{pdf_path}')\n"
            "with sync_playwright() as p:\n"
            "    browser = p.chromium.launch()\n"
            "    page = browser.new_page(viewport={'width': 1240, 'height': 1754})\n"
            "    page.goto(html_path.resolve().as_uri(), wait_until='networkidle')\n"
            "    page.pdf(path=str(pdf_path), format='A4', print_background=True, margin={'top':'12mm','right':'12mm','bottom':'12mm','left':'12mm'})\n"
            "    browser.close()\n"
        )
        try:
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=45,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return pdf_path.exists() and pdf_path.stat().st_size > 800

    def _plain_lines(self, data: dict[str, Any]) -> list[str]:
        lines = [
            str(data.get("title") or "水稻农情分析报告"),
            f"报告编号: {data.get('report_id')}",
            f"生成时间: {data.get('created_at')}",
            f"地块: {data.get('plot_name')}",
            "",
            str(data.get("summary") or ""),
            "",
            "天气分析:",
            str(data.get("weather_analysis") or ""),
            "",
            "检测结果:",
        ]
        for item in data.get("detection_rows", []):
            lines.append(f"- {item.get('label')} / {float(item.get('confidence') or 0):.0%} / {item.get('risk_level')}")
        lines.extend(["", "历史趋势:"])
        if data.get("history_rows"):
            for item in data.get("history_rows", []):
                lines.append(f"- {item.get('date')}: {item.get('total')} 次检测, {item.get('abnormal')} 次异常")
        else:
            lines.append(str(data.get("insufficient_history_message") or "当前历史检测记录不足，暂不生成长期趋势判断。"))
        lines.extend(["", "知识依据:"])
        if data.get("rag_chunks"):
            for item in data.get("rag_chunks", []):
                lines.append(f"- {item.get('title')}: {item.get('content')}")
        else:
            lines.append("- RAG 证据不足，未补写知识依据。")
        lines.extend(["", "不确定性说明:"])
        lines.extend(f"- {item}" for item in data.get("uncertainty", []))
        lines.extend(["", f"结论: {data.get('conclusion')}", "本报告为辅助分析结果，不作为最终农事处置依据。"])
        return lines

    def _write_simple_pdf(self, pdf_path: Path, lines: list[str]) -> None:
        wrapped = []
        for line in lines:
            text = str(line)
            if not text:
                wrapped.append("")
                continue
            while len(text) > 42:
                wrapped.append(text[:42])
                text = text[42:]
            wrapped.append(text)

        lines_per_page = 42
        pages = [wrapped[index : index + lines_per_page] for index in range(0, len(wrapped), lines_per_page)] or [["水稻农情分析报告"]]
        font_object_id = 3 + len(pages)
        content_object_start = font_object_id + 1
        page_ids = list(range(3, 3 + len(pages)))
        content_ids = list(range(content_object_start, content_object_start + len(pages)))

        objects: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{item} 0 R' for item in page_ids)}] /Count {len(page_ids)} >>".encode("ascii"),
        ]
        for content_id in content_ids:
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
            )
        objects.append(
            b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H "
            b"/DescendantFonts [<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> "
            b"/FontDescriptor << /Type /FontDescriptor /FontName /STSong-Light /Flags 4 "
            b"/FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >> >>] >>"
        )
        for page_index, page_lines in enumerate(pages, 1):
            text_commands = ["BT", "/F1 11 Tf", "50 790 Td", "15 TL"]
            for index, line in enumerate(page_lines):
                if index:
                    text_commands.append("T*")
                text_commands.append(f"<{self._pdf_hex(line)}> Tj")
            text_commands.append("T*")
            text_commands.append(f"<{self._pdf_hex(f'第 {page_index} 页 / 共 {len(pages)} 页')}> Tj")
            text_commands.append("ET")
            stream = "\n".join(text_commands).encode("ascii")
            objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

        payload = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for idx, obj in enumerate(objects, 1):
            offsets.append(len(payload))
            payload.extend(f"{idx} 0 obj\n".encode("ascii"))
            payload.extend(obj)
            payload.extend(b"\nendobj\n")
        xref = len(payload)
        payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets[1:]:
            payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        payload.extend(
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        )
        pdf_path.write_bytes(payload)

    def _pdf_hex(self, value: str) -> str:
        return str(value).encode("utf-16-be", errors="replace").hex().upper()


report_pdf_service = ReportPdfService()
