from dataclasses import replace

import pytest

from core.params import SimulationInputs, validate_inputs


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


def test_validate_inputs_accepts_baseline() -> None:
    validate_inputs(_baseline_inputs())


def test_validate_inputs_accepts_fraction_sum_within_tolerance() -> None:
    inputs = _baseline_inputs()
    near_boundary = replace(inputs, y_n2=0.79 + 5e-10)
    validate_inputs(near_boundary)


def test_validate_inputs_rejects_fraction_sum_outside_tolerance() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, y_n2=0.79000001)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "y_o2 + y_n2 must equal 1" in str(exc.value)


def test_validate_inputs_rejects_negative_kla() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, kla_o2_s_inv=-0.01)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "kla_o2_s_inv must be >= 0" in str(exc.value)


def test_validate_inputs_rejects_non_positive_pressure() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, p_total_kpa=0.0)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "p_total_kpa must be > 0" in str(exc.value)


def test_validate_inputs_rejects_dt_greater_than_t_end() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, dt_s=2000.0)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "dt_s must be <= t_end_s" in str(exc.value)


def test_validate_inputs_rejects_non_positive_flow() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, flow_ml_min=0.0)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "flow_ml_min must be > 0" in str(exc.value)


def test_validate_inputs_requires_permeability_fields_when_enabled() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, transfer_model="permeability")
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    msg = str(exc.value)
    assert "perm_o2_mmol_m_per_m2_s_kpa is required for permeability mode" in msg
    assert "perm_n2_mmol_m_per_m2_s_kpa is required for permeability mode" in msg


def test_validate_inputs_rejects_shell_not_larger_than_tube_od() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, shell_id_mm=4.5)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "shell_id_mm must be greater than tube_od_mm" in str(exc.value)


def test_validate_inputs_rejects_segmented_with_too_few_segments() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, gas_liquid_model="segmented", n_segments=1)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "n_segments must be >= 2 when gas_liquid_model='segmented'" in str(exc.value)


def test_validate_inputs_rejects_non_positive_total_hold_up_volume() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, total_hold_up_volume_ml=0.0)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "total_hold_up_volume_ml must be > 0 when provided" in str(exc.value)


def test_validate_inputs_rejects_non_positive_hco3() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, hco3_mmol_l=0.0)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "hco3_mmol_l must be > 0" in str(exc.value)


def test_validate_inputs_rejects_co2_percent_out_of_range() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, ph_gas_co2_percent=120.0)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "ph_gas_co2_percent must be between 0 and 100" in str(exc.value)


def test_validate_inputs_requires_co2_permeability_when_enabled() -> None:
    inputs = _baseline_inputs()
    invalid = replace(inputs, co2_transfer_model="permeability", perm_co2_mmol_m_per_m2_s_kpa=None)
    with pytest.raises(ValueError) as exc:
        validate_inputs(invalid)
    assert "perm_co2_mmol_m_per_m2_s_kpa is required for co2_transfer_model='permeability'" in str(exc.value)
