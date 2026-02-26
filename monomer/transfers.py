"""Transfer array generation and composition helpers.

Pure computation — no workcell communication. Generates liquid-handling
transfer arrays for gradient descent media optimization experiments.
"""

from __future__ import annotations

from copy import deepcopy

# Default plate layout constants
ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]

ROW_LABELS = {
    "A": "control",
    "B": "center",
    "C": "glucose_rep1",
    "D": "glucose_rep2",
    "E": "nacl_rep1",
    "F": "nacl_rep2",
    "G": "mgso4_rep1",
    "H": "mgso4_rep2",
}

# Default reagent well map (24-well deep well, modeled as 96-well)
REAGENT_WELLS = {
    "Glucose": "A1",
    "NaCl": "B1",
    "MgSO4": "C1",
    "Novel_Bio": "D1",
}

SUPPLEMENT_NAMES = ["Glucose", "NaCl", "MgSO4"]

# Volume constraints
WELL_VOLUME_UL = 180
MIN_SUPPLEMENT_UL = 1
MAX_SUPPLEMENT_UL = 90
MIN_NOVEL_BIO_UL = 90

# Default algorithm parameters
DELTA_UL = 10

# Novel_Bio well is the only one that reuses tips
REUSE_TIP_SOURCE_WELLS = [REAGENT_WELLS["Novel_Bio"]]


# ---------------------------------------------------------------------------
# Composition helpers
# ---------------------------------------------------------------------------


def compute_novel_bio(supplements: dict, well_volume: int = WELL_VOLUME_UL) -> int:
    """Compute Novel_Bio volume to fill remaining well volume."""
    return well_volume - sum(supplements.values())


def apply_constraints(
    supplements: dict,
    supplement_names: list[str] = SUPPLEMENT_NAMES,
    min_ul: int = MIN_SUPPLEMENT_UL,
    max_ul: int = MAX_SUPPLEMENT_UL,
    min_novel_bio: int = MIN_NOVEL_BIO_UL,
    well_volume: int = WELL_VOLUME_UL,
    delta: int = DELTA_UL,
) -> dict:
    """Apply volume constraints to a supplement composition.

    Rules:
    - Each supplement in {0} union [min_ul, max_ul]
    - All values are integers
    - Novel_Bio must be >= min_novel_bio
    - Sum of all components = well_volume
    """
    result = {}
    for name in supplement_names:
        vol = int(round(supplements.get(name, 0)))
        if vol < min_ul:
            vol = 0
        vol = min(vol, max_ul)
        result[name] = vol

    # Ensure Novel_Bio >= min_novel_bio
    novel_bio = compute_novel_bio(result, well_volume)
    while novel_bio < min_novel_bio:
        largest = max(supplement_names, key=lambda n: result[n])
        if result[largest] <= 0:
            break
        result[largest] = max(0, result[largest] - delta)
        novel_bio = compute_novel_bio(result, well_volume)

    return result


def make_perturbed(center: dict, supplement_name: str, delta: int) -> dict:
    """Create a perturbed composition: center + delta on one axis."""
    perturbed = deepcopy(center)
    perturbed[supplement_name] = center[supplement_name] + delta
    return apply_constraints(perturbed)


# ---------------------------------------------------------------------------
# Transfer array generation
# ---------------------------------------------------------------------------


def generate_transfer_array(
    center: dict,
    column_index: int,
    delta: int = DELTA_UL,
    reagent_wells: dict = REAGENT_WELLS,
    supplement_names: list[str] = SUPPLEMENT_NAMES,
) -> list:
    """Generate a transfer array for one iteration (8 wells in 1 column).

    Returns: [[source_well, dest_well, volume_uL], ...]

    Row layout:
      A: Control (180 uL Novel_Bio)
      B: Center point
      C: +delta Glucose (rep 1)
      D: +delta Glucose (rep 2)
      E: +delta NaCl (rep 1)
      F: +delta NaCl (rep 2)
      G: +delta MgSO4 (rep 1)
      H: +delta MgSO4 (rep 2)
    """
    transfers = []
    col = column_index

    # Row A: Control — 180 uL Novel_Bio
    transfers.append([reagent_wells["Novel_Bio"], f"A{col}", WELL_VOLUME_UL])

    # Row B: Center point
    novel_bio_center = compute_novel_bio(center)
    if novel_bio_center > 0:
        transfers.append([reagent_wells["Novel_Bio"], f"B{col}", novel_bio_center])
    for name in supplement_names:
        if center[name] > 0:
            transfers.append([reagent_wells[name], f"B{col}", center[name]])

    # Rows C-H: Perturbations (2 reps each for 3 supplements)
    perturbation_rows = [
        ("C", "D", "Glucose"),
        ("E", "F", "NaCl"),
        ("G", "H", "MgSO4"),
    ]

    for row1, row2, supplement in perturbation_rows:
        perturbed = make_perturbed(center, supplement, delta)
        novel_bio_pert = compute_novel_bio(perturbed)

        for row in (row1, row2):
            if novel_bio_pert > 0:
                transfers.append(
                    [reagent_wells["Novel_Bio"], f"{row}{col}", novel_bio_pert]
                )
            for name in supplement_names:
                if perturbed[name] > 0:
                    transfers.append(
                        [reagent_wells[name], f"{row}{col}", perturbed[name]]
                    )

    # Sort: Novel_Bio first (largest volume, tip reuse), then supplements smallest-to-last.
    # This groups all Novel_Bio transfers together so only one tip change is needed.
    source_order = [
        reagent_wells["Novel_Bio"],
        reagent_wells["MgSO4"],
        reagent_wells["NaCl"],
        reagent_wells["Glucose"],
    ]
    order_map = {well: i for i, well in enumerate(source_order)}
    transfers.sort(key=lambda t: order_map.get(t[0], 99))

    return transfers


def compute_tip_consumption(
    transfer_array: list,
    reuse_source_wells: list[str] | None = None,
) -> dict:
    """Compute tip consumption for hybrid tip mode.

    Novel_Bio (D1): 1 tip reused for all transfers (grouped by pipette type).
    All other source wells: 1 new tip per transfer.
    """
    if reuse_source_wells is None:
        reuse_source_wells = REUSE_TIP_SOURCE_WELLS
    reuse_set = set(reuse_source_wells)

    reuse_by_pipette: dict[str, set] = {"p50": set(), "p200": set(), "p1000": set()}
    single_counts = {"p50": 0, "p200": 0, "p1000": 0}

    for source_well, _, volume in transfer_array:
        if volume <= 50:
            pip = "p50"
        elif volume <= 200:
            pip = "p200"
        else:
            pip = "p1000"

        if source_well in reuse_set:
            reuse_by_pipette[pip].add(source_well)
        else:
            single_counts[pip] += 1

    return {
        "p50": len(reuse_by_pipette["p50"]) + single_counts["p50"],
        "p200": len(reuse_by_pipette["p200"]) + single_counts["p200"],
        "p1000": len(reuse_by_pipette["p1000"]) + single_counts["p1000"],
    }
