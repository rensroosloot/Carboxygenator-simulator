# User Requirements Specification (URS) - CarboxySim MVP

## 1. Document Control
- Version: `0.1.0`
- Date: `2026-02-17`
- Status: Released
- Owner: Research/Engineering

## 2. Product Goal
A research tool to simulate time-based outlet concentrations of O2 and N2 added to PBS in a carboxygenator-like single-pass tubing setting.

## 3. Intended Users
- Researchers performing exploratory parameter studies.
- Engineers validating expected transfer trends before wet-lab tests.

## 4. In Scope
- Constant, user-adjustable process inputs.
- Time-domain simulation outputs.
- Single-pass tubing residence-time model from source vessel to outlet measurement point.
- Plotting of dissolved O2 and N2 vs time.
- Source-vessel perfect-mixing DO% trajectory and time-to-target estimation.
- Optional upstream CO2/pH-conditioning section with bicarbonate-buffer pH estimate.
- Cell oxygen demand based perfusion recommendation.
- Export of run metadata, Excel datasets, and PDF report.
- Explicit display of assumptions and units.

## 5. Out of Scope (MVP)
- CFD/spatial gradients.
- Closed-loop control.
- Reactive chemistry and hemoglobin models.
- Closed-loop pH control.

## 6. User Requirements
- UR-001: User can set gas composition (`y_O2`, `y_N2`, sum=1).
- UR-002: User can set gas-side pressure and liquid temperature.
- UR-003: User can set liquid volume and species-specific `kLa`.
- UR-003a: User can set flow rate and tubing geometry (`flow_ml_min`, `tube_id_mm`, `tube_length_cm`).
- UR-003b: User can set outer shell diameter and gas flow to model O2 supply limitation.
- UR-003c: User can switch between lumped and segmented gas-liquid coupling to model axial gas depletion.
- UR-003d: User can select pressure mode (manual/conservative/optimistic) to derive total pressure from gas flow.
- UR-004: User can set initial dissolved concentrations.
- UR-005: User can set simulation horizon and timestep.
- UR-006: User can run simulation and see O2/N2 trajectories.
- UR-007: User can inspect final/equilibrium-approach values.
- UR-008: User can export Excel + JSON metadata and a PDF report.
- UR-009: Tool validates invalid inputs with clear error text.
- UR-010: Re-running with identical inputs reproduces identical outputs.
- UR-011: User can set total loop hold-up volume and model startup transport delay.
- UR-012: User can enter total cell number and average O2 uptake to get perfusion recommendation.
- UR-013: User can optionally enable a CO2 conditioning section and inspect predicted dissolved CO2 and pH trends across both pH and O2 sections, with selectable CO2 transfer parameterization (`kLa` or permeability/Barrer) and optional reversed stage order.

## 7. Usability/Performance Requirements
- Run time for standard simulation (`t_end <= 3600 s`, `dt >= 0.1 s`) under 2 s on typical laptop.
- UI feedback on invalid fields in under 200 ms.

## 8. Compliance/Traceability
- Every UR maps to FS acceptance tests and development plan tasks.
