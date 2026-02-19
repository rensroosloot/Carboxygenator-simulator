# CarboxySim 0.1.0

CarboxySim is a research-focused Streamlit simulator for oxygen/nitrogen transfer into PBS in a carboxygenator-like single-pass tubing setup.

The tool is intended for engineering exploration, scenario comparison, and pre-lab reasoning.

## 1. What The App Does

CarboxySim simulates:

- single-pass dissolved gas transfer (O2/N2) through tubing
- optional upstream CO2-conditioning section for bicarbonate pH control
- optional stage-order reversal (DO section first, then pH section)
- startup transport delay from total loop hold-up volume
- gas-side O2 supply limitation
- optional axial gas depletion (segmented counterflow model)
- pressure effects (manual or gas-flow-derived)
- source-vessel recirculation dynamics (perfect-mixing approximation)
- perfusion recommendation from cell oxygen demand

It provides:

- interactive plots
- sweep analysis
- summary metrics
- exports: Excel, JSON, and PDF report

## 2. Core Modeling Assumptions

The 0.1.0 model assumes:

- liquid phase is non-reactive PBS (no cellular uptake inside transfer core model)
- gas composition and pressure are constant during one run input state
- transfer can be represented by either:
  - direct `kLa`
  - permeability-derived effective transfer coefficient
- source vessel is perfectly mixed for recirculation estimate
- optional pH estimate follows Henderson-Hasselbalch with fixed bicarbonate concentration
- startup delay is governed by:
  - `transport_delay = total_hold_up_volume / perfusion_speed`

Important:

- this is an engineering approximation tool, not a validated clinical/dosing model
- parameters (especially permeability/kLa) should be calibrated to your setup data

## 3. Model Modes

### 3.1 Transfer Model

- `kLa`
  - user enters `kla_o2_s_inv` and `kla_n2_s_inv`
- `Permeability`
  - user enters material permeability (Barrer or SI-like units)
  - app derives effective transfer from tube geometry + solubility

### 3.2 Gas-Liquid Coupling

- `Lumped`
  - one gas composition for whole exchanger
- `Segmented depletion`
  - tubing divided into `n_segments`
  - gas composition updated segment-by-segment (counterflow effect)

### 3.3 CO2 Transfer Model (pH Stage)

- `Permeability` (default)
  - user can enter `perm_co2` in `Barrer` or `mmol*m/(m2*s*kPa)`
  - app derives effective CO2 transfer from geometry + solubility
- `kLa`
  - user enters `kla_co2_s_inv` directly
### 3.4 Pressure Model

- `Manual`
  - user sets `p_total_kpa`
- `Conservative curve`
  - `dP_mbar = 4.0 * gas_flow_ml_min`
- `Optimistic curve`
  - `dP_mbar = 6.4 * gas_flow_ml_min`

with:

- `p_total_kpa = p_atm_kpa + 0.1 * dP_mbar`

## 4. Main Inputs

The UI includes:

- gas composition:
  - `O2 [%]` (N2 is auto-computed to 100%)
- operating conditions:
  - gas flow
  - perfusion speed
  - temperature
  - pressure model / atmosphere
- liquid path geometry:
  - tube ID/OD
  - shell ID
  - tube length
  - total hold-up volume
- transfer settings:
  - kLa or permeability inputs
  - segmented/lumped selection
- initialization:
  - inlet DO2%
  - inlet N2%
  - inlet pH (converted internally to dissolved CO2 via bicarbonate relation)
  - target source DO2%
- simulation horizon:
  - `t_end_min`
  - `dt_min`
- cell demand:
  - `total_cells`
  - `q_o2_cell [x1e-17 mol/cell/s]`
  - demand margin factor

## 5. Main Outputs

- segmented counterflow visualization (when segmented mode is active)
- one-row segmented CO2+pH and O2 visualization with selectable stage order
- source vessel target panel:
  - start DO2
  - target DO2
  - estimated time to target
  - status
- source vessel DO2 vs time plot
- source vessel pH vs time plot (when CO2/pH workflow is enabled)
- flow sweep:
  - outlet DO%
  - O2 throughput / net O2 added
- cell-demand perfusion recommendation
- summary metrics:
  - transfer residence time
  - transport delay
  - effective transfer coefficients
  - O2 supply / limitation status

## 6. Cell Demand Recommendation Logic

The app computes oxygen demand from:

- `N_cells`
- average cellular oxygen uptake `q_O2_cell`

Formula:

- `O2_demand_mmol_min = N_cells * q_O2_cell(mol/cell/s) * 60 * 1000 * margin`

Then it scans flow sweep results and returns the first perfusion flow where:

- `o2_net_added_mmol_min >= O2_demand_mmol_min`

If not found, app reports demand is not met within the current sweep range.

## 7. Exports

Available in-app downloads:

- `Timeseries Excel` (`.xlsx`)
- `Source Vessel Excel` (`.xlsx`)
- `Metadata JSON` (`.json`)
- `PDF Report` (`.pdf`)

PDF report includes:

- key graphs first
- assumptions
- detailed settings with explanation
- run summary
- flow sweep data table

If Excel/PDF dependencies are unavailable in deployment environment, app falls back with safe warnings (and CSV fallback for Excel).

## 8. Repository Structure

- `streamlit_app.py` - Streamlit Cloud entrypoint
- `ui/app.py` - UI and reporting/export logic
- `core/params.py` - input schema and validation
- `core/model.py` - physics/helper equations
- `core/solver.py` - simulation routines
- `core/results.py` - output data structures + export helpers
- `tests/` - unit and integration tests
- `docs/` - URS/DS/FS and validation artifacts

## 9. Local Setup

From repository root (project-local virtual environment):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install streamlit numpy pandas altair openpyxl reportlab xlsxwriter pytest
```

Run:

```powershell
python -m streamlit run ui/app.py
```

Windows helper:

```powershell
.\start_app.bat
```

After startup, open the URL shown in terminal (commonly `http://localhost:8501` or `http://localhost:8502` if 8501 is occupied).

## 10. Testing

```powershell
python -m pytest -q
```

## 11. Streamlit Cloud Deployment

Use:

- Repository: `rensroosloot/Carboxygenator-simulator`
- Branch: `main`
- Main file path: `streamlit_app.py`

## 12. Versioning

Current release:

- `0.1.0` (research MVP with reporting, segmented analysis, source-vessel dynamics, and demand-based perfusion recommendation)

## 13. Documentation Links

- User Requirements: `docs/URS.md`
- Design Specification: `docs/DS.md`
- Functional Specification: `docs/FS.md`
- Validation artifacts: `docs/validation/`
- Change history: `CHANGELOG.md`
