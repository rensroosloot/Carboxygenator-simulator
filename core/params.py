"""Input schema and validation for CarboxySim."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationInputs:
    y_o2: float
    y_n2: float
    p_total_kpa: float
    temperature_c: float
    volume_l: float
    flow_ml_min: float
    tube_id_mm: float
    tube_od_mm: float
    shell_id_mm: float
    tube_length_cm: float
    gas_flow_ml_min: float
    kla_o2_s_inv: float
    kla_n2_s_inv: float
    c_o2_init_mmol_l: float
    c_n2_init_mmol_l: float
    t_end_s: float
    dt_s: float
    transfer_model: str = "kla"
    tube_od_mm_override_mm: float | None = None
    perm_o2_mmol_m_per_m2_s_kpa: float | None = None
    perm_n2_mmol_m_per_m2_s_kpa: float | None = None
    gas_liquid_model: str = "lumped"
    n_segments: int = 40
    total_hold_up_volume_ml: float | None = None
    enable_co2_ph_stage: bool = False
    ph_tube_length_cm: float = 16.0
    ph_gas_co2_percent: float = 5.0
    ph_gas_flow_ml_min: float = 20.0
    kla_co2_s_inv: float = 0.05416666666666667
    co2_transfer_model: str = "kla"
    perm_co2_mmol_m_per_m2_s_kpa: float | None = None
    c_co2_init_mmol_l: float = 1.2
    hco3_mmol_l: float = 24.0
    pka_app: float = 6.1
    reverse_ph_do_flow: bool = False


def validate_inputs(inputs: SimulationInputs) -> None:
    """Validate simulation inputs and raise ValueError on failures."""

    errors: list[str] = []

    if not (0.0 <= inputs.y_o2 <= 1.0):
        errors.append("y_o2 must be between 0 and 1")
    if not (0.0 <= inputs.y_n2 <= 1.0):
        errors.append("y_n2 must be between 0 and 1")
    if abs((inputs.y_o2 + inputs.y_n2) - 1.0) > 1e-9:
        errors.append("y_o2 + y_n2 must equal 1 within tolerance 1e-9")

    if inputs.p_total_kpa <= 0.0:
        errors.append("p_total_kpa must be > 0")
    if inputs.volume_l <= 0.0:
        errors.append("volume_l must be > 0")
    if inputs.flow_ml_min <= 0.0:
        errors.append("flow_ml_min must be > 0")
    if inputs.tube_id_mm <= 0.0:
        errors.append("tube_id_mm must be > 0")
    if inputs.tube_od_mm <= inputs.tube_id_mm:
        errors.append("tube_od_mm must be greater than tube_id_mm")
    if inputs.shell_id_mm <= inputs.tube_od_mm:
        errors.append("shell_id_mm must be greater than tube_od_mm")
    if inputs.tube_length_cm <= 0.0:
        errors.append("tube_length_cm must be > 0")
    if inputs.gas_flow_ml_min <= 0.0:
        errors.append("gas_flow_ml_min must be > 0")
    if inputs.total_hold_up_volume_ml is not None and inputs.total_hold_up_volume_ml <= 0.0:
        errors.append("total_hold_up_volume_ml must be > 0 when provided")
    if inputs.t_end_s <= 0.0:
        errors.append("t_end_s must be > 0")
    if inputs.dt_s <= 0.0:
        errors.append("dt_s must be > 0")
    if inputs.dt_s > inputs.t_end_s:
        errors.append("dt_s must be <= t_end_s")

    if inputs.kla_o2_s_inv < 0.0:
        errors.append("kla_o2_s_inv must be >= 0")
    if inputs.kla_n2_s_inv < 0.0:
        errors.append("kla_n2_s_inv must be >= 0")
    if inputs.kla_co2_s_inv < 0.0:
        errors.append("kla_co2_s_inv must be >= 0")
    if inputs.c_o2_init_mmol_l < 0.0:
        errors.append("c_o2_init_mmol_l must be >= 0")
    if inputs.c_n2_init_mmol_l < 0.0:
        errors.append("c_n2_init_mmol_l must be >= 0")
    if inputs.c_co2_init_mmol_l < 0.0:
        errors.append("c_co2_init_mmol_l must be >= 0")
    if inputs.hco3_mmol_l <= 0.0:
        errors.append("hco3_mmol_l must be > 0")
    if not (0.0 <= inputs.ph_gas_co2_percent <= 100.0):
        errors.append("ph_gas_co2_percent must be between 0 and 100")
    if inputs.ph_gas_flow_ml_min <= 0.0:
        errors.append("ph_gas_flow_ml_min must be > 0")
    if inputs.ph_tube_length_cm <= 0.0:
        errors.append("ph_tube_length_cm must be > 0")

    if inputs.transfer_model not in {"kla", "permeability"}:
        errors.append("transfer_model must be either 'kla' or 'permeability'")
    if inputs.co2_transfer_model not in {"kla", "permeability"}:
        errors.append("co2_transfer_model must be either 'kla' or 'permeability'")
    if inputs.gas_liquid_model not in {"lumped", "segmented"}:
        errors.append("gas_liquid_model must be either 'lumped' or 'segmented'")
    if inputs.gas_liquid_model == "segmented" and inputs.n_segments < 2:
        errors.append("n_segments must be >= 2 when gas_liquid_model='segmented'")

    if inputs.transfer_model == "permeability":
        if inputs.tube_od_mm_override_mm is not None and inputs.tube_od_mm_override_mm <= inputs.tube_id_mm:
            errors.append("tube_od_mm_override_mm must be greater than tube_id_mm in permeability mode")
        if inputs.perm_o2_mmol_m_per_m2_s_kpa is None:
            errors.append("perm_o2_mmol_m_per_m2_s_kpa is required for permeability mode")
        elif inputs.perm_o2_mmol_m_per_m2_s_kpa < 0.0:
            errors.append("perm_o2_mmol_m_per_m2_s_kpa must be >= 0")
        if inputs.perm_n2_mmol_m_per_m2_s_kpa is None:
            errors.append("perm_n2_mmol_m_per_m2_s_kpa is required for permeability mode")
        elif inputs.perm_n2_mmol_m_per_m2_s_kpa < 0.0:
            errors.append("perm_n2_mmol_m_per_m2_s_kpa must be >= 0")
    if inputs.co2_transfer_model == "permeability":
        if inputs.perm_co2_mmol_m_per_m2_s_kpa is None:
            errors.append("perm_co2_mmol_m_per_m2_s_kpa is required for co2_transfer_model='permeability'")
        elif inputs.perm_co2_mmol_m_per_m2_s_kpa < 0.0:
            errors.append("perm_co2_mmol_m_per_m2_s_kpa must be >= 0")

    if errors:
        raise ValueError("; ".join(errors))
