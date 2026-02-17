"""Single-pass tubing simulation for CarboxySim."""

import math

import numpy as np

from .model import (
    SolubilityModel,
    compute_annulus_volume_ml,
    compute_equilibrium_concentrations,
    compute_effective_kla_from_permeability,
    compute_gas_o2_supply_rate_mmol_min,
    compute_residence_time_s,
    compute_single_pass_outlet_concentration,
    compute_tube_volume_ml,
)
from .params import SimulationInputs, validate_inputs
from .results import SimulationOutputs


def _compute_segmented_outlet_concentrations(
    inputs: SimulationInputs,
    c_o2_in_mmol_l: float,
    c_n2_in_mmol_l: float,
    kla_o2_s_inv: float,
    kla_n2_s_inv: float,
    solubility_model: SolubilityModel,
    residence_time_s: float,
) -> tuple[float, float, dict[str, float | bool | list[float]]]:
    """Segmented counterflow coupling with gas depletion along the tube."""

    temperature_k = inputs.temperature_c + 273.15
    r_kpa_l_per_mol_k = 8.314462618
    gas_conc_mmol_l = (inputs.p_total_kpa / (r_kpa_l_per_mol_k * temperature_k)) * 1000.0
    total_gas_mmol_min = (inputs.gas_flow_ml_min / 1000.0) * gas_conc_mmol_l
    n_o2_inlet_mmol_min = total_gas_mmol_min * inputs.y_o2
    n_n2_inlet_mmol_min = total_gas_mmol_min * inputs.y_n2
    q_liq_l_min = inputs.flow_ml_min / 1000.0
    dt_seg_s = residence_time_s / inputs.n_segments
    a_o2 = 1.0 - math.exp(-kla_o2_s_inv * dt_seg_s)
    a_n2 = 1.0 - math.exp(-kla_n2_s_inv * dt_seg_s)

    # Gas interfaces indexed left->right. Gas inlet is at right boundary (counterflow).
    iface_o2 = [n_o2_inlet_mmol_min for _ in range(inputs.n_segments + 1)]
    iface_n2 = [n_n2_inlet_mmol_min for _ in range(inputs.n_segments + 1)]
    limited_hit = False
    c_liq_o2 = [0.0 for _ in range(inputs.n_segments + 1)]
    c_liq_n2 = [0.0 for _ in range(inputs.n_segments + 1)]
    c_liq_o2[0] = c_o2_in_mmol_l
    c_liq_n2[0] = c_n2_in_mmol_l

    for _ in range(50):
        prev_iface_o2 = iface_o2.copy()
        prev_iface_n2 = iface_n2.copy()
        c_liq_o2[0] = c_o2_in_mmol_l
        c_liq_n2[0] = c_n2_in_mmol_l
        tr_o2 = [0.0 for _ in range(inputs.n_segments)]
        tr_n2 = [0.0 for _ in range(inputs.n_segments)]

        for seg in range(inputs.n_segments):
            gas_o2_in = prev_iface_o2[seg + 1]
            gas_n2_in = prev_iface_n2[seg + 1]
            gas_total = max(gas_o2_in + gas_n2_in, 1e-15)
            y_o2_local = max(0.0, min(1.0, gas_o2_in / gas_total))
            y_n2_local = max(0.0, min(1.0, gas_n2_in / gas_total))

            cstar_o2 = solubility_model("O2", inputs.temperature_c) * y_o2_local * inputs.p_total_kpa
            cstar_n2 = solubility_model("N2", inputs.temperature_c) * y_n2_local * inputs.p_total_kpa

            dc_o2 = (cstar_o2 - c_liq_o2[seg]) * a_o2
            dc_n2 = (cstar_n2 - c_liq_n2[seg]) * a_n2
            seg_tr_o2 = dc_o2 * q_liq_l_min
            seg_tr_n2 = dc_n2 * q_liq_l_min

            if seg_tr_o2 > gas_o2_in:
                limited_hit = True
                seg_tr_o2 = gas_o2_in
                dc_o2 = seg_tr_o2 / max(q_liq_l_min, 1e-15)
            if seg_tr_n2 > gas_n2_in:
                limited_hit = True
                seg_tr_n2 = gas_n2_in
                dc_n2 = seg_tr_n2 / max(q_liq_l_min, 1e-15)

            tr_o2[seg] = seg_tr_o2
            tr_n2[seg] = seg_tr_n2
            c_liq_o2[seg + 1] = c_liq_o2[seg] + dc_o2
            c_liq_n2[seg + 1] = c_liq_n2[seg] + dc_n2

        iface_o2[inputs.n_segments] = n_o2_inlet_mmol_min
        iface_n2[inputs.n_segments] = n_n2_inlet_mmol_min
        for seg in range(inputs.n_segments - 1, -1, -1):
            iface_o2[seg] = max(0.0, iface_o2[seg + 1] - tr_o2[seg])
            iface_n2[seg] = max(0.0, iface_n2[seg + 1] - tr_n2[seg])

        diff = max(
            max(abs(a - b) for a, b in zip(iface_o2, prev_iface_o2)),
            max(abs(a - b) for a, b in zip(iface_n2, prev_iface_n2)),
        )
        if diff < 1e-9:
            break

    gas_out_total = max(iface_o2[0] + iface_n2[0], 1e-15)
    gas_profile_y_o2 = []
    for seg in range(inputs.n_segments):
        gtot = max(iface_o2[seg + 1] + iface_n2[seg + 1], 1e-15)
        gas_profile_y_o2.append(iface_o2[seg + 1] / gtot)
    extra = {
        "o2_transfer_limited": limited_hit,
        "gas_out_y_o2": iface_o2[0] / gas_out_total,
        "gas_out_y_n2": iface_n2[0] / gas_out_total,
        "liq_profile_o2_mmol_l": c_liq_o2,
        "gas_profile_y_o2": gas_profile_y_o2,
    }
    return c_liq_o2[-1], c_liq_n2[-1], extra


def compute_single_pass_steady_outlet(
    inputs: SimulationInputs,
    solubility_model: SolubilityModel,
    c_o2_in_mmol_l: float,
    c_n2_in_mmol_l: float,
) -> tuple[float, float, dict[str, float | bool | list[float]]]:
    """Compute steady single-pass outlet concentrations for a given inlet state."""

    cstar_o2, cstar_n2 = compute_equilibrium_concentrations(inputs, solubility_model)
    tube_volume_ml = compute_tube_volume_ml(inputs.tube_id_mm, inputs.tube_length_cm)
    annulus_volume_ml = compute_annulus_volume_ml(inputs.shell_id_mm, inputs.tube_od_mm, inputs.tube_length_cm)
    residence_time_s = compute_residence_time_s(inputs.flow_ml_min, tube_volume_ml)
    gas_residence_time_s = compute_residence_time_s(inputs.gas_flow_ml_min, annulus_volume_ml)

    if inputs.transfer_model == "permeability":
        kla_o2_s_inv = compute_effective_kla_from_permeability("O2", inputs, solubility_model)
        kla_n2_s_inv = compute_effective_kla_from_permeability("N2", inputs, solubility_model)
        model_name = "single_pass_tubing_permeability_Henry"
    else:
        kla_o2_s_inv = inputs.kla_o2_s_inv
        kla_n2_s_inv = inputs.kla_n2_s_inv
        model_name = "single_pass_tubing_kLa_Henry"

    o2_supply_rate_mmol_min = compute_gas_o2_supply_rate_mmol_min(
        inputs.gas_flow_ml_min,
        inputs.y_o2,
        inputs.p_total_kpa,
        inputs.temperature_c,
    )
    liquid_flow_l_min = inputs.flow_ml_min / 1000.0

    seg_meta: dict[str, float | bool | list[float]] | None = None
    if inputs.gas_liquid_model == "segmented":
        steady_out_o2, steady_out_n2, seg_meta = _compute_segmented_outlet_concentrations(
            inputs=inputs,
            c_o2_in_mmol_l=c_o2_in_mmol_l,
            c_n2_in_mmol_l=c_n2_in_mmol_l,
            kla_o2_s_inv=kla_o2_s_inv,
            kla_n2_s_inv=kla_n2_s_inv,
            solubility_model=solubility_model,
            residence_time_s=residence_time_s,
        )
        o2_transfer_limited = bool(seg_meta["o2_transfer_limited"])
    else:
        steady_out_o2 = compute_single_pass_outlet_concentration(
            c_in_mmol_l=c_o2_in_mmol_l,
            cstar_mmol_l=cstar_o2,
            kla_s_inv=kla_o2_s_inv,
            residence_time_s=residence_time_s,
        )
        steady_out_n2 = compute_single_pass_outlet_concentration(
            c_in_mmol_l=c_n2_in_mmol_l,
            cstar_mmol_l=cstar_n2,
            kla_s_inv=kla_n2_s_inv,
            residence_time_s=residence_time_s,
        )
        o2_required_rate_mmol_min = max(0.0, (steady_out_o2 - c_o2_in_mmol_l) * liquid_flow_l_min)
        o2_transfer_limited = o2_required_rate_mmol_min > o2_supply_rate_mmol_min
        if o2_transfer_limited:
            max_o2_delta_c = o2_supply_rate_mmol_min / max(liquid_flow_l_min, 1e-15)
            steady_out_o2 = c_o2_in_mmol_l + max_o2_delta_c

    metadata: dict[str, float | bool | list[float]] = {
        "model": model_name,
        "solver": "segmented_gas_liquid" if inputs.gas_liquid_model == "segmented" else "analytical_plug_flow",
        "tube_volume_ml": tube_volume_ml,
        "annulus_volume_ml": annulus_volume_ml,
        "residence_time_s": residence_time_s,
        "gas_residence_time_s": gas_residence_time_s,
        "effective_kla_o2_s_inv": kla_o2_s_inv,
        "effective_kla_n2_s_inv": kla_n2_s_inv,
        "o2_supply_rate_mmol_min": o2_supply_rate_mmol_min,
        "o2_transfer_limited": o2_transfer_limited,
        "gas_liquid_model": inputs.gas_liquid_model,
        "n_segments": inputs.n_segments,
    }
    if seg_meta is not None:
        metadata["gas_out_y_o2"] = float(seg_meta["gas_out_y_o2"])
        metadata["gas_out_y_n2"] = float(seg_meta["gas_out_y_n2"])
        metadata["liq_profile_o2_mmol_l"] = [float(v) for v in seg_meta["liq_profile_o2_mmol_l"]]
        metadata["gas_profile_y_o2"] = [float(v) for v in seg_meta["gas_profile_y_o2"]]

    return steady_out_o2, steady_out_n2, metadata


def simulate(inputs: SimulationInputs, solubility_model: SolubilityModel) -> SimulationOutputs:
    """Run single-pass tubing simulation for dissolved O2 and N2 in PBS."""

    validate_inputs(inputs)
    cstar_o2, cstar_n2 = compute_equilibrium_concentrations(inputs, solubility_model)
    steady_out_o2, steady_out_n2, steady_meta = compute_single_pass_steady_outlet(
        inputs=inputs,
        solubility_model=solubility_model,
        c_o2_in_mmol_l=inputs.c_o2_init_mmol_l,
        c_n2_in_mmol_l=inputs.c_n2_init_mmol_l,
    )

    n_steps = math.floor(inputs.t_end_s / inputs.dt_s) + 1
    time_s = np.arange(n_steps, dtype=float) * inputs.dt_s
    c_o2 = np.full(n_steps, steady_out_o2, dtype=float)
    c_n2 = np.full(n_steps, steady_out_n2, dtype=float)

    # Represent startup transport delay before treated fluid reaches outlet.
    residence_time_s = float(steady_meta["residence_time_s"])
    delay_mask = time_s < residence_time_s
    c_o2[delay_mask] = inputs.c_o2_init_mmol_l
    c_n2[delay_mask] = inputs.c_n2_init_mmol_l

    metadata = {
        "model": steady_meta["model"],
        "solver": steady_meta["solver"],
        "n_steps": n_steps,
        "dt_s": inputs.dt_s,
        "t_end_s": inputs.t_end_s,
        "tube_volume_ml": steady_meta["tube_volume_ml"],
        "annulus_volume_ml": steady_meta["annulus_volume_ml"],
        "residence_time_s": steady_meta["residence_time_s"],
        "gas_residence_time_s": steady_meta["gas_residence_time_s"],
        "effective_kla_o2_s_inv": steady_meta["effective_kla_o2_s_inv"],
        "effective_kla_n2_s_inv": steady_meta["effective_kla_n2_s_inv"],
        "o2_supply_rate_mmol_min": steady_meta["o2_supply_rate_mmol_min"],
        "o2_transfer_limited": steady_meta["o2_transfer_limited"],
        "gas_liquid_model": steady_meta["gas_liquid_model"],
        "n_segments": steady_meta["n_segments"],
    }
    if inputs.gas_liquid_model == "segmented":
        metadata["gas_out_y_o2"] = float(steady_meta["gas_out_y_o2"])
        metadata["gas_out_y_n2"] = float(steady_meta["gas_out_y_n2"])
        metadata["liq_profile_o2_mmol_l"] = [float(v) for v in steady_meta["liq_profile_o2_mmol_l"]]
        metadata["gas_profile_y_o2"] = [float(v) for v in steady_meta["gas_profile_y_o2"]]

    return SimulationOutputs(
        time_s=time_s,
        c_o2_mmol_l=c_o2,
        c_n2_mmol_l=c_n2,
        cstar_o2_mmol_l=cstar_o2,
        cstar_n2_mmol_l=cstar_n2,
        metadata=metadata,
    )
