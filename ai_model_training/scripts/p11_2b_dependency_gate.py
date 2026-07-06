from __future__ import annotations

import importlib.util
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
EXP_DIR = ROOT / "experiments/p11_2a_riceseg_smoke"
REPORT_PATH = PROJECT_ROOT / "reports/p11_2b_dependency_gate_and_smoke_rerun_plan.md"
GATE_JSON = EXP_DIR / "p11_2b_dependency_gate.json"

SAFETY = {
    "experimental": True,
    "smoke_only": True,
    "not_for_production": True,
    "probability_claim": False,
    "backend_main_chain_integration": False,
    "risk_fusion_ml_training": False,
    "prescription_or_dosage": False,
    "dependency_install_performed": False,
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


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def nvidia_smi() -> dict[str, Any]:
    try:
        proc = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return {"available": False, "error": f"{exc.__class__.__name__}: {exc}"}
    return {
        "available": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "returncode": proc.returncode,
    }


def build_gate() -> dict[str, Any]:
    deps = {name: has_module(name) for name in ["torch", "torchvision", "numpy", "PIL", "cv2"]}
    missing_required = [name for name in ["torch", "torchvision"] if not deps[name]]
    split_manifest = load_json(EXP_DIR / "split_manifest.json")
    metrics = load_json(EXP_DIR / "metrics_smoke.json")
    gate_status = "BLOCKED_BY_DEPENDENCY" if missing_required else "READY_TO_RERUN_P11_2A_SMOKE_TRAINING"
    return {
        "generated_at": now(),
        "gate_status": gate_status,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependencies": deps,
        "missing_required_dependencies": missing_required,
        "nvidia_smi": nvidia_smi(),
        "p11_2a_status": {
            "split_counts": split_manifest.get("split_counts"),
            "pairing_all_passed": split_manifest.get("pairing_all_passed"),
            "cross_split_leakage_key_count": split_manifest.get("cross_split_leakage_key_count"),
            "training_status": metrics.get("status"),
            "weights_generated": metrics.get("weights_generated"),
        },
        "recommended_install_options_not_executed": {
            "cpu_only": "python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu",
            "gpu_cuda": "Choose the project-approved CUDA wheel from https://pytorch.org/get-started/locally/ after checking nvidia-smi.",
            "conda_cpu": "conda install pytorch torchvision cpuonly -c pytorch",
        },
        "rerun_after_dependency_ready": [
            "python scripts/p11_2a_train_riceseg_smoke.py",
            "python scripts/p11_2a_validate_riceseg_smoke.py",
            "python scripts/p11_2a_infer_riceseg_smoke.py",
        ],
        "allowed_next_step": "Install dependencies only after explicit approval, then rerun P11-2A 1-epoch smoke training.",
        "not_allowed": [
            "backend main-chain integration",
            "risk_fusion ML training",
            "formal model performance claim",
            "formal disease probability claim",
            "prescription or dosage output",
        ],
        "safety": SAFETY,
    }


def write_report(gate: dict[str, Any]) -> None:
    deps = gate["dependencies"]
    p11 = gate["p11_2a_status"]
    lines = [
        "# P11-2B Dependency Gate And Smoke Rerun Plan",
        "",
        f"Generated at: {gate['generated_at']}",
        "",
        "## Conclusion",
        "",
        f"- Gate status: `{gate['gate_status']}`",
        "- dependency_install_performed=false",
        "- experimental=true",
        "- smoke_only=true",
        "- not_for_production=true",
        "- probability_claim=false",
        "- Backend main-chain integration: `NO`",
        "- risk_fusion ML training: `NO`",
        "- Prescription or dosage output: `NO`",
        "",
        "## Current Environment",
        "",
        f"- Python executable: `{gate['python_executable']}`",
        f"- Platform: `{gate['platform']}`",
        f"- Dependency status: `{deps}`",
        f"- Missing required dependencies: `{gate['missing_required_dependencies']}`",
        f"- NVIDIA check: `{gate['nvidia_smi']}`",
        "",
        "## P11-2A Carryover",
        "",
        f"- Split counts: `{p11.get('split_counts')}`",
        f"- Pairing all passed: `{p11.get('pairing_all_passed')}`",
        f"- Cross-split leakage key count: `{p11.get('cross_split_leakage_key_count')}`",
        f"- Training status: `{p11.get('training_status')}`",
        f"- Weights generated: `{p11.get('weights_generated')}`",
        "",
        "## Install Options Not Executed",
        "",
        f"- CPU-only pip: `{gate['recommended_install_options_not_executed']['cpu_only']}`",
        f"- Conda CPU: `{gate['recommended_install_options_not_executed']['conda_cpu']}`",
        "- GPU/CUDA: choose a project-approved PyTorch CUDA wheel only after checking driver/CUDA compatibility.",
        "",
        "## Rerun Commands After Approval",
        "",
        "```powershell",
        "cd <project_root>/ai_model_training",
        "python scripts/p11_2a_train_riceseg_smoke.py",
        "python scripts/p11_2a_validate_riceseg_smoke.py",
        "python scripts/p11_2a_infer_riceseg_smoke.py",
        "```",
        "",
        "## Boundary",
        "",
        "P11-2B is limited to dependency readiness and rerunning the same P11-2A smoke baseline. It must not connect the model to backend routes, must not enter risk_fusion ML, must not claim formal disease probability or formal model accuracy, and must not produce prescription or dosage advice.",
    ]
    atomic_write_text(REPORT_PATH, "\n".join(lines) + "\n")


def main() -> None:
    gate = build_gate()
    atomic_write_json(GATE_JSON, gate)
    write_report(gate)
    print(json.dumps(gate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
