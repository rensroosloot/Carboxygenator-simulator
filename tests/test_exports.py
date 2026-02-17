import csv
import json

from core.model import constant_solubility_model
from core.params import SimulationInputs
from core.results import export_csv, export_metadata_json
from core.solver import simulate


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


def test_ac007_export_integrity_csv_and_metadata_json(tmp_path) -> None:
    inputs = _baseline_inputs()
    outputs = simulate(inputs, constant_solubility_model)

    csv_path = tmp_path / "run.csv"
    json_path = tmp_path / "run_metadata.json"
    export_csv(outputs, csv_path)
    export_metadata_json(inputs, outputs, json_path)

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["time_s", "c_o2_mmol_l", "c_n2_mmol_l"]
    assert len(rows) == len(outputs.time_s) + 1

    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "inputs" in payload
    assert "outputs_summary" in payload
    assert "metadata" in payload
    assert payload["inputs"]["y_o2"] == inputs.y_o2
    assert payload["outputs_summary"]["n_steps"] == len(outputs.time_s)
