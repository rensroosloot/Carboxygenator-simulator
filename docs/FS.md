# Functional Specification (FS) - CarboxySim MVP

## 1. Document Control
- Version: `0.1.0`
- Date: `2026-02-17`
- Status: Released

## 2. Physical Assumptions
- Single-pass liquid flow through carboxygenator tubing.
- Constant gas composition and total pressure.
- Constant temperature.
- No reactions/consumption in PBS.
- Transfer may be represented either by direct `kLa_i` or by tubing permeability-derived effective `k_eff,i`.
- Optional pH estimate uses a bicarbonate-buffer approximation with fixed `[HCO3-]` and `pKa`.

## 3. Equations
For each species `i in {O2, N2}`:
1. `p_i = y_i * P_total`
2. `C_i* = S_i(T) * p_i`
3. `V_tube = pi * (ID/2)^2 * L`
4. `V_annulus = pi * ((D_shell/2)^2 - (OD_tube/2)^2) * L`
5. `tau = V_tube / Q_liq`
6. `n_dot_O2,supply = Q_gas * y_O2 * P/(R*T)`
7. `C_i,out = C_i* + (C_i,in - C_i*) * exp(-kLa_i * tau)`
8. Optional permeability mode (effective transfer):
   - `k_eff,i = ((P_i / delta) * (A/V)) / S_i(T)`
   - `C_i,out = C_i* + (C_i,in - C_i*) * exp(-k_eff,i * tau)`
9. O2 supply cap:
   - `n_dot_O2,required = max(0, (C_O2,out - C_O2,in) * Q_liq)`
   - if `n_dot_O2,required > n_dot_O2,supply`, set `C_O2,out = C_O2,in + n_dot_O2,supply / Q_liq`
10. Optional segmented depletion mode:
   - split tubing into `N` segments.
   - in each segment, update gas composition from transferred O2/N2 before computing next local `C*`.
11. Pressure mode:
   - Manual or flow-derived pressure curve (conservative/optimistic).
12. Transport delay:
   - `tau_transport = V_hold_up / Q_liq`
   - where `V_hold_up` is user-provided total loop hold-up (or tube-volume fallback).
13. Source-vessel perfect-mixing approximation:
   - `dC_vessel/dt = (Q_liq/V_vessel) * (C_return_delayed - C_vessel)`
14. Cell-demand recommendation:
   - `O2_demand_mmol_min = N_cells * q_O2_cell(mol/cell/s) * 60 * 1000 * margin`
   - choose first flow where `o2_net_added_mmol_min >= O2_demand_mmol_min`
15. Optional upstream CO2-conditioning stage and downstream stripping:
   - Stage 1 (CO2 section): `C_CO2,after1 = C*_CO2,1 + (C_CO2,in - C*_CO2,1) * exp(-kLa_CO2 * tau_1)`
   - Stage 2 (O2 section): `C_CO2,out = C*_CO2,2 + (C_CO2,after1 - C*_CO2,2) * exp(-kLa_CO2 * tau_2)`
   - default downstream assumption: `C*_CO2,2 = 0` (no CO2 in O2-section gas feed)
   - optional reverse-order mode: apply Stage 2 first, then Stage 1 (`DO -> pH`)
16. Bicarbonate pH estimate:
   - `pH = pKa_app + log10([HCO3-]/[CO2*])`
17. CO2 transfer parameterization:
   - `co2_transfer_model = kLa` uses direct `kla_co2`.
   - `co2_transfer_model = permeability` derives effective `k_eff,CO2` from `perm_CO2`, geometry, and solubility (same formulation as O2/N2 permeability mode).

Where:
- `C_i,in`, `C_i,out` in `mmol/L`
- `P_total` in `kPa`
- `S_i(T)` in `mmol/(L*kPa)`
- `kLa_i` in `s^-1`
- `P_i` in `mmol*m/(m2*s*kPa)`, `delta` in `m`, `A` in `m2`, `V` in `m3`
- `ID` in `cm`, `OD_tube` in `cm`, `D_shell` in `cm`, `L` in `cm`
- `V_tube` and `V_annulus` in `mL`, `Q_liq` and `Q_gas` in `mL/s`, `tau` in `s`

Initial conditions:
- `C_i,in = C_i_init`

Output interpretation:
- Outlet concentration is measured after tubing residence time.

## 4. Function Contracts
- `validate_inputs(inputs) -> None`
  - Raises `ValueError` on invalid ranges or fraction sum.
- `compute_equilibrium_concentrations(inputs, solubility_model) -> (cstar_o2, cstar_n2)`
- `compute_tube_volume_ml(tube_id_mm, tube_length_cm) -> float`
- `compute_residence_time_s(flow_ml_min, tube_volume_ml) -> float`
- `compute_single_pass_outlet_concentration(c_in_mmol_l, cstar_mmol_l, kla_s_inv, residence_time_s) -> float`
- `compute_effective_kla_from_permeability(species, inputs, solubility_model) -> float`
- `simulate(inputs, solubility_model) -> SimulationOutputs`
- `export_csv(outputs, path) -> None`
- `export_metadata_json(inputs, outputs, path) -> None`
- UI report/export helpers:
  - Excel timeseries and source-vessel trajectory
  - PDF report generation with graphs + explained settings + summary + flow-sweep table

## 5. Units Standard
- Time: `s`
- Pressure: `kPa` absolute
- Temperature input: `C`, converted internally to `K` where needed
- Concentration: `mmol/L`
- Volume: `L`
- Flow: `mL/min`
- Tube ID: `mm`
- Tube length: `cm`
- Tube hold-up volume: `mL`
- Outer shell ID: `mm`
- Gas flow: `mL/min`
- `kLa`: `s^-1`
- Tube OD: `mm`
- Permeability coefficients: `mmol*m/(m2*s*kPa)`

## 6. Acceptance Criteria
- AC-001 (`kLa=0`): concentration remains constant for all `t`.
- AC-002 (equilibrium direction): if `C_i,in <= C_i*`, then `C_i,out` is bounded by `C_i,in <= C_i,out <= C_i*`.
- AC-003 (degassing direction): if `C_i,in > C_i*`, then `C_i,out` is bounded by `C_i* <= C_i,out <= C_i,in`.
- AC-004 (fraction validity): reject `y_o2 + y_n2 != 1` beyond tolerance.
- AC-005 (step consistency): halving `dt` changes final concentrations by <1% for baseline case.
- AC-006 (determinism): repeated identical runs return identical arrays.
- AC-007 (export integrity): CSV rows equal simulation step count; metadata contains full input set.
- AC-008 (flow effect): lower flow (higher residence time) yields `C_i,out` closer to `C_i*`.
- AC-009 (permeability mode): with permeability mode active, `P_i=0` gives `C_i,out = C_i,in`; higher `P_i` increases transfer toward `C_i*`.
- AC-010 (gas supply limit): low gas flow caps O2 transfer, reducing `C_O2,out` versus unrestricted case.
- AC-011 (segmented depletion): at low gas flow and high transfer rates, segmented mode predicts equal or lower `C_O2,out` than lumped mode.
- AC-012 (hold-up delay): increasing total hold-up volume increases startup delay.
- AC-013 (cell-demand recommendation): recommended flow is first sweep point meeting/exceeding demand, else explicit unmet warning.
- AC-014 (report/export): Excel/JSON/PDF exports complete without runtime errors in supported environments.
- AC-015 (CO2 two-stage behavior): optional CO2 stage can increase dissolved CO2 upstream and downstream O2 section can reduce CO2 versus post-stage value.
- AC-016 (buffer pH response): increasing dissolved CO2 with fixed bicarbonate decreases predicted pH.
- AC-017 (CO2 permeability mode): with `co2_transfer_model='permeability'`, CO2 permeability input is required and derived effective `k_eff,CO2` is positive.
- AC-018 (CO2/DO reverse-order mode): when reverse-order is enabled, displayed pH/CO2 stage inlets/outlets follow `DO -> pH` ordering and use upstream stage output as downstream stage input.

## 7. Baseline Synthetic Scenario
Use one canonical test scenario in FS appendix:
- `y_o2=0.21`, `y_n2=0.79`, `P_total=101.325 kPa`
- `T=25 C`, `V=1.0 L`, `Q=10 mL/min`
- `tube_id=3.2 mm`, `tube_length=160 cm`
- `kLa_o2=0.01 s^-1`, `kLa_n2=0.008 s^-1`
- `C_o2_init=0`, `C_n2_init=0`
- `t_end=1800 s`, `dt=1 s`

Expected behavior:
- outlet is piecewise constant with startup delay then converged outlet level
- lower flow produces higher transfer toward `C*`

## Appendix A - URS to FS Traceability Matrix
| URS ID | Requirement Summary | FS Acceptance Criteria Coverage |
|---|---|---|
| UR-001 | Set gas composition (`y_O2`, `y_N2`, sum=1) | AC-004 |
| UR-002 | Set gas-side pressure and liquid temperature | AC-002, AC-003 |
| UR-003 | Set liquid volume and species-specific `kLa` | AC-001, AC-002, AC-003, AC-008 |
| UR-003a | Set flow rate and tubing geometry | AC-005, AC-008 |
| UR-003b | Set outer shell diameter and gas flow for O2 supply limitation | AC-010 |
| UR-003c | Switch between lumped and segmented gas-liquid coupling | AC-011 |
| UR-003d | Select pressure mode (manual/conservative/optimistic) | AC-002, AC-003, AC-010 |
| UR-004 | Set initial dissolved concentrations | AC-002, AC-003 |
| UR-005 | Set simulation horizon and timestep | AC-005 |
| UR-006 | Run simulation and view O2/N2 trajectories | AC-002, AC-003, AC-006 |
| UR-007 | Inspect final/equilibrium-approach values | AC-002, AC-003 |
| UR-008 | Export CSV + JSON metadata | AC-007 |
| UR-009 | Validate invalid inputs with clear errors | AC-004 |
| UR-010 | Reproducible outputs for identical inputs | AC-006 |
| UR-011 | Set total hold-up volume and startup delay behavior | AC-012 |
| UR-012 | Enter cell demand and obtain perfusion recommendation | AC-013 |
| UR-013 | Optional upstream CO2 conditioning and pH/CO2 trend inspection | AC-015, AC-016, AC-017, AC-018 |
