"""Streamlit UI for CarboxySim MVP."""

from __future__ import annotations

import csv
from collections import deque
from dataclasses import replace
from dataclasses import asdict
import io
import json

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from core import (
    SimulationInputs,
    compute_single_pass_steady_outlet,
    compute_tube_volume_ml,
    compute_equilibrium_concentrations,
    constant_solubility_model,
    simulate,
    validate_inputs,
)


def _default_inputs() -> SimulationInputs:
    return SimulationInputs(
        y_o2=0.50,
        y_n2=0.50,
        p_total_kpa=101.325,
        temperature_c=37.0,
        volume_l=1.0,
        flow_ml_min=2.0,
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


def _build_csv_text(time_s, c_o2, c_n2) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["time_s", "c_o2_mmol_l", "c_n2_mmol_l"])
    for idx in range(len(time_s)):
        writer.writerow([f"{time_s[idx]:.12g}", f"{c_o2[idx]:.12g}", f"{c_n2[idx]:.12g}"])
    return buffer.getvalue()


def _build_excel_bytes(time_s, c_o2, c_n2) -> bytes:
    """Build XLSX export bytes for timeseries output."""

    df = pd.DataFrame(
        {
            "time_s": [float(v) for v in time_s],
            "c_o2_mmol_l": [float(v) for v in c_o2],
            "c_n2_mmol_l": [float(v) for v in c_n2],
        }
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="timeseries", index=False)
    return output.getvalue()


def _build_source_vessel_excel_bytes(source_vessel_df: pd.DataFrame) -> bytes:
    """Build XLSX export bytes for source-vessel DO trajectory."""

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        source_vessel_df.to_excel(writer, sheet_name="source_vessel_do", index=False)
    return output.getvalue()


def _reference_concentrations_mmol_l(temperature_c: float) -> tuple[float, float]:
    """Reference concentrations at air/1atm for percentage-based inlet fields."""
    p_total_ref_kpa = 101.325
    y_o2_ref = 0.21
    y_n2_ref = 0.79
    s_o2 = constant_solubility_model("O2", temperature_c)
    s_n2 = constant_solubility_model("N2", temperature_c)
    c_o2_ref = s_o2 * y_o2_ref * p_total_ref_kpa
    c_n2_ref = s_n2 * y_n2_ref * p_total_ref_kpa
    return c_o2_ref, c_n2_ref


def _pressure_from_mode(
    pressure_mode: str,
    gas_flow_ml_min: float,
    p_atm_kpa: float,
    p_total_manual_kpa: float | None,
) -> tuple[float, float]:
    """Return (p_total_kpa, delta_p_mbar) from pressure-mode selection."""

    if pressure_mode == "Manual":
        if p_total_manual_kpa is None:
            raise ValueError("Manual pressure mode requires p_total_manual_kpa")
        return p_total_manual_kpa, max(0.0, (p_total_manual_kpa - p_atm_kpa) * 10.0)
    if pressure_mode == "Conservative curve":
        delta_p_mbar = 4.0 * gas_flow_ml_min
        return p_atm_kpa + 0.1 * delta_p_mbar, delta_p_mbar
    if pressure_mode == "Optimistic curve":
        delta_p_mbar = 6.4 * gas_flow_ml_min
        return p_atm_kpa + 0.1 * delta_p_mbar, delta_p_mbar
    raise ValueError(f"Unsupported pressure mode: {pressure_mode}")


def _estimate_time_to_target_do_source_vessel(
    inputs: SimulationInputs,
    target_do_percent: float,
    do_ref_o2_mmol_l: float,
) -> tuple[bool, float | None, float]:
    """Estimate time for a perfectly mixed source vessel to reach target DO%."""

    target_c_o2 = (target_do_percent / 100.0) * do_ref_o2_mmol_l
    c_o2 = float(inputs.c_o2_init_mmol_l)
    c_n2 = float(inputs.c_n2_init_mmol_l)
    q_l_min = inputs.flow_ml_min / 1000.0
    vessel_volume_l = inputs.volume_l

    if vessel_volume_l <= 0.0 or q_l_min <= 0.0:
        return False, None, (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0

    if abs(c_o2 - target_c_o2) <= 1e-9:
        return True, 0.0, (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0

    max_time_s = 8.0 * 3600.0
    tau_s = (vessel_volume_l / q_l_min) * 60.0
    dt_s = max(max_time_s / 4000.0, min(30.0, max(1.0, tau_s / 10.0)))
    n_steps = int(max_time_s / dt_s)
    reaching_up = target_c_o2 > c_o2
    transport_volume_ml = (
        float(inputs.total_hold_up_volume_ml)
        if inputs.total_hold_up_volume_ml is not None
        else compute_tube_volume_ml(inputs.tube_id_mm, inputs.tube_length_cm)
    )
    transport_delay_s = (transport_volume_ml / max(inputs.flow_ml_min, 1e-12)) * 60.0
    delay_steps = max(0, int(round(transport_delay_s / dt_s)))
    out_hist_o2 = [c_o2 for _ in range(delay_steps + 1)]
    out_hist_n2 = [c_n2 for _ in range(delay_steps + 1)]

    for step in range(1, n_steps + 1):
        c_o2_out, c_n2_out, _ = compute_single_pass_steady_outlet(
            inputs=inputs,
            solubility_model=constant_solubility_model,
            c_o2_in_mmol_l=c_o2,
            c_n2_in_mmol_l=c_n2,
        )
        out_hist_o2.append(c_o2_out)
        out_hist_n2.append(c_n2_out)
        delayed_out_o2 = out_hist_o2.pop(0)
        delayed_out_n2 = out_hist_n2.pop(0)
        dt_min = dt_s / 60.0
        dc_o2_dt = (q_l_min / vessel_volume_l) * (delayed_out_o2 - c_o2)
        dc_n2_dt = (q_l_min / vessel_volume_l) * (delayed_out_n2 - c_n2)
        c_o2 += dc_o2_dt * dt_min
        c_n2 += dc_n2_dt * dt_min
        t_now_s = step * dt_s
        if reaching_up and c_o2 >= target_c_o2:
            return True, t_now_s, (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0
        if (not reaching_up) and c_o2 <= target_c_o2:
            return True, t_now_s, (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0

    return False, None, (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0


def _simulate_source_vessel_do_timeseries(
    inputs: SimulationInputs,
    do_ref_o2_mmol_l: float,
    t_end_s: float,
    dt_s: float,
) -> pd.DataFrame:
    """Simulate source-vessel DO% trajectory for a perfectly mixed recirculating vessel."""

    # Keep plotting responsive for long horizons by capping point count.
    max_points = 1200
    eff_dt_s = max(dt_s, t_end_s / max_points)
    n_steps = int(np.floor(t_end_s / eff_dt_s)) + 1
    time_s = np.arange(n_steps, dtype=float) * eff_dt_s

    c_o2 = float(inputs.c_o2_init_mmol_l)
    c_n2 = float(inputs.c_n2_init_mmol_l)
    q_l_min = inputs.flow_ml_min / 1000.0
    vessel_volume_l = max(inputs.volume_l, 1e-15)

    transport_volume_ml = (
        float(inputs.total_hold_up_volume_ml)
        if inputs.total_hold_up_volume_ml is not None
        else compute_tube_volume_ml(inputs.tube_id_mm, inputs.tube_length_cm)
    )
    transport_delay_s = (transport_volume_ml / max(inputs.flow_ml_min, 1e-15)) * 60.0
    delay_steps = max(0, int(round(transport_delay_s / max(eff_dt_s, 1e-12))))
    out_hist_o2: deque[float] = deque([c_o2] * (delay_steps + 1), maxlen=delay_steps + 1)
    out_hist_n2: deque[float] = deque([c_n2] * (delay_steps + 1), maxlen=delay_steps + 1)

    rows = [
        {
            "time_s": 0.0,
            "time_min": 0.0,
            "source_do2_percent": (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0,
        }
    ]
    dt_min = eff_dt_s / 60.0

    for step in range(1, n_steps):
        c_o2_out, c_n2_out, _ = compute_single_pass_steady_outlet(
            inputs=inputs,
            solubility_model=constant_solubility_model,
            c_o2_in_mmol_l=c_o2,
            c_n2_in_mmol_l=c_n2,
        )
        delayed_out_o2 = out_hist_o2[0]
        delayed_out_n2 = out_hist_n2[0]
        out_hist_o2.append(c_o2_out)
        out_hist_n2.append(c_n2_out)

        dc_o2_dt = (q_l_min / vessel_volume_l) * (delayed_out_o2 - c_o2)
        dc_n2_dt = (q_l_min / vessel_volume_l) * (delayed_out_n2 - c_n2)
        c_o2 += dc_o2_dt * dt_min
        c_n2 += dc_n2_dt * dt_min

        t_s = float(time_s[step])
        rows.append(
            {
                "time_s": t_s,
                "time_min": t_s / 60.0,
                "source_do2_percent": (c_o2 / max(do_ref_o2_mmol_l, 1e-15)) * 100.0,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="CarboxySim", layout="wide")
    st.title("CarboxySim - O2/N2 in PBS (Single-Pass Tubing)")
    st.caption("Research-first MVP using kLa + Henry law and plug-flow residence-time transfer.")

    defaults = _default_inputs()

    with st.sidebar:
        st.header("Inputs")
        o2_percent = st.number_input(
            "O2 [%]",
            min_value=0.0,
            max_value=100.0,
            value=defaults.y_o2 * 100.0,
            step=0.5,
            help="Gas-phase oxygen percentage. N2 is automatically set to keep total at 100%.",
        )
        n2_percent = 100.0 - o2_percent
        st.caption(f"N2 [%] (auto): {n2_percent:.2f}")
        y_o2 = o2_percent / 100.0
        y_n2 = n2_percent / 100.0
        gas_flow_ml_min = st.number_input(
            "gas_flow_ml_min [mL/min]",
            min_value=0.001,
            value=defaults.gas_flow_ml_min,
            step=1.0,
            help="Total gas flow through the annulus. This limits available O2 supply.",
        )
        flow_ml_min = st.number_input(
            "perfusion_speed_ml_min [mL/min]",
            min_value=0.001,
            value=defaults.flow_ml_min,
            step=0.5,
            help="Liquid perfusion speed through tubing. Lower flow increases residence time and transfer.",
        )
        temperature_c = st.number_input(
            "temperature_c [C]",
            value=defaults.temperature_c,
            step=1.0,
            help="Liquid temperature in degrees Celsius.",
        )
        volume_l = st.number_input(
            "volume_l [L] (source vessel)",
            min_value=0.0001,
            value=defaults.volume_l,
            step=0.1,
            help="Source vessel volume. Kept for context/metadata in single-pass mode.",
        )
        c_o2_ref_mmol_l, c_n2_ref_mmol_l = _reference_concentrations_mmol_l(temperature_c)
        c_o2_init_percent = st.number_input(
            "inlet_do2_percent [%]",
            min_value=0.0,
            value=(defaults.c_o2_init_mmol_l / c_o2_ref_mmol_l) * 100.0,
            step=1.0,
            help="User-set inlet dissolved O2 as DO%. 100% is O2 equilibrium at air (21%) and 1 atm.",
        )
        c_n2_init_percent = st.number_input(
            "inlet_n2_percent [%]",
            min_value=0.0,
            value=(defaults.c_n2_init_mmol_l / c_n2_ref_mmol_l) * 100.0,
            step=1.0,
            help="Inlet dissolved N2 as % of N2 reference (air at 1 atm).",
        )
        target_source_do_percent = st.number_input(
            "target_source_do2_percent [%]",
            min_value=0.0,
            value=100.0,
            step=1.0,
            help="Target DO% for the perfectly mixed source vessel recirculation estimate.",
        )
        c_o2_init_mmol_l = (c_o2_init_percent / 100.0) * c_o2_ref_mmol_l
        c_n2_init_mmol_l = (c_n2_init_percent / 100.0) * c_n2_ref_mmol_l
        tube_id_mm = st.number_input(
            "tube_id_mm [mm]",
            min_value=0.001,
            value=defaults.tube_id_mm,
            step=0.1,
            help="Tubing inner diameter used to calculate hold-up volume.",
        )
        tube_od_mm = st.number_input(
            "tube_od_mm [mm]",
            min_value=tube_id_mm + 0.001,
            value=defaults.tube_od_mm,
            step=0.1,
            help="Tubing outer diameter.",
        )
        shell_id_mm = st.number_input(
            "shell_id_mm [mm]",
            min_value=tube_od_mm + 0.001,
            value=defaults.shell_id_mm,
            step=0.1,
            help="Inner diameter of the closed outer tube around the gas-exchange tubing.",
        )
        tube_length_cm = st.number_input(
            "tube_length_cm [cm]",
            min_value=0.001,
            value=defaults.tube_length_cm,
            step=1.0,
            help="Effective gas-exchange tubing length.",
        )
        auto_tube_volume_ml = compute_tube_volume_ml(tube_id_mm, tube_length_cm)
        total_hold_up_volume_ml = st.number_input(
            "total_hold_up_volume_ml [mL]",
            min_value=0.001,
            value=float(auto_tube_volume_ml),
            step=0.5,
            help="Total liquid hold-up from source through loop to measurement point. Used for startup transport delay.",
        )
        st.caption(
            f"Derived transport delay = volume / perfusion speed = "
            f"{(total_hold_up_volume_ml / max(flow_ml_min, 1e-12)):.2f} min"
        )
        pressure_mode = st.selectbox(
            "Pressure model",
            options=["Manual", "Conservative curve", "Optimistic curve"],
            index=0,
            help="Select manual pressure input or flow-derived pressure curve.",
        )
        p_atm_kpa = st.number_input(
            "p_atm_kpa [kPa]",
            min_value=0.001,
            value=101.325,
            step=0.5,
            help="Atmospheric baseline pressure used by curve modes.",
        )
        if pressure_mode == "Manual":
            p_total_manual_kpa = st.number_input(
                "p_total_kpa [kPa]",
                min_value=0.001,
                value=defaults.p_total_kpa,
                step=1.0,
                help="Absolute total gas pressure at the carboxygenator.",
            )
        else:
            p_total_manual_kpa = None
        p_total_kpa, delta_p_mbar = _pressure_from_mode(
            pressure_mode=pressure_mode,
            gas_flow_ml_min=gas_flow_ml_min,
            p_atm_kpa=p_atm_kpa,
            p_total_manual_kpa=p_total_manual_kpa,
        )
        if pressure_mode != "Manual":
            st.caption(
                f"Derived pressure: dP={delta_p_mbar:.1f} mbar, p_total={p_total_kpa:.3f} kPa"
            )
        transfer_model_ui = st.selectbox(
            "Transfer model",
            options=["kLa", "Permeability"],
            index=1,
            help="kLa mode uses fitted coefficients. Permeability mode derives effective transfer from tubing material data.",
        )
        if transfer_model_ui == "kLa":
            transfer_model = "kla"
            kla_o2_s_inv = st.number_input(
                "kla_o2_s_inv [1/s]",
                min_value=0.0,
                value=defaults.kla_o2_s_inv,
                step=0.001,
                format="%.6f",
                help="O2 overall mass-transfer coefficient. Higher means faster transfer toward equilibrium.",
            )
            kla_n2_s_inv = st.number_input(
                "kla_n2_s_inv [1/s]",
                min_value=0.0,
                value=defaults.kla_n2_s_inv,
                step=0.001,
                format="%.6f",
                help="N2 overall mass-transfer coefficient. Higher means faster transfer toward equilibrium.",
            )
            perm_o2 = None
            perm_n2 = None
            tube_od_mm_override = None
        else:
            transfer_model = "permeability"
            perm_unit = st.selectbox(
                "Permeability unit",
                options=["Barrer", "mmol*m/(m2*s*kPa)"],
                index=0,
                help="Choose the unit used by your tubing datasheet.",
            )
            if perm_unit == "Barrer":
                perm_o2_barrer = st.number_input(
                    "perm_o2 [Barrer]",
                    min_value=0.0,
                    value=600.0,
                    step=10.0,
                    help="O2 permeability from datasheet in Barrer.",
                )
                perm_n2_barrer = st.number_input(
                    "perm_n2 [Barrer]",
                    min_value=0.0,
                    value=300.0,
                    step=10.0,
                    help="N2 permeability from datasheet in Barrer.",
                )
                barrer_to_mmol_m_per_m2_s_kpa = 3.35e-10
                perm_o2 = perm_o2_barrer * barrer_to_mmol_m_per_m2_s_kpa
                perm_n2 = perm_n2_barrer * barrer_to_mmol_m_per_m2_s_kpa
                st.caption(
                    "Converted permeability: "
                    f"O2={perm_o2:.3e}, N2={perm_n2:.3e} mmol*m/(m2*s*kPa)"
                )
            else:
                perm_o2 = st.number_input(
                    "perm_o2 [mmol*m/(m2*s*kPa)]",
                    min_value=0.0,
                    value=2.0e-7,
                    step=1.0e-8,
                    format="%.3e",
                    help="O2 permeability coefficient of tubing wall material.",
                )
                perm_n2 = st.number_input(
                    "perm_n2 [mmol*m/(m2*s*kPa)]",
                    min_value=0.0,
                    value=1.0e-7,
                    step=1.0e-8,
                    format="%.3e",
                    help="N2 permeability coefficient of tubing wall material.",
                )
            kla_o2_s_inv = 0.0
            kla_n2_s_inv = 0.0
            tube_od_mm_override = tube_od_mm
        gas_liquid_model_ui = st.selectbox(
            "Gas-liquid coupling",
            options=["Lumped", "Segmented depletion"],
            index=1,
            help="Segmented depletion updates gas composition along tube segments; lumped uses a single gas composition.",
        )
        gas_liquid_model = "segmented" if gas_liquid_model_ui == "Segmented depletion" else "lumped"
        n_segments = int(
            st.number_input(
                "n_segments [-]",
                min_value=2,
                value=160,
                step=1,
                help="Number of axial segments when using segmented depletion mode.",
                disabled=(gas_liquid_model != "segmented"),
            )
        )
        t_end_s = st.number_input(
            "t_end_min [min]",
            min_value=0.1,
            value=defaults.t_end_s / 60.0,
            step=1.0,
            help="Total simulated time window.",
        )
        dt_s = st.number_input(
            "dt_min [min]",
            min_value=0.0001,
            value=defaults.dt_s / 60.0,
            step=0.01,
            format="%.4f",
            help="Time resolution for generated output points.",
        )
        t_end_s *= 60.0
        dt_s *= 60.0
        auto_run = st.checkbox(
            "Auto-run simulation",
            value=True,
            help="Automatically re-run when model inputs change.",
        )
        run = st.button("Run Simulation", type="primary")

    st.markdown("### Assumptions")
    st.write("- Single-pass tubing transfer from source to waste")
    st.write("- Constant gas composition, pressure, and temperature")
    st.write("- No reactions in PBS")

    candidate_inputs = SimulationInputs(
        y_o2=y_o2,
        y_n2=y_n2,
        p_total_kpa=p_total_kpa,
        temperature_c=temperature_c,
        volume_l=volume_l,
        flow_ml_min=flow_ml_min,
        tube_id_mm=tube_id_mm,
        tube_od_mm=tube_od_mm,
        shell_id_mm=shell_id_mm,
        tube_length_cm=tube_length_cm,
        gas_flow_ml_min=gas_flow_ml_min,
        kla_o2_s_inv=kla_o2_s_inv,
        kla_n2_s_inv=kla_n2_s_inv,
        c_o2_init_mmol_l=c_o2_init_mmol_l,
        c_n2_init_mmol_l=c_n2_init_mmol_l,
        t_end_s=t_end_s,
        dt_s=dt_s,
        transfer_model=transfer_model,
        tube_od_mm_override_mm=tube_od_mm_override,
        perm_o2_mmol_m_per_m2_s_kpa=perm_o2,
        perm_n2_mmol_m_per_m2_s_kpa=perm_n2,
        gas_liquid_model=gas_liquid_model,
        n_segments=n_segments,
        total_hold_up_volume_ml=total_hold_up_volume_ml,
    )

    should_run = run
    if auto_run:
        last_inputs = st.session_state.get("last_inputs")
        last_pressure_context = st.session_state.get("last_pressure_context")
        if last_inputs is None or last_pressure_context is None:
            should_run = True
        else:
            pressure_changed = (
                pressure_mode != str(last_pressure_context.get("pressure_mode"))
                or abs(p_atm_kpa - float(last_pressure_context.get("p_atm_kpa", p_atm_kpa))) > 1e-12
                or abs(delta_p_mbar - float(last_pressure_context.get("delta_p_mbar", delta_p_mbar))) > 1e-9
            )
            if candidate_inputs != last_inputs or pressure_changed:
                should_run = True

    if should_run:
        try:
            validate_inputs(candidate_inputs)
            run_outputs = simulate(candidate_inputs, constant_solubility_model)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state["last_inputs"] = candidate_inputs
        st.session_state["last_outputs"] = run_outputs
        st.session_state["last_pressure_context"] = {
            "pressure_mode": pressure_mode,
            "p_atm_kpa": p_atm_kpa,
            "delta_p_mbar": delta_p_mbar,
        }

    if "last_inputs" not in st.session_state or "last_outputs" not in st.session_state:
        st.info("Set inputs in the sidebar and click 'Run Simulation'.")
        return

    inputs = st.session_state["last_inputs"]
    outputs = st.session_state["last_outputs"]
    pressure_context = st.session_state.get(
        "last_pressure_context",
        {"pressure_mode": "Manual", "p_atm_kpa": 101.325, "delta_p_mbar": (inputs.p_total_kpa - 101.325) * 10.0},
    )
    if not should_run:
        st.caption("Showing results from last simulation run. Flow sweep updates live.")
    if not auto_run and candidate_inputs != inputs:
        st.warning(
            "Model inputs changed since last run. Click 'Run Simulation' to apply changes. "
            "Flow sweep controls update live, but gas/liquid model inputs do not."
        )

    do_ref_inputs = replace(inputs, y_o2=0.21, y_n2=0.79, p_total_kpa=101.325)
    do_ref_o2_mmol_l, _ = compute_equilibrium_concentrations(do_ref_inputs, constant_solubility_model)
    do_percent = (outputs.c_o2_mmol_l / do_ref_o2_mmol_l) * 100.0
    flow_l_min = inputs.flow_ml_min / 1000.0
    o2_outlet_rate_mmol_min = float(outputs.c_o2_mmol_l[-1]) * flow_l_min
    o2_inlet_rate_mmol_min = float(inputs.c_o2_init_mmol_l) * flow_l_min
    o2_added_rate_mmol_min = o2_outlet_rate_mmol_min - o2_inlet_rate_mmol_min

    st.markdown("### Segmented Counterflow Visualization")
    if outputs.metadata.get("gas_liquid_model") == "segmented":
        liq_profile = outputs.metadata.get("liq_profile_o2_mmol_l", [])
        gas_profile = outputs.metadata.get("gas_profile_y_o2", [])
        if len(liq_profile) >= 2 and len(gas_profile) >= 1:
            left_col, center_col, right_col = st.columns([1, 6, 1])
            left_col.metric("DO2% inlet", f"{do_percent[0]:.2f}%")
            right_col.metric("DO2% outlet", f"{do_percent[-1]:.2f}%")
            nseg = len(gas_profile)
            seg_rows = []
            for seg in range(nseg):
                x0 = seg / nseg
                x1 = (seg + 1) / nseg
                liq_do_seg = (((liq_profile[seg] + liq_profile[seg + 1]) * 0.5) / do_ref_o2_mmol_l) * 100.0
                gas_do_potential_seg = (
                    (gas_profile[seg] * inputs.p_total_kpa) / (0.21 * 101.325)
                ) * 100.0
                seg_rows.append(
                    {
                        "lane": "Liquid DO% (left -> right flow)",
                        "x0": x0,
                        "x1": x1,
                        "value": float(liq_do_seg),
                    }
                )
                seg_rows.append(
                    {
                        "lane": "Gas O2 potential% (right -> left flow)",
                        "x0": x0,
                        "x1": x1,
                        "value": float(gas_do_potential_seg),
                    }
                )
            seg_df = pd.DataFrame(seg_rows)
            seg_chart = (
                alt.Chart(seg_df)
                .mark_rect()
                .encode(
                    x=alt.X("x0:Q", title="Normalized tube position (0 = liquid inlet, 1 = liquid outlet)"),
                    x2="x1:Q",
                    y=alt.Y("lane:N", title="Segment bar"),
                    color=alt.Color(
                        "value:Q",
                        title="Color scale [% DO equivalent]",
                        scale=alt.Scale(
                            domain=[0, 100, 250, 500],
                            range=["#d73027", "#fdae61", "#74add1", "#313695"],
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("lane:N", title="Lane"),
                        alt.Tooltip("value:Q", title="Value [%]", format=".2f"),
                    ],
                )
                .properties(height=360)
            )
            st.caption(
                "Color legend: 0% DO = red (low O2), 500% DO = blue (high O2). "
                "Liquid flows left->right, gas flows right->left."
            )
            center_col.altair_chart(seg_chart, use_container_width=True)
        else:
            st.info("No segmented profile data available in last run.")
    else:
        st.info("Run with `Gas-liquid coupling = Segmented depletion` and click `Run Simulation` to show this view.")

    reached_target, target_time_s, final_pred_do_percent = _estimate_time_to_target_do_source_vessel(
        inputs=inputs,
        target_do_percent=target_source_do_percent,
        do_ref_o2_mmol_l=do_ref_o2_mmol_l,
    )
    st.markdown("### Source Vessel Target (Perfect Mixing)")
    start_do_percent = (inputs.c_o2_init_mmol_l / max(do_ref_o2_mmol_l, 1e-15)) * 100.0
    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    tcol1.metric("Start DO2 [%]", f"{start_do_percent:.2f}")
    tcol2.metric("Target DO2 [%]", f"{target_source_do_percent:.2f}")
    if reached_target and target_time_s is not None:
        tcol3.metric("Estimated time to target [min]", f"{target_time_s / 60.0:.1f}")
        tcol4.metric("Status", "Target reachable")
    else:
        tcol3.metric("Estimated time to target [min]", "Not reached (8 h)")
        tcol4.metric("Status", "Check gas/perfusion settings")
    st.caption(
        f"Predicted source DO after 8 h max window: {final_pred_do_percent:.2f}%. "
        "Assumption: source vessel is perfectly mixed and recirculates through tubing."
    )
    if reached_target and target_time_s is not None:
        source_plot_t_end_s = max(float(target_time_s) * 1.05, 60.0)
    else:
        source_plot_t_end_s = 8.0 * 3600.0
    source_vessel_df = _simulate_source_vessel_do_timeseries(
        inputs=inputs,
        do_ref_o2_mmol_l=do_ref_o2_mmol_l,
        t_end_s=source_plot_t_end_s,
        dt_s=inputs.dt_s,
    )
    source_chart = (
        alt.Chart(source_vessel_df)
        .mark_line()
        .encode(
            x=alt.X("time_min:Q", title="Time [min]"),
            y=alt.Y("source_do2_percent:Q", title="Source vessel DO2 [%]"),
            tooltip=[
                alt.Tooltip("time_min:Q", title="Time [min]", format=".2f"),
                alt.Tooltip("source_do2_percent:Q", title="DO2 [%]", format=".2f"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(source_chart, use_container_width=True)
    st.caption("Source-vessel plot is adaptively downsampled for performance on long time windows.")

    st.markdown("### Export")
    excel_bytes = _build_excel_bytes(outputs.time_s, outputs.c_o2_mmol_l, outputs.c_n2_mmol_l)
    source_vessel_excel_bytes = _build_source_vessel_excel_bytes(source_vessel_df)
    metadata = {
        "inputs": asdict(inputs),
        "outputs_summary": {
            "n_steps": int(len(outputs.time_s)),
            "cstar_o2_mmol_l": float(outputs.cstar_o2_mmol_l),
            "cstar_n2_mmol_l": float(outputs.cstar_n2_mmol_l),
            "final_c_o2_mmol_l": float(outputs.c_o2_mmol_l[-1]),
            "final_c_n2_mmol_l": float(outputs.c_n2_mmol_l[-1]),
            "do_reference_o2_mmol_l": float(do_ref_o2_mmol_l),
            "final_do_o2_percent": float(do_percent[-1]),
            "o2_outflow_mmol_min": float(o2_outlet_rate_mmol_min),
            "o2_net_added_mmol_min": float(o2_added_rate_mmol_min),
        },
        "pressure_context": pressure_context,
        "metadata": outputs.metadata,
    }
    metadata_json = json.dumps(metadata, indent=2, sort_keys=True)

    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "Download Timeseries Excel",
        data=excel_bytes,
        file_name="carboxysim_timeseries.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    c2.download_button(
        "Download Source Vessel Excel",
        data=source_vessel_excel_bytes,
        file_name="carboxysim_source_vessel_do.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    c3.download_button(
        "Download Metadata JSON",
        data=metadata_json,
        file_name="carboxysim_metadata.json",
        mime="application/json",
    )

    st.markdown("### Flow Sweep")
    st.caption("Single-pass outlet concentration as a function of flow rate.")
    fcol1, fcol2, fcol3 = st.columns(3)
    sweep_min = fcol1.number_input("flow_min [mL/min]", min_value=0.001, value=2.0, step=0.5)
    sweep_max = fcol2.number_input("flow_max [mL/min]", min_value=0.001, value=20.0, step=0.5)
    sweep_points = int(fcol3.number_input("flow_points [-]", min_value=2, value=10, step=1))

    if sweep_min >= sweep_max:
        st.warning("flow_min must be smaller than flow_max for sweep plot.")
        return

    flows = np.linspace(sweep_min, sweep_max, sweep_points)
    sweep_rows = []
    for flow in flows:
        sweep_p_total_kpa, sweep_delta_p_mbar = _pressure_from_mode(
            pressure_mode=pressure_context["pressure_mode"],
            gas_flow_ml_min=float(flow),
            p_atm_kpa=float(pressure_context["p_atm_kpa"]),
            p_total_manual_kpa=inputs.p_total_kpa if pressure_context["pressure_mode"] == "Manual" else None,
        )
        sweep_inputs = replace(inputs, flow_ml_min=float(flow))
        sweep_inputs = replace(sweep_inputs, p_total_kpa=float(sweep_p_total_kpa))
        sweep_outputs = simulate(sweep_inputs, constant_solubility_model)
        c_out_o2 = float(sweep_outputs.c_o2_mmol_l[-1])
        c_out_n2 = float(sweep_outputs.c_n2_mmol_l[-1])
        sweep_flow_l_min = float(flow) / 1000.0
        o2_outflow_mmol_min = c_out_o2 * sweep_flow_l_min
        o2_net_added_mmol_min = (c_out_o2 - sweep_inputs.c_o2_init_mmol_l) * sweep_flow_l_min
        sweep_rows.append(
            {
                "flow_ml_min": float(flow),
                "do_o2_out_percent": float((c_out_o2 / do_ref_o2_mmol_l) * 100.0),
                "c_o2_out_mmol_l": c_out_o2,
                "c_n2_out_mmol_l": c_out_n2,
                "o2_outflow_mmol_min": float(o2_outflow_mmol_min),
                "o2_net_added_mmol_min": float(o2_net_added_mmol_min),
                "delta_p_mbar": float(sweep_delta_p_mbar),
                "p_total_kpa": float(sweep_p_total_kpa),
            }
        )

    sweep_df = pd.DataFrame(sweep_rows).sort_values("flow_ml_min")

    do_chart = (
        alt.Chart(sweep_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("flow_ml_min:Q", title="Flow [mL/min]"),
            y=alt.Y("do_o2_out_percent:Q", title="DO outlet [%]"),
        )
        .properties(height=280)
    )
    st.altair_chart(do_chart, use_container_width=True)

    throughput_df = sweep_df.melt(
        id_vars=["flow_ml_min"],
        value_vars=["o2_outflow_mmol_min", "o2_net_added_mmol_min"],
        var_name="series",
        value_name="value",
    )
    throughput_chart = (
        alt.Chart(throughput_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("flow_ml_min:Q", title="Flow [mL/min]"),
            y=alt.Y("value:Q", title="O2 throughput [mmol/min]"),
            color=alt.Color("series:N", title="Series"),
        )
        .properties(height=320)
    )
    st.altair_chart(throughput_chart, use_container_width=True)

    sweep_do_values = sweep_df["do_o2_out_percent"].tolist()
    sweep_o2_net_values = sweep_df["o2_net_added_mmol_min"].tolist()
    scol1, scol2 = st.columns(2)
    scol1.metric("Sweep DO range [%]", f"{min(sweep_do_values):.2f} to {max(sweep_do_values):.2f}")
    scol2.metric(
        "Sweep net O2 range [mmol/min]",
        f"{min(sweep_o2_net_values):.6f} to {max(sweep_o2_net_values):.6f}",
    )

    st.markdown("### Summary")
    col1, col2 = st.columns(2)
    col1.metric("final DO [%]", f"{do_percent[-1]:.2f}")
    col2.metric("DO reference c_o2 [mmol/L]", f"{do_ref_o2_mmol_l:.6f}")
    col1.metric("final c_o2 [mmol/L]", f"{outputs.c_o2_mmol_l[-1]:.6f}")
    col2.metric("final c_n2 [mmol/L]", f"{outputs.c_n2_mmol_l[-1]:.6f}")
    col1.metric("pressure_mode", str(pressure_context["pressure_mode"]))
    col2.metric("delta_p [mbar]", f"{float(pressure_context['delta_p_mbar']):.1f}")
    col1.metric("tube_volume_ml [mL]", f"{float(outputs.metadata['tube_volume_ml']):.3f}")
    col2.metric("transfer_residence_time_min [min]", f"{float(outputs.metadata['residence_time_s']) / 60.0:.2f}")
    col1.metric("annulus_volume_ml [mL]", f"{float(outputs.metadata['annulus_volume_ml']):.3f}")
    col2.metric("gas_residence_time_min [min]", f"{float(outputs.metadata['gas_residence_time_s']) / 60.0:.2f}")
    col1.metric("transport_volume_ml [mL]", f"{float(outputs.metadata['transport_volume_ml']):.3f}")
    col2.metric("transport_delay_min [min]", f"{float(outputs.metadata['transport_delay_s']) / 60.0:.2f}")
    col1.metric("k_eff_o2 [1/s]", f"{float(outputs.metadata['effective_kla_o2_s_inv']):.4e}")
    col2.metric("k_eff_n2 [1/s]", f"{float(outputs.metadata['effective_kla_n2_s_inv']):.4e}")
    col1.metric("Gas-liquid model", str(outputs.metadata["gas_liquid_model"]))
    col2.metric("n_segments", f"{int(outputs.metadata['n_segments'])}")
    col1.metric("O2 gas supply [mmol/min]", f"{float(outputs.metadata['o2_supply_rate_mmol_min']):.6f}")
    col2.metric("O2 transfer limited", "Yes" if bool(outputs.metadata["o2_transfer_limited"]) else "No")
    col1.metric("O2 outflow [mmol/min]", f"{o2_outlet_rate_mmol_min:.6f}")
    col2.metric("Net O2 added [mmol/min]", f"{o2_added_rate_mmol_min:.6f}")


if __name__ == "__main__":
    main()
