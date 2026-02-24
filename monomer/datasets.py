"""Dataset helpers for fetching OD600 absorbance results from the workcell.

Uses both MCP (for plate UUID lookup) and REST API (for dataset queries).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from monomer.mcp_client import McpClient

# REST API headers (ClientIdentifierMiddleware requires desktop-frontend)
API_HEADERS = {
    "Content-Type": "application/json",
    "X-Monomer-Client": "desktop-frontend",
}

ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]
SUPPLEMENT_NAMES = ["Glucose", "NaCl", "MgSO4"]


def get_plate_uuid(client: McpClient, plate_barcode: str) -> str:
    """Look up a culture plate's UUID from its barcode via MCP."""
    plates = client.call_tool("list_culture_plates", {})
    for p in plates:
        if p.get("barcode") == plate_barcode:
            return p.get("uuid", "")
    raise RuntimeError(f"Plate '{plate_barcode}' not found on workcell")


def fetch_absorbance_results(
    client: McpClient,
    plate_barcode: str,
    column_index: int,
    rows: list[str] = ROWS,
) -> dict:
    """Fetch OD600 readings for a plate: both baseline (earliest) and endpoint (latest).

    Queries the datasets REST API (camelCase response), filters by plate UUID
    and OD600 wavelength, and extracts well values for the target column.

    Returns::

        {
            "baseline": {well: od600_value},   # First reading (pre-growth)
            "endpoint": {well: od600_value},   # Latest reading (post-growth)
        }
    """
    plate_uuid = get_plate_uuid(client, plate_barcode)

    # Fetch all datasets, ordered newest first
    resp = requests.get(
        f"{client.base_url}/api/datasets/",
        headers=API_HEADERS,
        params={"verbose": "1", "ordering": "-createdAt"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    datasets = data.get("results", data) if isinstance(data, dict) else data

    # Filter for OD600 datasets matching our plate UUID
    absorbance_datasets = []
    for ds in datasets:
        meta = ds.get("metadata", {})
        rm = meta.get("resultMetadata", {})
        pm = meta.get("plateMetadata", {})
        if rm.get("measurementWavelength") == 600 and pm.get("uuid") == plate_uuid:
            absorbance_datasets.append(ds)

    if not absorbance_datasets:
        raise RuntimeError(f"No OD600 datasets found for plate {plate_barcode}")

    # Collect timestamps that have data for our target column wells
    target_wells = [f"{row}{column_index}" for row in rows]
    column_readings: dict[str, dict] = {}
    for ds in absorbance_datasets:
        sd = ds.get("structuredData", {})
        results = sd.get("resultsByWell", {})
        for ts, wells in results.items():
            if any(wells.get(w) for w in target_wells):
                column_readings[ts] = wells

    if not column_readings:
        raise RuntimeError(
            f"No OD600 readings found for column {column_index} wells "
            f"on plate {plate_barcode}"
        )

    sorted_timestamps = sorted(column_readings.keys())
    earliest_well_data = column_readings[sorted_timestamps[0]]
    latest_well_data = column_readings[sorted_timestamps[-1]]

    # Extract the 8 wells in our target column for both timepoints
    baseline = {}
    endpoint = {}
    for row in rows:
        well = f"{row}{column_index}"
        baseline[well] = float(earliest_well_data.get(well, 0.0))
        endpoint[well] = float(latest_well_data.get(well, 0.0))

    return {"baseline": baseline, "endpoint": endpoint}


def parse_od_results(
    absorbance_results: dict,
    column_index: int,
    rows: list[str] = ROWS,
    supplement_names: list[str] = SUPPLEMENT_NAMES,
) -> dict:
    """Parse baseline + endpoint absorbance into growth deltas for gradient computation.

    Uses delta OD (endpoint - baseline) as the objective function, which normalizes
    for varying initial cell densities across wells.

    Returns::

        {
            "control_od": float,       # delta OD for control well
            "center_od": float,        # delta OD for center well
            "perturbed_ods": {supplement: [rep1_delta, rep2_delta]},
            "abs_control_od": float,   # absolute endpoint (for logging)
            "abs_center_od": float,    # absolute endpoint (for logging)
        }
    """
    col = column_index
    baseline = absorbance_results.get("baseline", {})
    endpoint = absorbance_results.get("endpoint", {})

    def delta(well: str) -> float:
        return endpoint.get(well, 0.0) - baseline.get(well, 0.0)

    control_delta = delta(f"A{col}")
    center_delta = delta(f"B{col}")

    # Rows C/D, E/F, G/H map to the three supplements
    perturbed_deltas = {}
    row_pairs = [("C", "D"), ("E", "F"), ("G", "H")]
    for (r1, r2), name in zip(row_pairs, supplement_names):
        perturbed_deltas[name] = [delta(f"{r1}{col}"), delta(f"{r2}{col}")]

    return {
        "control_od": control_delta,
        "center_od": center_delta,
        "perturbed_ods": perturbed_deltas,
        "abs_control_od": endpoint.get(f"A{col}", 0.0),
        "abs_center_od": endpoint.get(f"B{col}", 0.0),
    }
