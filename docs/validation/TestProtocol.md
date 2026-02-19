# Test Protocol

## 1. Document Control
- Version: `0.1`
- Date: `2026-02-16`
- Status: Draft
- Owner: Research/Engineering

## 2. Preconditions
- URS/DS/FS approved baseline.
- Test environment and toolchain documented.
- Input datasets/constants versioned.

## 3. Test Cases
| Test Case ID | Objective | Related URS | Related FS/AC | Method | Acceptance Criteria |
|---|---|---|---|---|---|
| TC-VAL-001 | Reject invalid gas fraction sums | UR-001, UR-009 | AC-004 | Unit test | Invalid values raise `ValueError` |
| TC-MOD-001 | Verify equilibrium direction behavior | UR-002, UR-007 | AC-002, AC-003 | Unit/integration | Outlet concentration remains bounded between inlet and `C*` |
| TC-MOD-002 | Verify `kLa=0` behavior | UR-003 | AC-001 | Unit test | Outlet concentration remains equal to inlet |
| TC-SOL-001 | Verify timestep consistency | UR-005 | AC-005 | Integration test | Final values differ <1% when halving `dt` |
| TC-INT-001 | Verify deterministic repeatability | UR-006, UR-010 | AC-006 | Integration test | Identical outputs across repeated runs |
| TC-EXP-001 | Verify export integrity | UR-008 | AC-007 | Integration test | Row count and metadata completeness correct |
| TC-FLOW-001 | Verify flow/residence transfer effect | UR-003, UR-003a | AC-008 | Unit/integration | Lower flow yields outlet concentration closer to `C*` |
| TC-PERM-001 | Verify permeability-mode boundary and sensitivity | UR-003, UR-003a | AC-009 | Unit/integration | Zero permeability keeps inlet unchanged; higher permeability increases transfer |
| TC-GAS-001 | Verify gas-side O2 supply limitation | UR-003b | AC-010 | Unit/integration | Lower gas flow caps O2 transfer compared with unrestricted case |
| TC-SEG-001 | Verify segmented depletion behavior | UR-003c | AC-011 | Unit/integration | Segmented mode yields equal or lower O2 outlet than lumped under low gas flow |
| TC-PRES-001 | Verify pressure-mode mapping from gas flow | UR-003d | AC-002, AC-003, AC-010 | Unit/UI | Conservative/optimistic pressure curves produce expected `p_total_kpa` values |
| TC-CO2-001 | Verify two-stage CO2 conditioning then stripping behavior | UR-013 | AC-015 | Unit/integration | Stage-1 can increase CO2 and stage-2 can reduce it under zero-CO2 downstream gas assumption |
| TC-CO2-002 | Verify bicarbonate pH trend versus dissolved CO2 | UR-013 | AC-016 | Unit test | Higher dissolved CO2 yields lower predicted pH for fixed bicarbonate |
| TC-CO2-003 | Verify CO2 permeability-mode parameterization path | UR-013 | AC-017 | Unit test | CO2 permeability input is validated and yields positive effective `k_eff,CO2` |
| TC-CO2-004 | Verify reverse stage-order behavior in CO2 path | UR-013 | AC-018 | Unit test | Enabling reverse-order changes final CO2 outcome versus default stage order |

## 4. Test Data
- Baseline synthetic scenario from `docs/FS.md` Section 7.

## 5. Deviations Handling
- Any deviation requires:
  - deviation ID
  - description
  - impact assessment
  - resolution and approval
