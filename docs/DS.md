# Design Specification (DS) - CarboxySim MVP

## 1. Document Control
- Version: `0.1`
- Date: `2026-02-16`
- Status: Draft

## 2. Architecture Overview
Modules:
1. `core/params.py` for schema + validation
2. `core/model.py` for physics equations
3. `core/solver.py` for time integration
4. `core/results.py` for output objects + export helpers
5. `ui/app.py` for Streamlit UI and plotting
6. `tests/` for unit/integration/smoke coverage

## 3. Data Contracts (Public Interfaces)
- `SimulationInputs`
  - `y_o2: float`
  - `y_n2: float`
  - `p_total_kpa: float`
  - `temperature_c: float`
  - `volume_l: float`
  - `flow_ml_min: float`
  - `tube_id_mm: float`
  - `tube_od_mm: float`
  - `shell_id_mm: float`
  - `tube_length_cm: float`
  - `gas_flow_ml_min: float`
  - `kla_o2_s_inv: float`
  - `kla_n2_s_inv: float`
  - `transfer_model: str` (`"kla"` or `"permeability"`)
  - `tube_od_mm_override_mm: float | None` (optional override in permeability mode)
  - `perm_o2_mmol_m_per_m2_s_kpa: float | None` (required in permeability mode)
  - `perm_n2_mmol_m_per_m2_s_kpa: float | None` (required in permeability mode)
  - `gas_liquid_model: str` (`"lumped"` or `"segmented"`)
  - `n_segments: int` (required `>=2` for segmented mode)
  - `c_o2_init_mmol_l: float`
  - `c_n2_init_mmol_l: float`
  - `t_end_s: float`
  - `dt_s: float`
- `SimulationOutputs`
  - `time_s: np.ndarray`
  - `c_o2_mmol_l: np.ndarray`
  - `c_n2_mmol_l: np.ndarray`
  - `cstar_o2_mmol_l: float`
  - `cstar_n2_mmol_l: float`
  - `metadata: dict`

Validation rules:
- Fractions in `[0,1]` and `abs(y_o2 + y_n2 - 1.0) <= 1e-9`
- Positive pressure/volume/timestep/horizon
- Positive flow and positive tubing dimensions
- `tube_od_mm > tube_id_mm` and `shell_id_mm > tube_od_mm`
- In permeability mode: `tube_od_mm > tube_id_mm`, non-negative permeability coefficients
- Non-negative concentrations and `kLa`
- `dt_s <= t_end_s`

## 4. Numerical Method
- Single-pass analytical outlet calculation for each species:
  - `C_out = C* + (C_in - C*) * exp(-k_eff * tau)`
  - `tau = V_tube / Q`
- Gas-side O2 supply constraint:
  - `n_dot_O2,supply = Q_gas * y_O2 * P/(R*T)`
  - if required O2 transfer exceeds `n_dot_O2,supply`, O2 outlet is capped by supply.
- Segmented option:
  - solve transfer over `n_segments` axial sections with gas composition update per segment.
- Pressure mode in UI:
  - `Manual`: user-provided `p_total_kpa`
  - `Conservative curve`: `dP_mbar = 4.0 * Q_gas_ml_min`
  - `Optimistic curve`: `dP_mbar = 6.4 * Q_gas_ml_min`
  - `p_total_kpa = p_atm_kpa + 0.1 * dP_mbar`
- `k_eff` comes from:
  - `kLa` mode: direct user-entered `kLa`
  - permeability mode: effective `k_eff` derived from OD/ID/thickness, permeability, and solubility
- Time vector remains discrete (`n = floor(t_end/dt) + 1`) for visualization/export.
- Deterministic behavior, no adaptive solver in MVP.

## 5. Error Handling
- Raise `ValueError` with field-specific messages from validation layer.
- UI catches and displays human-readable validation errors.

## 6. CO2 Extension Hook
- Keep species logic generic enough to add `species=["O2","N2","CO2"]` later.
- For MVP, expose only O2/N2 UI controls.

## 7. Traceability
- DS module responsibilities map to URS IDs and FS function contracts.
