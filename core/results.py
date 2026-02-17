"""Simulation result data structures."""

from dataclasses import dataclass
from dataclasses import asdict
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .params import SimulationInputs


@dataclass(frozen=True, slots=True)
class SimulationOutputs:
    time_s: np.ndarray
    c_o2_mmol_l: np.ndarray
    c_n2_mmol_l: np.ndarray
    cstar_o2_mmol_l: float
    cstar_n2_mmol_l: float
    metadata: dict[str, Any]


def export_csv(outputs: SimulationOutputs, path: str | Path) -> None:
    """Export simulation timeseries to CSV with deterministic column order."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", "c_o2_mmol_l", "c_n2_mmol_l"])
        for idx in range(len(outputs.time_s)):
            writer.writerow(
                [
                    f"{outputs.time_s[idx]:.12g}",
                    f"{outputs.c_o2_mmol_l[idx]:.12g}",
                    f"{outputs.c_n2_mmol_l[idx]:.12g}",
                ]
            )


def export_metadata_json(
    inputs: SimulationInputs,
    outputs: SimulationOutputs,
    path: str | Path,
) -> None:
    """Export simulation inputs/results metadata to JSON."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "inputs": asdict(inputs),
        "outputs_summary": {
            "n_steps": int(len(outputs.time_s)),
            "cstar_o2_mmol_l": outputs.cstar_o2_mmol_l,
            "cstar_n2_mmol_l": outputs.cstar_n2_mmol_l,
            "final_c_o2_mmol_l": float(outputs.c_o2_mmol_l[-1]),
            "final_c_n2_mmol_l": float(outputs.c_n2_mmol_l[-1]),
        },
        "metadata": outputs.metadata,
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
