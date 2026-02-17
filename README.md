# CarboxySim

Research tool for simulating O2/N2 transfer into PBS in a carboxygenator-like single-pass tubing setup.

## What This Tool Does

- Simulates outlet O2/N2 concentration after transfer tubing.
- Shows DO% as primary output (`100% DO` referenced to air at 1 atm).
- Supports two transfer models:
  - `kLa`
  - `Permeability` (derived effective transfer from tubing data)
- Supports two gas-liquid coupling models:
  - `Lumped`
  - `Segmented depletion` (axial gas depletion along tubing)
- Includes gas-side O2 supply limitation based on gas flow.
- Includes selectable pressure modeling:
  - `Manual`
  - `Conservative curve`
  - `Optimistic curve`
- Includes flow sweep plots and export (CSV + JSON metadata).
- Includes segmented counterflow bar visualization with color legend:
  - `0% DO` = white
  - `500% DO` = red

## Project Structure

- `ui/app.py` - Streamlit user interface
- `core/params.py` - input schema and validation
- `core/model.py` - core equations and helper calculations
- `core/solver.py` - simulation execution
- `core/results.py` - output containers and export helpers
- `tests/` - unit and integration tests
- `docs/` - URS/DS/FS and validation artifacts

## Install

From repository root:

```powershell
python -m pip install -e .
```

## Run The App

```powershell
python -m streamlit run ui/app.py
```

If imports fail from your environment, run from repo root and set:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m streamlit run ui/app.py
```

### Quick Start (Windows)

Double-click or run:

```powershell
.\start_app.bat
```

This script:
- switches to repo root
- sets `PYTHONPATH`
- uses `.venv\Scripts\python.exe` if available
- otherwise falls back to `py` or `python`

After startup, open the URL shown in the terminal (usually `http://localhost:8501`) in your browser.

## Test

```powershell
python -m pytest -q
```

## Key Inputs

- Gas composition: `O2 [%]` (N2 auto = 100 - O2)
- Liquid flow: `flow_ml_min`
- Gas flow: `gas_flow_ml_min`
- Geometry:
  - `tube_id_mm`
  - `tube_od_mm`
  - `shell_id_mm`
  - `tube_length_cm`
- Transfer model:
  - `kLa` with `kla_o2_s_inv`, `kla_n2_s_inv`
  - `Permeability` with `perm_o2`, `perm_n2` (+ unit selection)
- Gas-liquid coupling:
  - `Lumped`
  - `Segmented depletion` with `n_segments`
- Pressure model:
  - `Manual` (`p_total_kpa`)
  - `Conservative curve`
  - `Optimistic curve`

## Pressure Curves Used In UI

- Conservative: `dP_mbar = 4.0 * Q_gas_ml_min`
- Optimistic: `dP_mbar = 6.4 * Q_gas_ml_min`
- `p_total_kpa = p_atm_kpa + 0.1 * dP_mbar`

## Important Notes

- This is an MVP research model, not a certified clinical model.
- Current solubility model uses fixed constants (temperature input exists but is not yet fully temperature-coupled).
- Segmented mode is recommended when low gas flow causes noticeable gas depletion effects.
- In segmented mode, the app shows a two-lane color bar:
  - liquid DO% progression (left -> right)
  - gas O2 potential progression (right -> left, counterflow)
- Flow sweep controls update live using the last executed run; model-side input changes require pressing `Run Simulation`.

## Documentation

- Requirements: `docs/URS.md`
- Design: `docs/DS.md`
- Functional spec: `docs/FS.md`
- Validation docs: `docs/validation/`
- Change history: `CHANGELOG.md`
