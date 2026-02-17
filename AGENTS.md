# AGENTS.md

## Purpose
This repository is for a research simulation tool that models and visualizes the addition of O2/N2 into PBS in a carboxygenator context.

Primary goal: scientific correctness and traceability.
Secondary goal: UI polish. Prefer function over form.

## Product Scope (Current)
- Medium: PBS (well-mixed liquid phase).
- Gas species: O2 and N2.
- Model type: 0D, time-based, well-mixed.
- Input profile: constant (adjustable) gas composition/flow and process settings.
- Output: predicted time evolution and outlet values for dissolved O2/N2.

Future optional scope:
- Add CO2 as an optional third species without breaking O2/N2 workflows.

## Engineering Process (V-Model)
All work follows the V-model. No implementation without upstream specs.
Software development quality framework: GAMP5.

## GAMP5 and Change Control
- Development and verification activities must follow GAMP5 principles for scientific software.
- Requirements, design, implementation, testing, and release evidence must be traceable.
- Keep a project changelog and update it for every meaningful change.
- Changelog should capture at minimum: date, version/tag (if available), summary of change, and rationale/impact.

Changelog artifact:
- `CHANGELOG.md`

## GAMP5 Execution Rules (Mandatory)
1. Software Classification
- Classify the application under GAMP5 before implementation starts.
- Record and maintain classification in `docs/validation/ValidationPlan.md`.

2. Risk-Based Validation
- Assign risk level (`High`, `Medium`, `Low`) to each requirement.
- High-risk requirements require stricter test depth and explicit evidence links.
- Record and maintain risks in `docs/validation/RiskAssessment.md`.

3. Required Validation Artifacts
- `docs/validation/ValidationPlan.md`
- `docs/validation/RiskAssessment.md`
- `docs/validation/RTM.md`
- `docs/validation/TestProtocol.md`
- `docs/validation/TestReport.md`
- `CHANGELOG.md`

4. Traceability Rule
- No implementation task is complete without `URS -> FS -> Test Case -> Test Result` traceability.
- `docs/validation/RTM.md` must be updated in the same change as requirement or test changes.

5. Change Control Rule
- Every meaningful change must update `CHANGELOG.md`.
- Changelog entries must include: date, version/tag (if any), changed items, reason, impact, and verification evidence reference.
- Model-impacting or breaking changes must include a validation impact assessment note.

6. Release Gate
- No release unless planned tests pass, deviations are documented, and RTM has no open traceability gaps.

### 1. URS (User Requirements Specification)
Define what users need, not how to implement.

Minimum URS items:
- Research user can set constant adjustable inputs (gas fractions, flow, pressure, temperature, volume, transfer parameters).
- User can run time-domain simulation and inspect O2/N2 concentration trajectories.
- User can view/export key outputs and simulation metadata.
- Tool is reproducible: same inputs produce same outputs.
- Tool surfaces assumptions and units clearly.

URS output artifact:
- `docs/URS.md`

### 2. DS (Design Specification)
Translate URS into architecture and model structure.

Minimum DS items:
- Module boundaries (core model, parameter validation, solver, plotting/UI, persistence/export).
- Data model for inputs/outputs with units.
- Numerical method and time stepping strategy.
- Error handling and parameter constraints.
- Extension points for optional CO2.

DS output artifact:
- `docs/DS.md`

### 3. FS (Functional Specification)
Define concrete behaviors and acceptance criteria per function.

Minimum FS items:
- Function contracts (inputs, outputs, units, valid ranges, exceptions).
- Equation set for O2/N2 transfer in well-mixed PBS.
- Initial conditions and boundary assumptions.
- Expected plots and computed summary metrics.
- Acceptance scenarios with expected outcomes/tolerances.

FS output artifact:
- `docs/FS.md`

### 4. Implementation
Implement only FS-approved functions.

Implementation rules:
- Keep simulation core independent from UI.
- Keep units explicit at all interfaces.
- Prefer deterministic and testable pure functions in core physics.
- Document assumptions inline where non-obvious.

### 5. Verification and Validation
Right side of V-model must map to left side:
- Unit/function tests verify FS.
- Integration tests verify DS behavior across modules.
- User-facing scenario tests verify URS workflows.

No feature is complete without tests.

## Testing Policy (Mandatory)
- Add tests for every new or changed function in simulation core.
- Test nominal, edge, and invalid-input behavior.
- Include numerical tolerance checks for floating-point outputs.
- Add regression tests for previously fixed bugs.
- Keep test names descriptive and linked to FS requirements.

Minimum expected test categories:
- Parameter validation tests.
- O2/N2 transfer equation tests.
- Time-step integration stability/consistency tests.
- Output schema/units tests.
- UI-level smoke test for running a simulation and rendering plots.

## Scientific and UX Constraints
- Always show units for all inputs/outputs.
- Always expose model assumptions in UI or accompanying docs.
- Avoid hidden auto-corrections of invalid inputs; show clear validation errors.
- Prioritize readable scientific plots over visual styling.
- Keep UI simple and fast for iterative research use.

## Definition of Done
A change is done only when:
1. URS/DS/FS are updated if behavior changed.
2. Code implements the approved FS behavior.
3. Tests are added/updated and pass.
4. Assumptions, units, and limitations are documented.
5. UI allows a user to run and inspect the target simulation flow.

## Out of Scope (for now)
- Full CFD.
- Non-well-mixed spatial models.
- Multi-phase chemistry beyond O2/N2 (unless explicitly planned).
