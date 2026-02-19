# Experimental Test Matrix - Predicted DO2 Outlet

Date prepared: 2026-02-17
Status: Draft for lab execution

## Purpose
Prepare a fixed test matrix with current-model predicted outlet dissolved oxygen (`DO2_out [%]`) for later comparison against measured data.

## Scope and Fixed Assumptions
- Model build: current repository state on 2026-02-17.
- Transfer model: `Permeability`.
- Gas-liquid model: `Segmented depletion` (`n_segments = 160`).
- Gas composition: `O2 = 100%`, `N2 = 0%`.
- Inlet condition: `DO2_in = 0%`.
- Inlet `N2 = 0%` (air-reference basis).
- Temperature: `37 C`.
- Geometry: `tube_id = 3.2 mm`, `tube_od = 4.76 mm`, `shell_id = 5.0 mm`, `tube_length = 160 cm`.
- Permeability inputs: `O2 = 600 Barrer`, `N2 = 300 Barrer` (converted internally).
- Gas-flow constraint for this matrix: `1 to 20 mL/min`.
- Perfusion-flow setpoints for this matrix: `1, 5, 10, 20 mL/min`.
- Pressure mode for this matrix: `Conservative curve`, with:
  - `delta_p_mbar = 4.0 * gas_flow_ml_min`
  - `p_total_kpa = 101.325 + 0.1 * delta_p_mbar`
- Pump setting labels (`P1..P4`) are placeholders; map them to your real pump RPM/% in the lab sheet.

## Test Matrix (Predictions + Measurement Fields)

| Test ID | Perfusion flow [mL/min] | Gas flow [mL/min] | Predicted delta p [mbar] | Predicted p_total [kPa] | Predicted DO2_out [%] | Measured DO2_in [%] | Measured p_in [mbar] | Measured p_total [kPa] | Measured DO2_out [%] | Error (Measured - Pred) [%] | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| TM-01 | 1.0 | 1 | 4.0 | 101.725 | 478.070 |  |  |  |  |  |  |
| TM-02 | 5.0 | 1 | 4.0 | 101.725 | 476.594 |  |  |  |  |  |  |
| TM-03 | 10.0 | 1 | 4.0 | 101.725 | 451.505 |  |  |  |  |  |  |
| TM-04 | 20.0 | 1 | 4.0 | 101.725 | 365.375 |  |  |  |  |  |  |
| TM-05 | 1.0 | 5 | 20.0 | 103.325 | 485.590 |  |  |  |  |  |  |
| TM-06 | 5.0 | 5 | 20.0 | 103.325 | 484.090 |  |  |  |  |  |  |
| TM-07 | 10.0 | 5 | 20.0 | 103.325 | 458.606 |  |  |  |  |  |  |
| TM-08 | 20.0 | 5 | 20.0 | 103.325 | 371.122 |  |  |  |  |  |  |
| TM-09 | 1.0 | 10 | 40.0 | 105.325 | 494.989 |  |  |  |  |  |  |
| TM-10 | 5.0 | 10 | 40.0 | 105.325 | 493.461 |  |  |  |  |  |  |
| TM-11 | 10.0 | 10 | 40.0 | 105.325 | 467.483 |  |  |  |  |  |  |
| TM-12 | 20.0 | 10 | 40.0 | 105.325 | 378.306 |  |  |  |  |  |  |
| TM-13 | 1.0 | 20 | 80.0 | 109.325 | 513.788 |  |  |  |  |  |  |
| TM-14 | 5.0 | 20 | 80.0 | 109.325 | 512.201 |  |  |  |  |  |  |
| TM-15 | 10.0 | 20 | 80.0 | 109.325 | 485.237 |  |  |  |  |  |  |
| TM-16 | 20.0 | 20 | 80.0 | 109.325 | 392.673 |  |  |  |  |  |  |

## Data Capture Guidance
- Measure and log actual pressure for each run, even though predicted pressure is listed.
- Measure `DO2_in` at experiment start for each run.
- Run at least duplicate repeats per condition for reproducibility.
- Keep sensor calibration and timestamp metadata with each run.
