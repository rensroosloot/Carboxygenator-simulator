# Risk Assessment

## 1. Document Control
- Version: `0.1`
- Date: `2026-02-16`
- Status: Draft
- Owner: Research/Engineering

## 2. Risk Scoring Method
- Severity: `Low/Medium/High`
- Probability: `Low/Medium/High`
- Detectability: `Low/Medium/High`
- Overall risk: `Low/Medium/High` based on team-defined matrix.

## 3. Risk Register
| Risk ID | Requirement ID | Description | Severity | Probability | Detectability | Overall | Control/Mitigation | Verification Evidence |
|---|---|---|---|---|---|---|---|---|
| R-001 | UR-001 | Invalid gas fraction sum produces incorrect physics | High | Medium | High | High | Strict input validation and rejection | Test case ID |
| R-002 | UR-005 | Time step too large causes unstable/inaccurate integration | High | Medium | Medium | High | Timestep guidance and consistency checks | Test case ID |
| R-003 | UR-008 | Export mismatch between displayed and saved data | Medium | Low | High | Medium | Deterministic export tests | Test case ID |
| R-004 | UR-013 | CO2/pH extension misuse (invalid bicarbonate/CO2 assumptions) could mislead interpretation of pH trends | High | Medium | Medium | High | Explicit assumptions in UI, parameter validation, and equation-level tests for trend direction | TC-CO2-001, TC-CO2-002 |
| R-005 | UR-013 | CO2 transfer mis-parameterization if permeability basis is inconsistent with selected model/unit | Medium | Medium | Medium | Medium | Explicit CO2 transfer-model selector, unit-labeled inputs, and validation tests for permeability-mode path | TC-CO2-003 |

## 4. Residual Risks
- `TBD`

## 5. Review and Approval
- Reviewed by: `TBD`
- Approved by: `TBD`
