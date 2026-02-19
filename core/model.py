"""Core physical model helpers."""

from collections.abc import Callable
import math

from .params import SimulationInputs

SolubilityModel = Callable[[str, float], float]


def constant_solubility_model(species: str, temperature_c: float) -> float:
    """Return constant Henry-like coefficients in mmol/(L*kPa)."""

    # Temperature dependence is deferred to later versions.
    _ = temperature_c
    constants = {
        "O2": 0.0128,
        "N2": 0.0061,
        "CO2": 0.0307,
    }
    if species not in constants:
        raise ValueError(f"Unsupported species: {species}")
    return constants[species]


def compute_equilibrium_concentrations(
    inputs: SimulationInputs,
    solubility_model: SolubilityModel,
) -> tuple[float, float]:
    """Compute equilibrium concentrations for O2 and N2 in mmol/L."""

    p_o2_kpa = inputs.y_o2 * inputs.p_total_kpa
    p_n2_kpa = inputs.y_n2 * inputs.p_total_kpa

    s_o2 = solubility_model("O2", inputs.temperature_c)
    s_n2 = solubility_model("N2", inputs.temperature_c)

    cstar_o2 = s_o2 * p_o2_kpa
    cstar_n2 = s_n2 * p_n2_kpa
    return cstar_o2, cstar_n2


def compute_tube_volume_ml(tube_id_mm: float, tube_length_cm: float) -> float:
    """Compute tubing liquid hold-up volume in mL."""

    radius_cm = (tube_id_mm / 10.0) / 2.0
    return math.pi * (radius_cm**2) * tube_length_cm


def compute_residence_time_s(flow_ml_min: float, tube_volume_ml: float) -> float:
    """Compute tubing residence time in seconds."""

    return (tube_volume_ml / flow_ml_min) * 60.0


def compute_annulus_volume_ml(shell_id_mm: float, tube_od_mm: float, tube_length_cm: float) -> float:
    """Compute gas annulus hold-up volume in mL."""

    shell_radius_cm = (shell_id_mm / 10.0) / 2.0
    tube_od_radius_cm = (tube_od_mm / 10.0) / 2.0
    return math.pi * ((shell_radius_cm**2) - (tube_od_radius_cm**2)) * tube_length_cm


def compute_gas_o2_supply_rate_mmol_min(
    gas_flow_ml_min: float,
    y_o2: float,
    p_total_kpa: float,
    temperature_c: float,
) -> float:
    """Compute incoming O2 molar flow from gas stream in mmol/min."""

    temperature_k = temperature_c + 273.15
    r_kpa_l_per_mol_k = 8.314462618
    gas_concentration_mmol_l = (p_total_kpa / (r_kpa_l_per_mol_k * temperature_k)) * 1000.0
    return (gas_flow_ml_min / 1000.0) * y_o2 * gas_concentration_mmol_l


def compute_single_pass_outlet_concentration(
    c_in_mmol_l: float,
    cstar_mmol_l: float,
    kla_s_inv: float,
    residence_time_s: float,
) -> float:
    """Compute outlet concentration for plug-flow mass transfer."""

    return cstar_mmol_l + (c_in_mmol_l - cstar_mmol_l) * math.exp(-kla_s_inv * residence_time_s)


def compute_two_stage_co2_outlet_concentration(
    c_co2_in_mmol_l: float,
    cstar_co2_stage1_mmol_l: float,
    cstar_co2_stage2_mmol_l: float,
    kla_co2_s_inv: float,
    residence_time_stage1_s: float,
    residence_time_stage2_s: float,
) -> tuple[float, float]:
    """Compute CO2 outlet over two serial stages (upstream pH stage, then O2 stage)."""

    c_after_stage1 = compute_single_pass_outlet_concentration(
        c_in_mmol_l=c_co2_in_mmol_l,
        cstar_mmol_l=cstar_co2_stage1_mmol_l,
        kla_s_inv=kla_co2_s_inv,
        residence_time_s=residence_time_stage1_s,
    )
    c_after_stage2 = compute_single_pass_outlet_concentration(
        c_in_mmol_l=c_after_stage1,
        cstar_mmol_l=cstar_co2_stage2_mmol_l,
        kla_s_inv=kla_co2_s_inv,
        residence_time_s=residence_time_stage2_s,
    )
    return c_after_stage1, c_after_stage2


def compute_bicarbonate_buffer_ph(
    hco3_mmol_l: float,
    c_co2_mmol_l: float,
    pka_app: float = 6.1,
) -> float:
    """Compute pH from bicarbonate buffer using Henderson-Hasselbalch in concentration form."""

    if hco3_mmol_l <= 0.0:
        raise ValueError("hco3_mmol_l must be > 0 for bicarbonate pH calculation")
    if c_co2_mmol_l <= 0.0:
        c_co2_mmol_l = 1e-12
    return pka_app + math.log10(hco3_mmol_l / c_co2_mmol_l)


def compute_effective_kla_from_permeability(
    species: str,
    inputs: SimulationInputs,
    solubility_model: SolubilityModel,
) -> float:
    """Convert tubing permeability parameters into an effective first-order transfer rate."""

    tube_od_mm = inputs.tube_od_mm_override_mm if inputs.tube_od_mm_override_mm is not None else inputs.tube_od_mm
    if tube_od_mm <= inputs.tube_id_mm:
        raise ValueError("tube_od_mm must be greater than tube_id_mm in permeability mode")

    perm = {
        "O2": inputs.perm_o2_mmol_m_per_m2_s_kpa,
        "N2": inputs.perm_n2_mmol_m_per_m2_s_kpa,
        "CO2": inputs.perm_co2_mmol_m_per_m2_s_kpa,
    }.get(species)
    if perm is None:
        raise ValueError(f"Permeability missing for species: {species}")

    tube_id_m = inputs.tube_id_mm / 1000.0
    tube_od_m = tube_od_mm / 1000.0
    tube_length_m = inputs.tube_length_cm / 100.0

    wall_thickness_m = (tube_od_m - tube_id_m) / 2.0
    area_m2 = math.pi * tube_od_m * tube_length_m
    volume_m3 = compute_tube_volume_ml(inputs.tube_id_mm, inputs.tube_length_cm) * 1e-6
    solubility_mmol_per_m3_kpa = solubility_model(species, inputs.temperature_c) * 1000.0

    mass_transfer_rate = (perm / wall_thickness_m) * (area_m2 / volume_m3)
    return mass_transfer_rate / solubility_mmol_per_m3_kpa
