from dataclasses import replace

import numpy as np

from core.model import (
    compute_equilibrium_concentrations,
    compute_effective_kla_from_permeability,
    compute_residence_time_s,
    compute_single_pass_outlet_concentration,
    compute_tube_volume_ml,
    constant_solubility_model,
)
from core.params import SimulationInputs
from core.solver import compute_single_pass_steady_outlet, simulate


def _baseline_inputs() -> SimulationInputs:
    return SimulationInputs(
        y_o2=0.21,
        y_n2=0.79,
        p_total_kpa=101.325,
        temperature_c=25.0,
        volume_l=1.0,
        flow_ml_min=10.0,
        tube_id_mm=3.2,
        tube_od_mm=4.76,
        shell_id_mm=5.0,
        tube_length_cm=160.0,
        gas_flow_ml_min=100.0,
        kla_o2_s_inv=0.01,
        kla_n2_s_inv=0.008,
        c_o2_init_mmol_l=0.0,
        c_n2_init_mmol_l=0.0,
        t_end_s=1800.0,
        dt_s=1.0,
        transfer_model="kla",
    )


def test_compute_equilibrium_concentrations_positive() -> None:
    inputs = _baseline_inputs()
    cstar_o2, cstar_n2 = compute_equilibrium_concentrations(
        inputs, constant_solubility_model
    )
    assert cstar_o2 > 0.0
    assert cstar_n2 > 0.0


def test_tube_volume_matches_expected_geometry() -> None:
    tube_volume_ml = compute_tube_volume_ml(3.2, 160.0)
    assert abs(tube_volume_ml - 12.868) < 0.01


def test_ac001_kla_zero_keeps_outlet_equal_inlet() -> None:
    inputs = replace(
        _baseline_inputs(),
        kla_o2_s_inv=0.0,
        kla_n2_s_inv=0.0,
        c_o2_init_mmol_l=1.2,
        c_n2_init_mmol_l=0.8,
    )
    outputs = simulate(inputs, constant_solubility_model)
    assert np.allclose(outputs.c_o2_mmol_l, 1.2)
    assert np.allclose(outputs.c_n2_mmol_l, 0.8)


def test_ac002_and_ac003_outlet_between_inlet_and_equilibrium() -> None:
    base = _baseline_inputs()
    cstar_o2, cstar_n2 = compute_equilibrium_concentrations(base, constant_solubility_model)
    residence_s = compute_residence_time_s(
        base.flow_ml_min, compute_tube_volume_ml(base.tube_id_mm, base.tube_length_cm)
    )

    out_o2 = compute_single_pass_outlet_concentration(0.0, cstar_o2, base.kla_o2_s_inv, residence_s)
    assert 0.0 <= out_o2 <= cstar_o2

    out_n2 = compute_single_pass_outlet_concentration(cstar_n2 * 2.0, cstar_n2, base.kla_n2_s_inv, residence_s)
    assert cstar_n2 <= out_n2 <= cstar_n2 * 2.0


def test_flow_effect_low_flow_has_more_transfer() -> None:
    base = _baseline_inputs()
    low_flow = simulate(replace(base, flow_ml_min=2.0), constant_solubility_model)
    high_flow = simulate(replace(base, flow_ml_min=20.0), constant_solubility_model)
    assert low_flow.c_o2_mmol_l[-1] > high_flow.c_o2_mmol_l[-1]
    assert low_flow.c_n2_mmol_l[-1] > high_flow.c_n2_mmol_l[-1]


def test_ac005_timestep_consistency_within_one_percent() -> None:
    coarse = simulate(replace(_baseline_inputs(), dt_s=1.0), constant_solubility_model)
    fine = simulate(replace(_baseline_inputs(), dt_s=0.5), constant_solubility_model)

    rel_o2 = abs(fine.c_o2_mmol_l[-1] - coarse.c_o2_mmol_l[-1]) / max(fine.c_o2_mmol_l[-1], 1e-12)
    rel_n2 = abs(fine.c_n2_mmol_l[-1] - coarse.c_n2_mmol_l[-1]) / max(fine.c_n2_mmol_l[-1], 1e-12)
    assert rel_o2 < 0.01
    assert rel_n2 < 0.01


def test_ac006_simulation_is_deterministic() -> None:
    inputs = _baseline_inputs()
    a = simulate(inputs, constant_solubility_model)
    b = simulate(inputs, constant_solubility_model)
    assert np.array_equal(a.time_s, b.time_s)
    assert np.array_equal(a.c_o2_mmol_l, b.c_o2_mmol_l)
    assert np.array_equal(a.c_n2_mmol_l, b.c_n2_mmol_l)
    assert a.cstar_o2_mmol_l == b.cstar_o2_mmol_l
    assert a.cstar_n2_mmol_l == b.cstar_n2_mmol_l


def test_permeability_mode_with_zero_permeability_keeps_inlet() -> None:
    inputs = replace(
        _baseline_inputs(),
        transfer_model="permeability",
        tube_od_mm_override_mm=4.76,
        perm_o2_mmol_m_per_m2_s_kpa=0.0,
        perm_n2_mmol_m_per_m2_s_kpa=0.0,
        c_o2_init_mmol_l=0.7,
        c_n2_init_mmol_l=0.4,
    )
    outputs = simulate(inputs, constant_solubility_model)
    assert np.allclose(outputs.c_o2_mmol_l, 0.7)
    assert np.allclose(outputs.c_n2_mmol_l, 0.4)


def test_permeability_mode_higher_permeability_increases_transfer() -> None:
    base = replace(
        _baseline_inputs(),
        transfer_model="permeability",
        tube_od_mm_override_mm=4.76,
        c_o2_init_mmol_l=0.0,
        c_n2_init_mmol_l=0.0,
    )
    low_perm = simulate(
        replace(base, perm_o2_mmol_m_per_m2_s_kpa=1.0e-11, perm_n2_mmol_m_per_m2_s_kpa=1.0e-11),
        constant_solubility_model,
    )
    high_perm = simulate(
        replace(base, perm_o2_mmol_m_per_m2_s_kpa=1.0e-9, perm_n2_mmol_m_per_m2_s_kpa=1.0e-9),
        constant_solubility_model,
    )
    assert high_perm.c_o2_mmol_l[-1] > low_perm.c_o2_mmol_l[-1]
    assert high_perm.c_n2_mmol_l[-1] > low_perm.c_n2_mmol_l[-1]


def test_effective_kla_from_permeability_is_positive() -> None:
    inputs = replace(
        _baseline_inputs(),
        transfer_model="permeability",
        tube_od_mm_override_mm=4.76,
        perm_o2_mmol_m_per_m2_s_kpa=1.0e-9,
        perm_n2_mmol_m_per_m2_s_kpa=2.0e-10,
    )
    kla_o2 = compute_effective_kla_from_permeability("O2", inputs, constant_solubility_model)
    kla_n2 = compute_effective_kla_from_permeability("N2", inputs, constant_solubility_model)
    assert kla_o2 > 0.0
    assert kla_n2 > 0.0


def test_o2_gas_supply_limit_caps_outlet_transfer() -> None:
    base = replace(
        _baseline_inputs(),
        transfer_model="kla",
        kla_o2_s_inv=5.0,
        c_o2_init_mmol_l=0.0,
        flow_ml_min=20.0,
    )
    high_supply = simulate(replace(base, gas_flow_ml_min=500.0), constant_solubility_model)
    low_supply = simulate(replace(base, gas_flow_ml_min=0.1), constant_solubility_model)
    assert low_supply.c_o2_mmol_l[-1] < high_supply.c_o2_mmol_l[-1]
    assert bool(low_supply.metadata["o2_transfer_limited"]) is True


def test_segmented_depletion_limits_o2_more_than_lumped_at_low_gas_flow() -> None:
    base = replace(
        _baseline_inputs(),
        transfer_model="kla",
        kla_o2_s_inv=5.0,
        c_o2_init_mmol_l=0.0,
        flow_ml_min=20.0,
        gas_flow_ml_min=2.0,
    )
    lumped = simulate(replace(base, gas_liquid_model="lumped"), constant_solubility_model)
    segmented = simulate(
        replace(base, gas_liquid_model="segmented", n_segments=80),
        constant_solubility_model,
    )
    assert segmented.c_o2_mmol_l[-1] <= lumped.c_o2_mmol_l[-1] + 1e-3
    assert segmented.metadata["solver"] == "segmented_gas_liquid"
    assert segmented.metadata["gas_out_y_o2"] < base.y_o2
    assert len(segmented.metadata["liq_profile_o2_mmol_l"]) == 81
    assert len(segmented.metadata["gas_profile_y_o2"]) == 80


def test_compute_single_pass_steady_outlet_matches_simulate_terminal_value() -> None:
    inputs = _baseline_inputs()
    steady_o2, steady_n2, _ = compute_single_pass_steady_outlet(
        inputs=inputs,
        solubility_model=constant_solubility_model,
        c_o2_in_mmol_l=inputs.c_o2_init_mmol_l,
        c_n2_in_mmol_l=inputs.c_n2_init_mmol_l,
    )
    outputs = simulate(inputs, constant_solubility_model)
    assert abs(steady_o2 - outputs.c_o2_mmol_l[-1]) < 1e-12
    assert abs(steady_n2 - outputs.c_n2_mmol_l[-1]) < 1e-12
