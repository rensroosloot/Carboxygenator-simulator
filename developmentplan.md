# Development Plan - CarboxySim MVP

## 1. Objective
Implement and verify a research-first simulation GUI for O2/N2 transfer into PBS, fully traceable to URS/DS/FS.

## 2. Work Breakdown (V-model aligned)
1. Phase A: Finalize specs
- Create `docs/URS.md`, `docs/DS.md`, `docs/FS.md`.
- Add URS<->FS traceability table.
- Exit criteria: spec review complete.

2. Phase B: Core implementation
- Implement input schema + validator.
- Implement solubility abstraction and baseline constants source.
- Implement Euler solver and result packaging.
- Exit criteria: core runs synthetic baseline scenario.

3. Phase C: UI implementation
- Streamlit controls with units and validation messaging.
- Timeseries plots and summary panel.
- CSV/JSON export actions.
- Exit criteria: user can configure/run/export in one flow.

4. Phase D: Verification
- Unit tests for validators and equations.
- Integration tests for end-to-end simulation.
- UI smoke test for run-render loop.
- Exit criteria: all tests pass; AC-001..AC-007 satisfied.

5. Phase E: Documentation hardening
- Add assumptions/limitations section in UI and README.
- Add reproducibility notes and known model limitations.
- Exit criteria: onboarding-ready docs for research users.

## 3. Public API/Interface Additions
- `SimulationInputs` and `SimulationOutputs` data types.
- Core entrypoint: `simulate(inputs, solubility_model)`.
- UI contract: form input -> validated `SimulationInputs` -> `SimulationOutputs`.
- Export contract: deterministic CSV schema and JSON metadata schema.

## 4. Test Plan
Unit:
- validation boundaries
- equation correctness for `dC/dt`
- equilibrium computation consistency

Integration:
- full run with baseline synthetic scenario
- timestep refinement check
- export file structure and content checks

UI smoke:
- load app
- submit valid scenario
- render 2 line plots
- trigger exports without crash

## 5. Risks and Mitigations
- Risk: uncertain solubility constants by temperature.
- Mitigation: centralize constants and cite source in metadata.

- Risk: Euler instability with large `dt`.
- Mitigation: add warning when `dt * max(kLa) > 0.2`.

- Risk: unit confusion.
- Mitigation: display units on every input/output field and export header.

## 6. Definition of Done
- Specs approved and committed.
- Core + UI implemented per FS.
- AC-001..AC-007 automated in tests.
- Deterministic outputs verified.
- Documentation complete for research use.

## 7. Assumptions and Defaults
- Defaults chosen:
  - Streamlit UI
  - Explicit Euler solver
  - Constant gas composition and pressure
  - No CO2/reactive terms in MVP
- If solubility-source preference is not provided, implementer uses a single documented source and tags it in metadata as `solubility_source`.

## Implementation Notes For Next Turn
When Plan Mode is exited, implement in this order:
1. Create the four docs exactly as above.
2. Add a traceability matrix appendix in `docs/FS.md` mapping `UR-001..UR-010` to `AC-001..AC-007`.
3. Open a minimal repo structure skeleton (`core/`, `ui/`, `tests/`) only after doc files are in place.
