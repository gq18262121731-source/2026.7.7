# Text-to-CAD Skill Trial Report

Generated at: 2026-07-06

## Summary

- Installed Codex skill: `cad` from `earthtojake/text-to-cad`, path `skills/cad`.
- Trial model: `p11_experimental_smoke_module`, a conceptual CAD token for the P11 experimental smoke pipeline.
- Output scope: visual CAD module only; not a production part, not a backend component, and not a model artifact.

## Files

- Source: `ai_model_training/experiments/p11_2b_cad_skill_trial/p11_experimental_smoke_module.py`
- STEP: `ai_model_training/experiments/p11_2b_cad_skill_trial/p11_experimental_smoke_module.step`
- Snapshot: `ai_model_training/experiments/p11_2b_cad_skill_trial/snapshots/p11_experimental_smoke_module_iso_20260706T004125Z.png`
- CAD runtime venv: `ai_model_training/experiments/p11_2b_cad_skill_trial/.venv_cad/`

## Validation

- STEP generation: PASS via CAD skill `scripts/step`.
- Inspect refs/facts/planes/positioning: PASS.
- Reported bounding box: `160.0 x 86.0 x 27.0 mm`.
- Snapshot generation: PASS.
- Visual review: PASS; generated PNG is nonblank and shows the intended base plate, four flow blocks, training-gate bridge, and corner holes.

## Runtime Notes

- The newly installed `cad` skill will be automatically discoverable after restarting Codex.
- A first attempt with the global Anaconda Python installed `build123d` and upgraded some Anaconda packages (`numpy`, `scipy`, `ipython`), and pip reported possible compatibility conflicts with Spyder/numba. The successful CAD run used an isolated `.venv_cad` under the experiment directory instead.
- The isolated CAD venv needed a local build123d font-scan skip patch because one Windows system font was not parseable by `fontTools`.

## Boundary

This trial did not modify backend business logic, `.env`, model weights, risk_fusion ML, disease probability wording, prescriptions, or dosage advice.
