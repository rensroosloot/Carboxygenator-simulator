"""Streamlit UI for CarboxySim MVP."""

from __future__ import annotations

import csv
from collections import deque
from dataclasses import replace
from dataclasses import asdict
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

# Ensure repository-root imports work when Streamlit runs `ui/app.py` directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import (
    SimulationInputs,
    compute_bicarbonate_buffer_ph,
    compute_effective_kla_from_permeability,
    compute_gas_o2_supply_rate_mmol_min,
    compute_single_pass_steady_outlet,
    compute_tube_volume_ml,
    compute_two_stage_co2_outlet_concentration,
    compute_equilibrium_concentrations,
    constant_solubility_model,
    simulate,
    validate_inputs,
)


def _default_inputs() -> SimulationInputs:
    co2_to_o2_perm_ratio = 3250.0 / 600.0
    barrer_to_mmol_m_per_m2_s_kpa = 3.35e-10
    return SimulationInputs(
        y_o2=1.00,
        y_n2=0.00,
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
        enable_co2_ph_stage=False,
        ph_tube_length_cm=16.0,
        ph_gas_co2_percent=99.0,
        ph_gas_flow_ml_min=20.0,
        kla_co2_s_inv=0.01 * co2_to_o2_perm_ratio,
        co2_transfer_model="permeability",
        perm_co2_mmol_m_per_m2_s_kpa=3250.0 * barrer_to_mmol_m_per_m2_s_kpa,
        c_co2_init_mmol_l=1.2,
        hco3_mmol_l=24.0,
        pka_app=6.1,
        reverse_ph_do_flow=False,
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
    last_error: Exception | None = None
    for engine in ("xlsxwriter", "openpyxl"):
        try:
            with pd.ExcelWriter(output, engine=engine) as writer:
                df.to_excel(writer, sheet_name="timeseries", index=False)
            return output.getvalue()
        except ModuleNotFoundError as exc:
            last_error = exc
            output = io.BytesIO()
    if last_error is not None:
        raise RuntimeError("No Excel writer engine available (xlsxwriter/openpyxl).") from last_error
    return output.getvalue()


def _build_source_vessel_excel_bytes(source_vessel_df: pd.DataFrame) -> bytes:
    """Build XLSX export bytes for source-vessel DO trajectory."""

    output = io.BytesIO()
    last_error: Exception | None = None
    for engine in ("xlsxwriter", "openpyxl"):
        try:
            with pd.ExcelWriter(output, engine=engine) as writer:
                source_vessel_df.to_excel(writer, sheet_name="source_vessel_do", index=False)
            return output.getvalue()
        except ModuleNotFoundError as exc:
            last_error = exc
            output = io.BytesIO()
    if last_error is not None:
        raise RuntimeError("No Excel writer engine available (xlsxwriter/openpyxl).") from last_error
    return output.getvalue()


def _build_pdf_report_bytes(
    inputs: SimulationInputs,
    outputs,
    pressure_context: dict,
    do_ref_o2_mmol_l: float,
    do_percent: np.ndarray,
    o2_outlet_rate_mmol_min: float,
    o2_added_rate_mmol_min: float,
    source_vessel_df: pd.DataFrame,
    sweep_df: pd.DataFrame,
    target_source_do_percent: float,
) -> bytes:
    """Build a multi-page PDF report with settings, assumptions, and all key datasets."""

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.graphics.charts.lineplots import LinePlot
        from reportlab.graphics.shapes import Drawing, Rect, String
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ModuleNotFoundError as exc:
        raise RuntimeError("PDF export unavailable: missing 'reportlab'.") from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    c_bg = colors.HexColor("#0b1220")
    c_card = colors.HexColor("#121a2b")
    c_header = colors.HexColor("#1f2a44")
    c_text = colors.HexColor("#e6edf3")
    c_muted = colors.HexColor("#9fb0c3")
    c_accent = colors.HexColor("#5bc0ff")
    c_grid = colors.HexColor("#2c3b5c")

    style_title = ParagraphStyle(
        "PdfTitle",
        parent=styles["Title"],
        textColor=c_text,
        fontSize=22,
        alignment=TA_LEFT,
    )
    style_h2 = ParagraphStyle(
        "PdfH2",
        parent=styles["Heading2"],
        textColor=c_text,
        fontSize=14,
        spaceAfter=6,
    )
    style_body = ParagraphStyle(
        "PdfBody",
        parent=styles["Normal"],
        textColor=c_muted,
        fontSize=9,
        leading=12,
    )
    story = []

    def _downsample_xy(x_vals: list[float], y_vals: list[float], max_points: int = 300) -> list[tuple[float, float]]:
        if len(x_vals) <= max_points:
            return [(float(x), float(y)) for x, y in zip(x_vals, y_vals)]
        idx = np.linspace(0, len(x_vals) - 1, max_points, dtype=int)
        return [(float(x_vals[i]), float(y_vals[i])) for i in idx]

    def _line_plot_drawing(
        title: str,
        x_label: str,
        y_label: str,
        x_vals: list[float],
        y_vals: list[float],
        x_fmt: str = "%.1f",
        y_fmt: str = "%.2f",
    ) -> Drawing:
        points = _downsample_xy(x_vals, y_vals)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min = min(xs) if xs else 0.0
        x_max = max(xs) if xs else 1.0
        y_min = min(ys) if ys else 0.0
        y_max = max(ys) if ys else 1.0
        if abs(x_max - x_min) < 1e-12:
            x_max = x_min + 1.0
        if abs(y_max - y_min) < 1e-12:
            y_max = y_min + 1.0

        drawing = Drawing(540, 240)
        drawing.add(Rect(0, 0, 540, 240, fillColor=c_card, strokeColor=c_grid, strokeWidth=0.6))
        drawing.add(String(270, 225, title, textAnchor="middle", fontSize=11, fillColor=c_text))
        drawing.add(String(270, 12, x_label, textAnchor="middle", fontSize=8, fillColor=c_muted))
        drawing.add(String(12, 120, y_label, fontSize=8, angle=90, fillColor=c_muted))

        plot = LinePlot()
        plot.x = 50
        plot.y = 35
        plot.width = 470
        plot.height = 165
        plot.data = [points]
        plot.lines[0].strokeColor = c_accent
        plot.lines[0].strokeWidth = 1.8
        plot.xValueAxis.valueMin = x_min
        plot.xValueAxis.valueMax = x_max
        plot.yValueAxis.valueMin = y_min
        plot.yValueAxis.valueMax = y_max
        plot.xValueAxis.valueStep = (x_max - x_min) / 5.0
        plot.yValueAxis.valueStep = (y_max - y_min) / 5.0
        plot.xValueAxis.labelTextFormat = x_fmt
        plot.yValueAxis.labelTextFormat = y_fmt
        plot.xValueAxis.strokeColor = c_grid
        plot.yValueAxis.strokeColor = c_grid
        plot.xValueAxis.labels.fillColor = c_muted
        plot.yValueAxis.labels.fillColor = c_muted
        plot.xValueAxis.labels.fontSize = 7
        plot.yValueAxis.labels.fontSize = 7
        drawing.add(plot)
        return drawing

    story.append(Paragraph("CarboxySim Report", style_title))
    story.append(
        Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            style_body,
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Model assumptions: single-pass tubing transfer, constant gas composition/pressure/temperature, no PBS reactions.",
            style_body,
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("Key Graphs", style_h2))
    story.append(
        _line_plot_drawing(
            title="Source Vessel DO2 vs Time",
            x_label="Time [min]",
            y_label="Source DO2 [%]",
            x_vals=[float(v) for v in source_vessel_df["time_min"].tolist()],
            y_vals=[float(v) for v in source_vessel_df["source_do2_percent"].tolist()],
            x_fmt="%.1f",
            y_fmt="%.1f",
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        _line_plot_drawing(
            title="Flow Sweep: Outlet DO2 vs Flow",
            x_label="Flow [mL/min]",
            y_label="Outlet DO2 [%]",
            x_vals=[float(v) for v in sweep_df["flow_ml_min"].tolist()],
            y_vals=[float(v) for v in sweep_df["do_o2_out_percent"].tolist()],
            x_fmt="%.1f",
            y_fmt="%.1f",
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        _line_plot_drawing(
            title="Flow Sweep: Net O2 Added vs Flow",
            x_label="Flow [mL/min]",
            y_label="Net O2 [mmol/min]",
            x_vals=[float(v) for v in sweep_df["flow_ml_min"].tolist()],
            y_vals=[float(v) for v in sweep_df["o2_net_added_mmol_min"].tolist()],
            x_fmt="%.1f",
            y_fmt="%.4f",
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Input Settings (Detailed)", style_h2))
    setting_explanations = {
        "O2 gas fraction y_o2 [-]": "Fraction of oxygen in gas phase. N2 is set as 1 - y_o2.",
        "N2 gas fraction y_n2 [-]": "Fraction of nitrogen in gas phase.",
        "Total gas pressure p_total_kpa [kPa]": "Absolute gas pressure used with Henry-law equilibrium.",
        "Temperature [C]": "Liquid temperature for solubility reference.",
        "Source vessel volume [L]": "Well-mixed vessel volume for recirculation estimate.",
        "Perfusion speed flow_ml_min [mL/min]": "Liquid flow through tubing.",
        "Total hold-up volume [mL]": "Total loop liquid volume to measurement point; sets transport delay.",
        "Tube ID [mm]": "Inner diameter of exchange tubing.",
        "Tube OD [mm]": "Outer diameter of exchange tubing.",
        "Shell ID [mm]": "Inner diameter of surrounding shell for annulus gas volume.",
        "Tube length [cm]": "Effective exchange length.",
        "Gas flow [mL/min]": "Total gas flow available for O2/N2 supply.",
        "Transfer model": "kLa uses direct transfer coefficients; permeability derives effective transfer.",
        "kLa O2 [1/s]": "First-order transfer rate to O2 equilibrium (kLa mode).",
        "kLa N2 [1/s]": "First-order transfer rate to N2 equilibrium (kLa mode).",
        "Permeability O2 [mmol*m/(m2*s*kPa)]": "Wall permeability coefficient for O2 (permeability mode).",
        "Permeability N2 [mmol*m/(m2*s*kPa)]": "Wall permeability coefficient for N2 (permeability mode).",
        "CO2 transfer model": "CO2 uses either direct kLa or permeability-derived effective transfer.",
        "kLa CO2 [1/s]": "First-order transfer rate used when CO2 transfer model is kLa.",
        "Permeability CO2 [mmol*m/(m2*s*kPa)]": "Wall permeability coefficient for CO2 when CO2 transfer model is permeability.",
        "Gas-liquid model": "Lumped uses one gas composition; segmented updates depletion along length.",
        "n_segments [-]": "Number of axial segments in segmented mode.",
        "Inlet DO2 [%]": "Starting dissolved oxygen in incoming liquid, relative to air/1atm reference.",
        "Inlet N2 [%]": "Starting dissolved nitrogen relative to air/1atm reference.",
        "Target source DO2 [%]": "Target DO in source vessel for time-to-target estimate.",
        "Simulation horizon [min]": "Output time window.",
        "Time step [min]": "Output sampling interval.",
    }
    settings_rows = [
        ["Setting", "Value", "Explanation"],
        ["O2 gas fraction y_o2 [-]", f"{inputs.y_o2:.6f}", setting_explanations["O2 gas fraction y_o2 [-]"]],
        ["N2 gas fraction y_n2 [-]", f"{inputs.y_n2:.6f}", setting_explanations["N2 gas fraction y_n2 [-]"]],
        ["Total gas pressure p_total_kpa [kPa]", f"{inputs.p_total_kpa:.3f}", setting_explanations["Total gas pressure p_total_kpa [kPa]"]],
        ["Temperature [C]", f"{inputs.temperature_c:.2f}", setting_explanations["Temperature [C]"]],
        ["Source vessel volume [L]", f"{inputs.volume_l:.3f}", setting_explanations["Source vessel volume [L]"]],
        ["Perfusion speed flow_ml_min [mL/min]", f"{inputs.flow_ml_min:.3f}", setting_explanations["Perfusion speed flow_ml_min [mL/min]"]],
        ["Total hold-up volume [mL]", f"{float(outputs.metadata.get('transport_volume_ml', 0.0)):.3f}", setting_explanations["Total hold-up volume [mL]"]],
        ["Tube ID [mm]", f"{inputs.tube_id_mm:.3f}", setting_explanations["Tube ID [mm]"]],
        ["Tube OD [mm]", f"{inputs.tube_od_mm:.3f}", setting_explanations["Tube OD [mm]"]],
        ["Shell ID [mm]", f"{inputs.shell_id_mm:.3f}", setting_explanations["Shell ID [mm]"]],
        ["Tube length [cm]", f"{inputs.tube_length_cm:.2f}", setting_explanations["Tube length [cm]"]],
        ["Gas flow [mL/min]", f"{inputs.gas_flow_ml_min:.3f}", setting_explanations["Gas flow [mL/min]"]],
        ["Transfer model", str(inputs.transfer_model), setting_explanations["Transfer model"]],
        ["kLa O2 [1/s]", f"{inputs.kla_o2_s_inv:.6g}", setting_explanations["kLa O2 [1/s]"]],
        ["kLa N2 [1/s]", f"{inputs.kla_n2_s_inv:.6g}", setting_explanations["kLa N2 [1/s]"]],
        [
            "Permeability O2 [mmol*m/(m2*s*kPa)]",
            "n/a" if inputs.perm_o2_mmol_m_per_m2_s_kpa is None else f"{inputs.perm_o2_mmol_m_per_m2_s_kpa:.3e}",
            setting_explanations["Permeability O2 [mmol*m/(m2*s*kPa)]"],
        ],
        [
            "Permeability N2 [mmol*m/(m2*s*kPa)]",
            "n/a" if inputs.perm_n2_mmol_m_per_m2_s_kpa is None else f"{inputs.perm_n2_mmol_m_per_m2_s_kpa:.3e}",
            setting_explanations["Permeability N2 [mmol*m/(m2*s*kPa)]"],
        ],
        ["CO2 transfer model", str(inputs.co2_transfer_model), setting_explanations["CO2 transfer model"]],
        ["kLa CO2 [1/s]", f"{inputs.kla_co2_s_inv:.6g}", setting_explanations["kLa CO2 [1/s]"]],
        [
            "Permeability CO2 [mmol*m/(m2*s*kPa)]",
            "n/a" if inputs.perm_co2_mmol_m_per_m2_s_kpa is None else f"{inputs.perm_co2_mmol_m_per_m2_s_kpa:.3e}",
            setting_explanations["Permeability CO2 [mmol*m/(m2*s*kPa)]"],
        ],
        ["Gas-liquid model", str(inputs.gas_liquid_model), setting_explanations["Gas-liquid model"]],
        ["n_segments [-]", f"{int(inputs.n_segments)}", setting_explanations["n_segments [-]"]],
        ["Inlet DO2 [%]", f"{(inputs.c_o2_init_mmol_l / max(do_ref_o2_mmol_l, 1e-15)) * 100.0:.3f}", setting_explanations["Inlet DO2 [%]"]],
        [
            "Inlet N2 [%]",
            f"{(inputs.c_n2_init_mmol_l / max(constant_solubility_model('N2', inputs.temperature_c) * 0.79 * 101.325, 1e-15)) * 100.0:.3f}",
            setting_explanations["Inlet N2 [%]"],
        ],
        ["Target source DO2 [%]", f"{target_source_do_percent:.3f}", setting_explanations["Target source DO2 [%]"]],
        ["Simulation horizon [min]", f"{inputs.t_end_s / 60.0:.3f}", setting_explanations["Simulation horizon [min]"]],
        ["Time step [min]", f"{inputs.dt_s / 60.0:.5f}", setting_explanations["Time step [min]"]],
    ]
    settings_table = Table(settings_rows, repeatRows=1, colWidths=[170, 90, 270])
    settings_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_header),
                ("BACKGROUND", (0, 1), (-1, -1), c_card),
                ("TEXTCOLOR", (0, 0), (-1, -1), c_text),
                ("GRID", (0, 0), (-1, -1), 0.25, c_grid),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(settings_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Run Summary", style_h2))
    summary_rows = [
        ["Metric", "Value"],
        ["Final DO2 [%]", f"{float(do_percent[-1]):.3f}"],
        ["Final c_o2 [mmol/L]", f"{float(outputs.c_o2_mmol_l[-1]):.6f}"],
        ["Final c_n2 [mmol/L]", f"{float(outputs.c_n2_mmol_l[-1]):.6f}"],
        ["Pressure model", str(pressure_context.get("pressure_mode", "Manual"))],
        ["Delta p [mbar]", f"{float(pressure_context.get('delta_p_mbar', 0.0)):.3f}"],
        ["Transfer residence time [min]", f"{float(outputs.metadata['residence_time_s']) / 60.0:.3f}"],
        ["Transport delay [min]", f"{float(outputs.metadata.get('transport_delay_s', 0.0)) / 60.0:.3f}"],
        ["O2 outflow [mmol/min]", f"{o2_outlet_rate_mmol_min:.6f}"],
        ["Net O2 added [mmol/min]", f"{o2_added_rate_mmol_min:.6f}"],
    ]
    summary_table = Table(summary_rows, repeatRows=1, colWidths=[220, 140])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_header),
                ("BACKGROUND", (0, 1), (-1, -1), c_card),
                ("TEXTCOLOR", (0, 0), (-1, -1), c_text),
                ("GRID", (0, 0), (-1, -1), 0.25, c_grid),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(summary_table)
    story.append(PageBreak())

    story.append(Paragraph("Flow Sweep Data (All Rows)", style_h2))
    sw_rows = [
        [
            "flow_ml_min",
            "do_o2_out_percent",
            "c_o2_out_mmol_l",
            "c_n2_out_mmol_l",
            "o2_outflow_mmol_min",
            "o2_net_added_mmol_min",
            "delta_p_mbar",
            "p_total_kpa",
        ]
    ]
    for row in sweep_df.itertuples(index=False):
        sw_rows.append(
            [
                f"{float(row.flow_ml_min):.5f}",
                f"{float(row.do_o2_out_percent):.6f}",
                f"{float(row.c_o2_out_mmol_l):.8f}",
                f"{float(row.c_n2_out_mmol_l):.8f}",
                f"{float(row.o2_outflow_mmol_min):.8f}",
                f"{float(row.o2_net_added_mmol_min):.8f}",
                f"{float(row.delta_p_mbar):.5f}",
                f"{float(row.p_total_kpa):.5f}",
            ]
        )
    sw_table = Table(sw_rows, repeatRows=1, colWidths=[65, 70, 75, 75, 75, 75, 65, 65])
    sw_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_header),
                ("BACKGROUND", (0, 1), (-1, -1), c_card),
                ("TEXTCOLOR", (0, 0), (-1, -1), c_text),
                ("GRID", (0, 0), (-1, -1), 0.2, c_grid),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(sw_table)

    def _draw_page(canvas, doc_) -> None:
        canvas.saveState()
        canvas.setFillColor(c_bg)
        canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        canvas.setFillColor(c_muted)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(A4[0] - 20, 12, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()


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


def _compute_two_stage_co2_outlet(inputs: SimulationInputs, c_co2_in_mmol_l: float) -> dict[str, float]:
    """Compute dissolved CO2 at pH stage, DO stage, and final outlet according to selected stage order."""

    kla_co2_eff_s_inv = (
        compute_effective_kla_from_permeability("CO2", inputs, constant_solubility_model)
        if inputs.co2_transfer_model == "permeability"
        else inputs.kla_co2_s_inv
    )
    co2_sol = constant_solubility_model("CO2", inputs.temperature_c)
    stage2_tube_volume_ml = compute_tube_volume_ml(inputs.tube_id_mm, inputs.tube_length_cm)
    stage2_tau_s = (stage2_tube_volume_ml / max(inputs.flow_ml_min, 1e-15)) * 60.0
    stage1_tube_volume_ml = compute_tube_volume_ml(inputs.tube_id_mm, inputs.ph_tube_length_cm)
    stage1_tau_s = (stage1_tube_volume_ml / max(inputs.flow_ml_min, 1e-15)) * 60.0
    y_co2_stage1 = inputs.ph_gas_co2_percent / 100.0
    cstar_stage1 = co2_sol * y_co2_stage1 * inputs.p_total_kpa

    def _apply_ph_stage(c_in: float) -> float:
        if not inputs.enable_co2_ph_stage:
            return c_in
        c_after, _ = compute_two_stage_co2_outlet_concentration(
            c_co2_in_mmol_l=c_in,
            cstar_co2_stage1_mmol_l=cstar_stage1,
            cstar_co2_stage2_mmol_l=cstar_stage1,
            kla_co2_s_inv=kla_co2_eff_s_inv,
            residence_time_stage1_s=stage1_tau_s,
            residence_time_stage2_s=0.0,
        )
        co2_supply_rate_mmol_min = compute_gas_o2_supply_rate_mmol_min(
            gas_flow_ml_min=inputs.ph_gas_flow_ml_min,
            y_o2=y_co2_stage1,
            p_total_kpa=inputs.p_total_kpa,
            temperature_c=inputs.temperature_c,
        )
        co2_required_rate_mmol_min = max(
            0.0,
            (c_after - c_in) * (inputs.flow_ml_min / 1000.0),
        )
        if co2_required_rate_mmol_min > co2_supply_rate_mmol_min:
            max_co2_delta_c = co2_supply_rate_mmol_min / max((inputs.flow_ml_min / 1000.0), 1e-15)
            c_after = c_in + max_co2_delta_c
        return c_after

    def _apply_do_stage(c_in: float) -> float:
        # Existing O2 section assumes no CO2 feed in gas, so this stage strips dissolved CO2.
        _, c_after = compute_two_stage_co2_outlet_concentration(
            c_co2_in_mmol_l=c_in,
            cstar_co2_stage1_mmol_l=0.0,
            cstar_co2_stage2_mmol_l=0.0,
            kla_co2_s_inv=kla_co2_eff_s_inv,
            residence_time_stage1_s=0.0,
            residence_time_stage2_s=stage2_tau_s,
        )
        return c_after

    if inputs.reverse_ph_do_flow:
        c_after_do = _apply_do_stage(c_co2_in_mmol_l)
        c_after_ph = _apply_ph_stage(c_after_do)
        c_final = c_after_ph
    else:
        c_after_ph = _apply_ph_stage(c_co2_in_mmol_l)
        c_after_do = _apply_do_stage(c_after_ph)
        c_final = c_after_do

    return {
        "co2_after_ph_part_mmol_l": float(c_after_ph),
        "co2_after_do_part_mmol_l": float(c_after_do),
        "co2_final_outlet_mmol_l": float(c_final),
    }


def _simulate_source_vessel_ph_timeseries(
    inputs: SimulationInputs,
    t_end_s: float,
    dt_s: float,
) -> pd.DataFrame:
    """Simulate source-vessel dissolved CO2 and pH with optional upstream CO2 conditioning."""

    max_points = 1200
    eff_dt_s = max(dt_s, t_end_s / max_points)
    n_steps = int(np.floor(t_end_s / eff_dt_s)) + 1
    time_s = np.arange(n_steps, dtype=float) * eff_dt_s

    q_l_min = inputs.flow_ml_min / 1000.0
    vessel_volume_l = max(inputs.volume_l, 1e-15)
    c_co2 = float(inputs.c_co2_init_mmol_l)

    transport_volume_ml = (
        float(inputs.total_hold_up_volume_ml)
        if inputs.total_hold_up_volume_ml is not None
        else compute_tube_volume_ml(inputs.tube_id_mm, inputs.tube_length_cm)
    )
    transport_delay_s = (transport_volume_ml / max(inputs.flow_ml_min, 1e-15)) * 60.0
    delay_steps = max(0, int(round(transport_delay_s / max(eff_dt_s, 1e-12))))
    out_hist_co2: deque[float] = deque([c_co2] * (delay_steps + 1), maxlen=delay_steps + 1)

    rows = [
        {
            "time_s": 0.0,
            "time_min": 0.0,
            "source_co2_mmol_l": c_co2,
            "source_ph": compute_bicarbonate_buffer_ph(
                hco3_mmol_l=inputs.hco3_mmol_l,
                c_co2_mmol_l=c_co2,
                pka_app=inputs.pka_app,
            ),
        }
    ]
    dt_min = eff_dt_s / 60.0

    for step in range(1, n_steps):
        co2_stage_result = _compute_two_stage_co2_outlet(inputs=inputs, c_co2_in_mmol_l=c_co2)
        c_co2_out = float(co2_stage_result["co2_final_outlet_mmol_l"])
        delayed_out_co2 = out_hist_co2[0]
        out_hist_co2.append(c_co2_out)

        dc_co2_dt = (q_l_min / vessel_volume_l) * (delayed_out_co2 - c_co2)
        c_co2 += dc_co2_dt * dt_min

        t_s = float(time_s[step])
        rows.append(
            {
                "time_s": t_s,
                "time_min": t_s / 60.0,
                "source_co2_mmol_l": c_co2,
                "source_ph": compute_bicarbonate_buffer_ph(
                    hco3_mmol_l=inputs.hco3_mmol_l,
                    c_co2_mmol_l=c_co2,
                    pka_app=inputs.pka_app,
                ),
            }
        )

    return pd.DataFrame(rows)


def _compute_co2_stage_segment_profiles(
    inputs: SimulationInputs,
    c_co2_in_mmol_l: float,
    n_segments: int,
) -> dict[str, list[float] | bool]:
    """Compute segmented counterflow profiles for the upstream CO2 conditioning stage."""

    nseg = max(2, int(n_segments))
    tube_volume_ml = compute_tube_volume_ml(inputs.tube_id_mm, inputs.ph_tube_length_cm)
    residence_time_s = (tube_volume_ml / max(inputs.flow_ml_min, 1e-15)) * 60.0
    dt_seg_s = residence_time_s / nseg
    kla_co2_eff_s_inv = (
        compute_effective_kla_from_permeability("CO2", inputs, constant_solubility_model)
        if inputs.co2_transfer_model == "permeability"
        else inputs.kla_co2_s_inv
    )
    a_co2 = 1.0 - np.exp(-kla_co2_eff_s_inv * dt_seg_s)

    temperature_k = inputs.temperature_c + 273.15
    r_kpa_l_per_mol_k = 8.314462618
    gas_conc_mmol_l = (inputs.p_total_kpa / (r_kpa_l_per_mol_k * temperature_k)) * 1000.0
    y_co2_inlet = inputs.ph_gas_co2_percent / 100.0
    total_gas_mmol_min = (inputs.ph_gas_flow_ml_min / 1000.0) * gas_conc_mmol_l
    n_co2_inlet_mmol_min = total_gas_mmol_min * y_co2_inlet
    n_other_inlet_mmol_min = total_gas_mmol_min * (1.0 - y_co2_inlet)
    q_liq_l_min = inputs.flow_ml_min / 1000.0
    sol_co2 = constant_solubility_model("CO2", inputs.temperature_c)

    # Gas interfaces indexed left->right, gas inlet at right boundary (counterflow).
    iface_co2 = [n_co2_inlet_mmol_min for _ in range(nseg + 1)]
    iface_other = [n_other_inlet_mmol_min for _ in range(nseg + 1)]
    c_liq = [0.0 for _ in range(nseg + 1)]
    c_liq[0] = c_co2_in_mmol_l

    limited_hit = False
    for _ in range(50):
        prev_iface_co2 = iface_co2.copy()
        c_liq[0] = c_co2_in_mmol_l
        tr_co2 = [0.0 for _ in range(nseg)]

        for seg in range(nseg):
            gas_co2_in = prev_iface_co2[seg + 1]
            gas_other_in = iface_other[seg + 1]
            gas_total_in = max(gas_co2_in + gas_other_in, 1e-15)
            y_co2_local = max(0.0, min(1.0, gas_co2_in / gas_total_in))
            cstar_local = sol_co2 * y_co2_local * inputs.p_total_kpa

            dc_co2 = (cstar_local - c_liq[seg]) * a_co2
            seg_tr_co2 = dc_co2 * q_liq_l_min

            # Gas-to-liquid absorption cannot exceed available upstream CO2 gas flow in segment.
            if seg_tr_co2 > gas_co2_in:
                limited_hit = True
                seg_tr_co2 = gas_co2_in
                dc_co2 = seg_tr_co2 / max(q_liq_l_min, 1e-15)

            tr_co2[seg] = seg_tr_co2
            c_liq[seg + 1] = c_liq[seg] + dc_co2

        iface_co2[nseg] = n_co2_inlet_mmol_min
        iface_other[nseg] = n_other_inlet_mmol_min
        for seg in range(nseg - 1, -1, -1):
            iface_co2[seg] = max(0.0, iface_co2[seg + 1] - tr_co2[seg])
            iface_other[seg] = iface_other[seg + 1]

        diff = max(abs(a - b) for a, b in zip(iface_co2, prev_iface_co2))
        if diff < 1e-9:
            break

    gas_profile_cstar_co2 = []
    for seg in range(nseg):
        gtot = max(iface_co2[seg + 1] + iface_other[seg + 1], 1e-15)
        y_co2_seg = iface_co2[seg + 1] / gtot
        gas_profile_cstar_co2.append(sol_co2 * y_co2_seg * inputs.p_total_kpa)
    liq_profile_ph = [
        compute_bicarbonate_buffer_ph(
            hco3_mmol_l=inputs.hco3_mmol_l,
            c_co2_mmol_l=max(c_val, 1e-12),
            pka_app=inputs.pka_app,
        )
        for c_val in c_liq
    ]

    return {
        "liq_profile_co2_mmol_l": [float(v) for v in c_liq],
        "gas_profile_cstar_co2_mmol_l": [float(v) for v in gas_profile_cstar_co2],
        "liq_profile_ph": [float(v) for v in liq_profile_ph],
        "co2_transfer_limited": limited_hit,
    }


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
        enable_co2_ph_stage = st.checkbox(
            "Enable upstream CO2 pH stage",
            value=defaults.enable_co2_ph_stage,
            help="Optional 16 cm (default) section before O2 tubing for bicarbonate pH conditioning with CO2.",
        )
        reverse_ph_do_flow = st.checkbox(
            "Reverse pH/DO stage order",
            value=defaults.reverse_ph_do_flow,
            help="When enabled, CO2/pH calculations apply DO section first, then pH section (DO output feeds pH part).",
        )
        ph_tube_length_cm = st.number_input(
            "ph_tube_length_cm [cm]",
            min_value=0.001,
            value=defaults.ph_tube_length_cm,
            step=1.0,
            disabled=(not enable_co2_ph_stage),
            help="Length of upstream CO2 conditioning tubing section.",
        )
        ph_gas_co2_percent = st.number_input(
            "ph_gas_co2_percent [%]",
            min_value=0.0,
            max_value=100.0,
            value=defaults.ph_gas_co2_percent,
            step=0.5,
            disabled=(not enable_co2_ph_stage),
            help="CO2 fraction in gas used for upstream pH-conditioning section.",
        )
        ph_gas_flow_ml_min = st.number_input(
            "ph_gas_flow_ml_min [mL/min]",
            min_value=0.001,
            value=defaults.ph_gas_flow_ml_min,
            step=1.0,
            disabled=(not enable_co2_ph_stage),
            help="Gas flow for upstream CO2-conditioning section.",
        )
        co2_transfer_model_ui = st.selectbox(
            "CO2 transfer model",
            options=["Permeability", "kLa"],
            index=0 if defaults.co2_transfer_model == "permeability" else 1,
            help="Choose permeability-based CO2 transfer (with Barrer/SI input) or direct kLa input.",
        )
        co2_transfer_model = "permeability" if co2_transfer_model_ui == "Permeability" else "kla"
        if co2_transfer_model == "permeability":
            co2_perm_unit = st.selectbox(
                "CO2 permeability unit",
                options=["Barrer", "mmol*m/(m2*s*kPa)"],
                index=0,
                help="Choose the unit used by your CO2 tubing permeability source.",
            )
            if co2_perm_unit == "Barrer":
                perm_co2_barrer = st.number_input(
                    "perm_co2 [Barrer]",
                    min_value=0.0,
                    value=3250.0,
                    step=50.0,
                    help="CO2 permeability benchmark/reference in Barrer.",
                )
                barrer_to_mmol_m_per_m2_s_kpa = 3.35e-10
                perm_co2 = perm_co2_barrer * barrer_to_mmol_m_per_m2_s_kpa
            else:
                perm_co2 = st.number_input(
                    "perm_co2 [mmol*m/(m2*s*kPa)]",
                    min_value=0.0,
                    value=float(defaults.perm_co2_mmol_m_per_m2_s_kpa or (3250.0 * 3.35e-10)),
                    step=1.0e-8,
                    format="%.3e",
                    help="CO2 permeability coefficient in SI-like unit.",
                )
            st.caption(f"Converted CO2 permeability: {perm_co2:.3e} mmol*m/(m2*s*kPa)")
            kla_co2_s_inv = defaults.kla_co2_s_inv
        else:
            kla_co2_s_inv = st.number_input(
                "kla_co2_s_inv [1/s]",
                min_value=0.0,
                value=defaults.kla_co2_s_inv,
                step=0.001,
                format="%.6f",
                help="CO2 transfer coefficient used for pH-conditioning and downstream CO2 stripping.",
            )
            perm_co2 = None
        hco3_mmol_l = st.number_input(
            "hco3_mmol_l [mmol/L]",
            min_value=0.0001,
            value=defaults.hco3_mmol_l,
            step=1.0,
            help="Bicarbonate buffer concentration used for Henderson-Hasselbalch pH estimate.",
        )
        pka_app = st.number_input(
            "pka_app [-]",
            min_value=0.0,
            value=defaults.pka_app,
            step=0.05,
            help="Apparent pKa used in pH = pKa + log10([HCO3-]/[CO2*]).",
        )
        inlet_ph = st.number_input(
            "inlet_ph [-]",
            min_value=0.0,
            max_value=14.0,
            value=7.40,
            step=0.05,
            help="Initial source-vessel pH converted to dissolved CO2 via Henderson-Hasselbalch.",
        )
        c_co2_init_mmol_l = hco3_mmol_l / max(10.0 ** (inlet_ph - pka_app), 1e-12)
        st.caption("Dissolved CO2 is derived internally from inlet pH and bicarbonate.")
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
        st.caption("Cell oxygen demand inputs")
        total_cells = st.number_input(
            "total_cells [-]",
            min_value=0.0,
            value=2.7e9,
            step=1.0e8,
            format="%.3e",
            help="Total number of cells in the culture system.",
        )
        q_o2_cell_e17 = st.number_input(
            "q_o2_cell [x1e-17 mol/cell/s]",
            min_value=0.0,
            value=5.0,
            step=0.5,
            help="Average cellular O2 uptake rate. 5 corresponds to 5e-17 mol/cell/s.",
        )
        o2_demand_margin = st.number_input(
            "o2_demand_margin_factor [-]",
            min_value=1.0,
            value=1.0,
            step=0.1,
            help="Safety factor on cellular O2 demand (e.g. 1.2 for 20% margin).",
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
                    value=280.0,
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
    st.write("- Optional bicarbonate pH estimate uses Henderson-Hasselbalch with fixed [HCO3-] and pKa")
    st.write("- CO2 in downstream O2 section is assumed absent in gas phase (CO2 stripping driver)")

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
        enable_co2_ph_stage=enable_co2_ph_stage,
        ph_tube_length_cm=ph_tube_length_cm,
        ph_gas_co2_percent=ph_gas_co2_percent,
        ph_gas_flow_ml_min=ph_gas_flow_ml_min,
        kla_co2_s_inv=kla_co2_s_inv,
        co2_transfer_model=co2_transfer_model,
        perm_co2_mmol_m_per_m2_s_kpa=perm_co2,
        c_co2_init_mmol_l=c_co2_init_mmol_l,
        hco3_mmol_l=hco3_mmol_l,
        pka_app=pka_app,
        reverse_ph_do_flow=reverse_ph_do_flow,
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
    co2_stage_result = _compute_two_stage_co2_outlet(inputs=inputs, c_co2_in_mmol_l=inputs.c_co2_init_mmol_l)
    c_co2_after_ph_part_mmol_l = float(co2_stage_result["co2_after_ph_part_mmol_l"])
    c_co2_after_do_part_mmol_l = float(co2_stage_result["co2_after_do_part_mmol_l"])
    c_co2_outlet_mmol_l = float(co2_stage_result["co2_final_outlet_mmol_l"])
    inlet_ph_value = compute_bicarbonate_buffer_ph(
        hco3_mmol_l=inputs.hco3_mmol_l,
        c_co2_mmol_l=inputs.c_co2_init_mmol_l,
        pka_app=inputs.pka_app,
    )
    ph_after_stage1 = compute_bicarbonate_buffer_ph(
        hco3_mmol_l=inputs.hco3_mmol_l,
        c_co2_mmol_l=c_co2_after_ph_part_mmol_l,
        pka_app=inputs.pka_app,
    )
    ph_after_do_part = compute_bicarbonate_buffer_ph(
        hco3_mmol_l=inputs.hco3_mmol_l,
        c_co2_mmol_l=c_co2_after_do_part_mmol_l,
        pka_app=inputs.pka_app,
    )
    ph_outlet = compute_bicarbonate_buffer_ph(
        hco3_mmol_l=inputs.hco3_mmol_l,
        c_co2_mmol_l=c_co2_outlet_mmol_l,
        pka_app=inputs.pka_app,
    )

    st.markdown(
        "### Process Schematic (O2 then CO2)"
        if inputs.reverse_ph_do_flow
        else "### Process Schematic (CO2 then O2)"
    )
    if inputs.reverse_ph_do_flow:
        process_rows = [
            {
                "zone": "O2 stage",
                "x0": 0.0,
                "x1": float(inputs.tube_length_cm),
                "label": f"O2 stage ({inputs.tube_length_cm:.0f} cm)",
                "enabled": "",
            },
            {
                "zone": "Break",
                "x0": float(inputs.tube_length_cm),
                "x1": float(inputs.tube_length_cm + 8.0),
                "label": "Connection break",
                "enabled": "",
            },
            {
                "zone": "CO2 pH stage",
                "x0": float(inputs.tube_length_cm + 8.0),
                "x1": float(inputs.tube_length_cm + 8.0 + inputs.ph_tube_length_cm),
                "label": f"CO2 stage ({inputs.ph_tube_length_cm:.0f} cm)",
                "enabled": "Enabled" if inputs.enable_co2_ph_stage else "Disabled",
            },
        ]
    else:
        process_rows = [
            {
                "zone": "CO2 pH stage",
                "x0": 0.0,
                "x1": float(inputs.ph_tube_length_cm),
                "label": f"CO2 stage ({inputs.ph_tube_length_cm:.0f} cm)",
                "enabled": "Enabled" if inputs.enable_co2_ph_stage else "Disabled",
            },
            {
                "zone": "Break",
                "x0": float(inputs.ph_tube_length_cm),
                "x1": float(inputs.ph_tube_length_cm + 8.0),
                "label": "Connection break",
                "enabled": "",
            },
            {
                "zone": "O2 stage",
                "x0": float(inputs.ph_tube_length_cm + 8.0),
                "x1": float(inputs.ph_tube_length_cm + 8.0 + inputs.tube_length_cm),
                "label": f"O2 stage ({inputs.tube_length_cm:.0f} cm)",
                "enabled": "",
            },
        ]
    process_df = pd.DataFrame(process_rows)
    process_chart = (
        alt.Chart(process_df)
        .mark_rect(stroke="#202a3c", strokeWidth=1.0)
        .encode(
            x=alt.X("x0:Q", title="Axial position [cm]"),
            x2="x1:Q",
            y=alt.value(20),
            color=alt.Color(
                "zone:N",
                scale=alt.Scale(
                    domain=["CO2 pH stage", "Break", "O2 stage"],
                    range=["#1e7f6d", "#5a6375", "#2f6db0"],
                ),
                legend=alt.Legend(title="Section"),
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Section"),
                alt.Tooltip("enabled:N", title="Status"),
            ],
        )
        .properties(height=120)
    )
    st.altair_chart(process_chart, width="stretch")

    st.markdown("### Segmented Counterflow Visualization (CO2 + O2 in One Row)")
    if inputs.reverse_ph_do_flow:
        panel_col_o2, panel_col_co2 = st.columns([3, 1], gap="small")
    else:
        panel_col_co2, panel_col_o2 = st.columns([1, 3], gap="small")

    with panel_col_co2:
        st.caption(f"CO2 pH stage ({inputs.ph_tube_length_cm:.0f} cm)")
        if inputs.enable_co2_ph_stage:
            ph_in_to_ph_part = ph_after_do_part if inputs.reverse_ph_do_flow else inlet_ph_value
            co2_m1, co2_m2 = st.columns(2)
            co2_m1.metric("pH inlet", f"{ph_in_to_ph_part:.2f}")
            co2_m2.metric("pH after pH part", f"{ph_after_stage1:.2f}")
            nseg_co2 = max(2, int(round(inputs.ph_tube_length_cm)))
            co2_stage_input = c_co2_after_do_part_mmol_l if inputs.reverse_ph_do_flow else inputs.c_co2_init_mmol_l
            co2_profiles = _compute_co2_stage_segment_profiles(
                inputs=inputs,
                c_co2_in_mmol_l=co2_stage_input,
                n_segments=nseg_co2,
            )
            co2_liq_profile = co2_profiles["liq_profile_co2_mmol_l"]
            co2_gas_profile = co2_profiles["gas_profile_cstar_co2_mmol_l"]
            co2_rows = []
            for seg in range(nseg_co2):
                x0 = seg / nseg_co2
                x1 = (seg + 1) / nseg_co2
                co2_rows.append(
                    {
                        "lane": "Liquid CO2*",
                        "x0": x0,
                        "x1": x1,
                        "value": float((co2_liq_profile[seg] + co2_liq_profile[seg + 1]) * 0.5),
                    }
                )
                co2_rows.append(
                    {
                        "lane": "Gas CO2 potential C*",
                        "x0": x0,
                        "x1": x1,
                        "value": float(co2_gas_profile[seg]),
                    }
                )
            co2_df = pd.DataFrame(co2_rows)
            co2_vmin = float(co2_df["value"].min())
            co2_vmax = float(co2_df["value"].max())
            if abs(co2_vmax - co2_vmin) < 1e-12:
                co2_vmax = co2_vmin + 1.0
            co2_seg_chart = (
                alt.Chart(co2_df)
                .mark_rect()
                .encode(
                    x=alt.X("x0:Q", title="Normalized position"),
                    x2="x1:Q",
                    y=alt.Y("lane:N", title=""),
                    color=alt.Color(
                        "value:Q",
                        title="[mmol/L]",
                        scale=alt.Scale(
                            domain=[co2_vmin, co2_vmax],
                            range=["#7f1d1d", "#f97316", "#60a5fa", "#1d4ed8"],
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("lane:N", title="Lane"),
                        alt.Tooltip("value:Q", title="Value [mmol/L]", format=".4f"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(co2_seg_chart, width="stretch")
            st.caption(f"CO2* in: {co2_stage_input:.3f}, out: {c_co2_after_ph_part_mmol_l:.3f} mmol/L")
        else:
            st.info("Enable CO2 stage to show CO2 segmented counterflow.")

    with panel_col_o2:
        st.caption(f"O2 section ({inputs.tube_length_cm:.0f} cm)")
        if outputs.metadata.get("gas_liquid_model") == "segmented":
            liq_profile = outputs.metadata.get("liq_profile_o2_mmol_l", [])
            gas_profile = outputs.metadata.get("gas_profile_y_o2", [])
            if len(liq_profile) >= 2 and len(gas_profile) >= 1:
                if inputs.enable_co2_ph_stage:
                    o2_m1, o2_m2, o2_m3 = st.columns(3)
                    o2_m1.metric("DO2% inlet", f"{do_percent[0]:.2f}%")
                    o2_m2.metric("DO2% outlet", f"{do_percent[-1]:.2f}%")
                    o2_m3.metric("pH after DO part", f"{ph_after_do_part:.2f}")
                else:
                    o2_m1, o2_m2 = st.columns(2)
                    o2_m1.metric("DO2% inlet", f"{do_percent[0]:.2f}%")
                    o2_m2.metric("DO2% outlet", f"{do_percent[-1]:.2f}%")
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
                            "lane": "Liquid DO%",
                            "x0": x0,
                            "x1": x1,
                            "value": float(liq_do_seg),
                        }
                    )
                    seg_rows.append(
                        {
                            "lane": "Gas O2 potential%",
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
                        x=alt.X("x0:Q", title="Normalized position"),
                        x2="x1:Q",
                        y=alt.Y("lane:N", title=""),
                        color=alt.Color(
                            "value:Q",
                            title="[% DO eq]",
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
                st.altair_chart(seg_chart, width="stretch")
                st.caption(f"DO2 inlet: {do_percent[0]:.2f}%, outlet: {do_percent[-1]:.2f}%")
            else:
                st.info("No segmented profile data available in last run.")
        else:
            st.info("Run with `Gas-liquid coupling = Segmented depletion` to show O2 segmented counterflow.")

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
            x=alt.X("time_min:Q", title="Time [min]", axis=alt.Axis(format=".1f")),
            y=alt.Y("source_do2_percent:Q", title="Source vessel DO2 [%]", axis=alt.Axis(format=".1f")),
            tooltip=[
                alt.Tooltip("time_min:Q", title="Time [min]", format=".2f"),
                alt.Tooltip("source_do2_percent:Q", title="DO2 [%]", format=".2f"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(source_chart, width="stretch")
    st.caption("Source-vessel plot is adaptively downsampled for performance on long time windows.")

    st.markdown("### pH (Bicarbonate Buffer)")
    pcol1, pcol2, pcol3 = st.columns(3)
    pcol1.metric("Inlet pH [-]", f"{inlet_ph_value:.2f}")
    pcol2.metric("After pH part pH [-]", f"{ph_after_stage1:.2f}")
    pcol3.metric("After DO part pH [-]", f"{ph_after_do_part:.2f}")
    pcol1.metric("pH shift in pH part [-]", f"{(ph_after_stage1 - inlet_ph_value):.3f}")
    pcol2.metric("pH shift in DO part [-]", f"{(ph_after_do_part - ph_after_stage1):.3f}")
    pcol3.metric("Net pH shift inlet->outlet [-]", f"{(ph_outlet - inlet_ph_value):.3f}")
    if inputs.enable_co2_ph_stage:
        if inputs.reverse_ph_do_flow:
            st.caption(
                "Reverse order active: DO section is applied first (CO2 stripping), then pH-conditioning section "
                "(CO2 addition), so DO-stage output is used as pH-stage input."
            )
        else:
            st.caption(
                "Default order: CO2 rises in the upstream pH-conditioning section and can be stripped in the "
                "downstream O2 section because downstream gas-phase CO2 is assumed 0%."
            )
    else:
        st.caption(
            "CO2 pH stage disabled: only downstream O2 section stripping is applied to dissolved CO2."
        )

    ph_series_df = _simulate_source_vessel_ph_timeseries(
        inputs=inputs,
        t_end_s=source_plot_t_end_s,
        dt_s=inputs.dt_s,
    )
    ph_chart = (
        alt.Chart(ph_series_df)
        .mark_line(color="#86efac")
        .encode(
            x=alt.X("time_min:Q", title="Time [min]", axis=alt.Axis(format=".1f")),
            y=alt.Y("source_ph:Q", title="Source vessel pH [-]", axis=alt.Axis(format=".2f")),
            tooltip=[
                alt.Tooltip("time_min:Q", title="Time [min]", format=".2f"),
                alt.Tooltip("source_ph:Q", title="pH [-]", format=".3f"),
                alt.Tooltip("source_co2_mmol_l:Q", title="CO2* [mmol/L]", format=".4f"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(ph_chart, width="stretch")

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
            x=alt.X("flow_ml_min:Q", title="Flow [mL/min]", axis=alt.Axis(format=".1f")),
            y=alt.Y("do_o2_out_percent:Q", title="DO outlet [%]", axis=alt.Axis(format=".1f")),
        )
        .properties(height=280)
    )
    st.altair_chart(do_chart, width="stretch")

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
            x=alt.X("flow_ml_min:Q", title="Flow [mL/min]", axis=alt.Axis(format=".1f")),
            y=alt.Y("value:Q", title="O2 throughput [mmol/min]", axis=alt.Axis(format=".4f")),
            color=alt.Color("series:N", title="Series"),
        )
        .properties(height=320)
    )
    st.altair_chart(throughput_chart, width="stretch")

    sweep_do_values = sweep_df["do_o2_out_percent"].tolist()
    sweep_o2_net_values = sweep_df["o2_net_added_mmol_min"].tolist()
    scol1, scol2 = st.columns(2)
    scol1.metric("Sweep DO range [%]", f"{min(sweep_do_values):.2f} to {max(sweep_do_values):.2f}")
    scol2.metric(
        "Sweep net O2 range [mmol/min]",
        f"{min(sweep_o2_net_values):.6f} to {max(sweep_o2_net_values):.6f}",
    )

    q_o2_cell_mol_s = q_o2_cell_e17 * 1.0e-17
    o2_demand_mmol_min = total_cells * q_o2_cell_mol_s * 60.0 * 1000.0 * o2_demand_margin
    rec_row = sweep_df[sweep_df["o2_net_added_mmol_min"] >= o2_demand_mmol_min]
    st.markdown("### Cell Demand -> Perfusion Recommendation")
    r1, r2, r3 = st.columns(3)
    r1.metric("Cell O2 demand [mmol/min]", f"{o2_demand_mmol_min:.6f}")
    r2.metric("Current net O2 [mmol/min]", f"{o2_added_rate_mmol_min:.6f}")
    if not rec_row.empty:
        recommended_flow = float(rec_row.iloc[0]["flow_ml_min"])
        r3.metric("Recommended perfusion [mL/min]", f"{recommended_flow:.2f}")
        st.caption(
            "Recommendation uses the first sweep flow where net O2 addition meets/exceeds cellular demand."
        )
    else:
        r3.metric("Recommended perfusion [mL/min]", "Not in sweep range")
        st.warning(
            "Current sweep range cannot satisfy cellular O2 demand. Increase gas transfer/supply or extend flow_max."
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
    col1.metric("Inlet pH [-]", f"{inlet_ph_value:.3f}")
    col2.metric("Outlet pH [-]", f"{ph_outlet:.3f}")

    st.markdown("### Export")
    excel_available = True
    excel_error = ""
    try:
        excel_bytes = _build_excel_bytes(outputs.time_s, outputs.c_o2_mmol_l, outputs.c_n2_mmol_l)
        source_vessel_excel_bytes = _build_source_vessel_excel_bytes(source_vessel_df)
    except RuntimeError as exc:
        excel_available = False
        excel_error = str(exc)
        timeseries_csv = _build_csv_text(outputs.time_s, outputs.c_o2_mmol_l, outputs.c_n2_mmol_l)
        source_vessel_csv = source_vessel_df.to_csv(index=False)

    pdf_available = True
    pdf_error = ""
    try:
        pdf_bytes = _build_pdf_report_bytes(
            inputs=inputs,
            outputs=outputs,
            pressure_context=pressure_context,
            do_ref_o2_mmol_l=do_ref_o2_mmol_l,
            do_percent=do_percent,
            o2_outlet_rate_mmol_min=o2_outlet_rate_mmol_min,
            o2_added_rate_mmol_min=o2_added_rate_mmol_min,
            source_vessel_df=source_vessel_df,
            sweep_df=sweep_df,
            target_source_do_percent=target_source_do_percent,
        )
    except RuntimeError as exc:
        pdf_available = False
        pdf_error = str(exc)

    metadata = {
        "inputs": asdict(inputs),
        "outputs_summary": {
            "n_steps": int(len(outputs.time_s)),
            "cstar_o2_mmol_l": float(outputs.cstar_o2_mmol_l),
            "cstar_n2_mmol_l": float(outputs.cstar_n2_mmol_l),
            "final_c_o2_mmol_l": float(outputs.c_o2_mmol_l[-1]),
            "final_c_n2_mmol_l": float(outputs.c_n2_mmol_l[-1]),
            "final_c_co2_outlet_mmol_l": float(c_co2_outlet_mmol_l),
            "do_reference_o2_mmol_l": float(do_ref_o2_mmol_l),
            "final_do_o2_percent": float(do_percent[-1]),
            "final_ph_outlet": float(ph_outlet),
            "o2_outflow_mmol_min": float(o2_outlet_rate_mmol_min),
            "o2_net_added_mmol_min": float(o2_added_rate_mmol_min),
        },
        "pressure_context": pressure_context,
        "source_vessel_timeseries": source_vessel_df.to_dict(orient="records"),
        "source_vessel_ph_timeseries": ph_series_df.to_dict(orient="records"),
        "co2_ph_summary": {
            "inlet_co2_mmol_l": float(inputs.c_co2_init_mmol_l),
            "co2_after_ph_part_mmol_l": float(c_co2_after_ph_part_mmol_l),
            "co2_after_do_part_mmol_l": float(c_co2_after_do_part_mmol_l),
            "co2_outlet_mmol_l": float(c_co2_outlet_mmol_l),
            "inlet_ph": float(inlet_ph_value),
            "ph_after_ph_part": float(ph_after_stage1),
            "ph_after_do_part": float(ph_after_do_part),
            "ph_outlet": float(ph_outlet),
            "reverse_ph_do_flow": bool(inputs.reverse_ph_do_flow),
        },
        "flow_sweep": sweep_df.to_dict(orient="records"),
        "metadata": outputs.metadata,
    }
    metadata_json = json.dumps(metadata, indent=2, sort_keys=True)

    c1, c2, c3, c4 = st.columns(4)
    if excel_available:
        c1.download_button(
            "Timeseries Excel",
            data=excel_bytes,
            file_name="carboxysim_timeseries.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        c2.download_button(
            "Source Vessel Excel",
            data=source_vessel_excel_bytes,
            file_name="carboxysim_source_vessel_do.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        c1.download_button(
            "Timeseries CSV",
            data=timeseries_csv,
            file_name="carboxysim_timeseries.csv",
            mime="text/csv",
        )
        c2.download_button(
            "Source Vessel CSV",
            data=source_vessel_csv,
            file_name="carboxysim_source_vessel_do.csv",
            mime="text/csv",
        )
    if pdf_available:
        c3.download_button(
            "PDF Report",
            data=pdf_bytes,
            file_name="carboxysim_report.pdf",
            mime="application/pdf",
        )
    c4.download_button(
        "Metadata JSON",
        data=metadata_json,
        file_name="carboxysim_metadata.json",
        mime="application/json",
    )
    if not excel_available:
        st.warning(f"Excel export unavailable in this environment: {excel_error}")
    if not pdf_available:
        st.warning(f"PDF export unavailable in this environment: {pdf_error}")


if __name__ == "__main__":
    main()
