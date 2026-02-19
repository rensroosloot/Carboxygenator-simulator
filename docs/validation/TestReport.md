# Test Report

## 1. Document Control
- Version: `0.1`
- Date: `2026-02-16`
- Status: Draft
- Owner: Research/Engineering

## 2. Execution Summary
- Protocol version: `0.1`
- Execution date(s): `2026-02-16`
- Environment: `Python (local), pytest via python -m pytest`
- Overall result: `Expanded partial execution complete`

## 3. Results by Test Case
| Test Result ID | Test Case ID | Result (Pass/Fail) | Evidence Reference | Notes |
|---|---|---|---|---|
| TR-001 | TC-VAL-001 | Pass | `python -m pytest -q` (6 passed) | Fraction sum validation behavior verified |
| TR-002 | TC-MOD-001 | Pass | `python -m pytest -q` (15 passed) | Outlet concentration bounded between inlet and equilibrium values |
| TR-003 | TC-MOD-002 | Pass | `python -m pytest -q` (15 passed) | `kLa=0` keeps outlet equal to inlet |
| TR-005 | TC-SOL-001 | Pass | `python -m pytest -q` (15 passed) | Timestep refinement stays within 1% |
| TR-006 | TC-INT-001 | Pass | `python -m pytest -q` (15 passed) | Repeated runs return identical arrays |
| TR-008 | TC-EXP-001 | Pass | `python -m pytest -q` (15 passed) | CSV row count matches steps and metadata JSON contains full input set |
| TR-010 | TC-REP-001 | Pass | `python -m pytest -q` (15 passed) | Reproducibility confirmed |
| TR-011 | TC-FLOW-001 | Pass | `python -m pytest -q` (15 passed) | Lower flow increases transfer toward equilibrium |
| TR-012 | TC-PERM-001 | Pass | `python -m pytest -q` (19 passed) | Permeability mode boundary and sensitivity behavior verified |
| TR-013 | TC-GAS-001 | Pass | `python -m pytest -q` (21 passed) | Low gas flow caps O2 transfer relative to high-gas-flow case |
| TR-014 | TC-SEG-001 | Pass | `python -m pytest -q` (23 passed) | Segmented depletion mode produces lower/equal O2 outlet than lumped under low gas flow |
| TR-015 | TC-PRES-001 | TBD | TBD | Pressure-mode mapping verification pending |
| TR-016 | TC-CO2-001 | Pass | `python -m pytest -q` (30 passed) | Optional two-stage CO2 model shows upstream conditioning and downstream stripping behavior |
| TR-017 | TC-CO2-002 | Pass | `python -m pytest -q` (30 passed) | Bicarbonate pH estimate decreases as dissolved CO2 increases |
| TR-018 | TC-CO2-003 | Pass | `python -m pytest -q` (32 passed) | CO2 permeability mode path validated with positive derived effective transfer coefficient |
| TR-019 | TC-CO2-004 | Pass | `python -m pytest -q` (33 passed) | Reverse stage order changes final CO2 result versus default stage order |

## 4. Deviations
| Deviation ID | Description | Impact | Resolution | Approved By |
|---|---|---|---|---|
| None | N/A | N/A | N/A | N/A |

## 5. Conclusion
- Validation status: `In progress`
- Open actions: `Execute UI smoke tests for the updated single-pass tubing workflow.`
