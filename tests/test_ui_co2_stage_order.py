from dataclasses import replace

from core.params import SimulationInputs
from ui.app import _compute_two_stage_co2_outlet


def _baseline_inputs() -> SimulationInputs:
    return SimulationInputs(
        y_o2=1.0,
        y_n2=0.0,
        p_total_kpa=101.325,
        temperature_c=37.0,
        volume_l=1.0,
        flow_ml_min=4.0,
        tube_id_mm=3.2,
        tube_od_mm=4.76,
        shell_id_mm=5.0,
        tube_length_cm=160.0,
        gas_flow_ml_min=2.0,
        kla_o2_s_inv=0.01,
        kla_n2_s_inv=0.008,
        c_o2_init_mmol_l=0.0,
        c_n2_init_mmol_l=0.0,
        t_end_s=1800.0,
        dt_s=1.0,
        transfer_model="kla",
        gas_liquid_model="segmented",
        n_segments=40,
        enable_co2_ph_stage=True,
        ph_tube_length_cm=16.0,
        ph_gas_co2_percent=99.0,
        ph_gas_flow_ml_min=20.0,
        kla_co2_s_inv=0.05,
        co2_transfer_model="kla",
        c_co2_init_mmol_l=1.0,
        hco3_mmol_l=24.0,
        pka_app=6.1,
        reverse_ph_do_flow=False,
    )


def test_reverse_stage_order_changes_final_co2() -> None:
    base = _baseline_inputs()
    normal = _compute_two_stage_co2_outlet(base, base.c_co2_init_mmol_l)
    reversed_out = _compute_two_stage_co2_outlet(
        replace(base, reverse_ph_do_flow=True),
        base.c_co2_init_mmol_l,
    )

    assert normal["co2_final_outlet_mmol_l"] != reversed_out["co2_final_outlet_mmol_l"]
