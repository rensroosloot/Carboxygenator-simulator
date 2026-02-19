# Requirements Traceability Matrix (RTM)

## 1. Document Control
- Version: `0.1`
- Date: `2026-02-16`
- Status: Draft
- Owner: Research/Engineering

## 2. Traceability Matrix
| URS ID | FS ID/Section | Test Case ID | Test Result ID | Status | Notes |
|---|---|---|---|---|---|
| UR-001 | AC-004 | TC-VAL-001 | TR-001 | Executed (Pass) | `tests/test_params.py::test_validate_inputs_rejects_fraction_sum_outside_tolerance` |
| UR-002 | FS Section 3 | TC-MOD-001 | TR-002 | Executed (Pass) | `tests/test_solver.py::test_ac002_and_ac003_outlet_between_inlet_and_equilibrium` |
| UR-003 | AC-001, AC-002, AC-003, AC-008, AC-009 | TC-MOD-002, TC-FLOW-001, TC-PERM-001 | TR-003, TR-011, TR-012 | Executed (Pass) | `tests/test_solver.py::test_ac001_kla_zero_keeps_outlet_equal_inlet`, `tests/test_solver.py::test_flow_effect_low_flow_has_more_transfer`, `tests/test_solver.py::test_permeability_mode_higher_permeability_increases_transfer` |
| UR-003a | AC-005, AC-008, AC-009 | TC-SOL-001, TC-FLOW-001, TC-PERM-001 | TR-005, TR-011, TR-012 | Executed (Pass) | `tests/test_solver.py::test_ac005_timestep_consistency_within_one_percent`, `tests/test_solver.py::test_flow_effect_low_flow_has_more_transfer`, `tests/test_solver.py::test_permeability_mode_with_zero_permeability_keeps_inlet` |
| UR-003b | AC-010 | TC-GAS-001 | TR-013 | Executed (Pass) | `tests/test_solver.py::test_o2_gas_supply_limit_caps_outlet_transfer` |
| UR-003c | AC-011 | TC-SEG-001 | TR-014 | Executed (Pass) | `tests/test_solver.py::test_segmented_depletion_limits_o2_more_than_lumped_at_low_gas_flow` |
| UR-003d | AC-002, AC-003, AC-010 | TC-PRES-001 | TR-015 | Planned | Pressure model mapping in UI and derived `p_total_kpa` verification pending |
| UR-004 | AC-002, AC-003 | TC-MOD-001 | TR-002 | Executed (Pass) | `tests/test_solver.py::test_ac002_and_ac003_outlet_between_inlet_and_equilibrium` |
| UR-005 | AC-005 | TC-SOL-001 | TR-005 | Executed (Pass) | `tests/test_solver.py::test_ac005_timestep_consistency_within_one_percent` |
| UR-006 | AC-002, AC-003, AC-006 | TC-INT-001 | TR-006 | Executed (Pass) | `tests/test_solver.py::test_ac006_simulation_is_deterministic` |
| UR-007 | AC-002, AC-003 | TC-MOD-001 | TR-002 | Executed (Pass) | `tests/test_solver.py::test_ac002_and_ac003_outlet_between_inlet_and_equilibrium` |
| UR-008 | AC-007 | TC-EXP-001 | TR-008 | Executed (Pass) | `tests/test_exports.py::test_ac007_export_integrity_csv_and_metadata_json` |
| UR-009 | AC-004 | TC-VAL-001 | TR-001 | Executed (Pass) | `tests/test_params.py::test_validate_inputs_rejects_fraction_sum_outside_tolerance` |
| UR-010 | AC-006 | TC-REP-001 | TR-010 | Executed (Pass) | `tests/test_solver.py::test_ac006_simulation_is_deterministic` |
| UR-013 | AC-015, AC-016, AC-017, AC-018 | TC-CO2-001, TC-CO2-002, TC-CO2-003, TC-CO2-004 | TR-016, TR-017, TR-018, TR-019 | Executed (Pass) | `tests/test_solver.py::test_two_stage_co2_transfer_can_add_then_strip`, `tests/test_solver.py::test_bicarbonate_ph_decreases_when_dissolved_co2_increases`, `tests/test_solver.py::test_effective_kla_from_permeability_supports_co2`, `tests/test_ui_co2_stage_order.py::test_reverse_stage_order_changes_final_co2` |

## 3. Open Gaps
- TR-015 (TC-PRES-001): pressure-mode verification not yet executed.
