"""Hackathon closed-loop workflow definition template — Track 2A.

HOW TO USE
----------
1. Register this file ONCE at the start of your session:

       from monomer.mcp_client import McpClient
       from monomer.workflows import register_workflow

       client = McpClient("http://192.168.68.55:8080")
       def_id = register_workflow(client, Path("workflow_definition_template.py"))

2. Each iteration, instantiate it with your agent's outputs:

       from monomer.workflows import instantiate_workflow

       uuid = instantiate_workflow(
           client,
           definition_id=def_id,
           plate_barcode="GD-R1-20260314",
           extra_inputs={
               "transfer_array": json.dumps(my_transfers),
               "dest_wells":     json.dumps(["A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2"]),
               "monitoring_wells": json.dumps(all_wells_used_so_far),
               "seed_well":      "A1",
               "next_seed_well": "B1",
               "reagent_type":   "GD Compound Stock Plate",
           },
           reason="Iteration 1: testing Glucose=30µL, NaCl=20µL center",
       )

WHAT YOUR AGENT MUST PRODUCE EACH ITERATION
--------------------------------------------
  transfer_array    [[source_well, dest_well, vol_uL], ...]
                    e.g. [["D1","A2",150], ["A1","B2",20], ...]
                    Source wells are on the REAGENT plate.
                    Dest wells are on the EXPERIMENT plate.
                    Max 30 entries.

  dest_wells        JSON list of experimental wells being filled this
                    iteration (usually 8 wells in one column).
                    e.g. ["A2","B2","C2","D2","E2","F2","G2","H2"]

  monitoring_wells  JSON list of ALL wells to read via OD600 — this is
                    CUMULATIVE: include all wells from prior iterations too.
                    e.g. after 2 iterations: ["A2",...,"H2","A3",...,"H3"]

  seed_well         The warm seed well on the experiment plate for this round.
                    Starts at "A1", advances one row per iteration:
                    Iter 1 → "A1", Iter 2 → "B1", ..., Iter 8 → "H1"

  next_seed_well    The well to pre-warm for the NEXT round (seed_well + 1 row).
                    Iter 1 → "B1", Iter 2 → "C1", ..., Iter 7 → "H1"
                    Set to "" on the last iteration to skip warmup.

  reagent_type      Tag identifying your stock plate in the Monomer system.
                    Default: "GD Compound Stock Plate"
                    Custom plates: use whatever tag you registered your plate with.

PLATE LAYOUT CONVENTIONS (default GD stock plate)
--------------------------------------------------
  Reagent plate wells:
    A1 = Glucose stock
    B1 = NaCl stock
    C1 = MgSO4 stock
    D1 = Novel Bio (base media) — largest volume, 1 tip reused across all transfers
    A2 = NM+Cells (pre-mixed Novel Media + seeded cells, for next-round warmup)
    A12–H12 = single-use seed aliquots, one per iteration (pre-aliquoted at plate prep)

  Experiment plate columns:
    Col 1  = seed wells (A1–H1), one warm seed well per iteration
    Col 2  = iteration 1 results
    Col 3  = iteration 2 results
    ...
    Col 11 = iteration 10 results

IMPORTANT: WELL REUSE
---------------------
This template does NOT check for well conflicts across iterations.
Your agent is responsible for ensuring dest_wells don't overlap with
wells used in previous iterations.

The simplest approach: track dest_wells yourself in a list and append
each iteration. If you need to recover state after a restart, query
OD600 observations — wells that already have readings are occupied:

    from monomer.datasets import fetch_absorbance_results
    raw = fetch_absorbance_results(client, plate_barcode, column_index=2)
    # Any well in raw["endpoint"] has already been inoculated
"""

from __future__ import annotations

import json

from src.platform.core_domain.units import Time
from src.workflows.workflow_definition_dsl.workflow_definition_descriptor import (
    MoreThanConstraint,
    RoutineReference,
    WorkflowDefinitionDescriptor,
)

# ── Fixed protocol constants ─────────────────────────────────────────────────
# These reflect physical and biological constraints of the workcell.
# Do not change them unless you know what you're doing.

_SEED_TRANSFER_UL = 20      # µL of seed culture added to each experimental well
_SEED_MIX_VOL_UL = 100     # µL used to resuspend seed well before seeding
_SEED_MIX_REPS = 5         # pipette mix repetitions on seed well
_NM_CELLS_VOL_UL = 220     # µL of NM+Cells transferred to pre-warm next seed well
_MAX_TRANSFERS = 30         # hard cap on reagent transfer steps per iteration


# ── Internal helpers ─────────────────────────────────────────────────────────

def _compute_tip_counts(
    transfers: list[list],
    dest_well_list: list[str],
    nm_cells_volume: int,
) -> tuple[int, int, int]:
    """Compute P50 / P200 / P1000 tip consumption from the transfer array.

    Tip reuse policy: one tip per unique source well (reused across all
    transfers from that source). Seeding uses 1 P50 tip reused across all
    dest wells. Seed well mixing uses 1 P200 tip. NM+Cells warmup uses 1
    P1000 tip (skipped if nm_cells_volume == 0).

    :param transfers: Parsed transfer array [[src, dst, vol_uL], ...]
    :param dest_well_list: List of destination wells being seeded
    :param nm_cells_volume: Volume for NM+Cells warmup (0 to skip)
    :returns: (p50_tips, p200_tips, p1000_tips)
    """
    # Determine pipette for each unique source well based on max transfer volume
    source_max_vols: dict[str, float] = {}
    for src, _dst, vol in transfers:
        source_max_vols[src] = max(source_max_vols.get(src, 0.0), float(vol))

    p50 = p200 = p1000 = 0
    for max_vol in source_max_vols.values():
        if max_vol > 200:
            p1000 += 1
        elif max_vol > 50:
            p200 += 1
        else:
            p50 += 1

    # Seed well resuspension mix: always 1 P200 tip
    p200 += 1
    # Seeding dest wells: 1 P50 tip, reused for all dest wells
    if dest_well_list:
        p50 += 1
    # NM+Cells warmup: 1 P1000 tip (only when warming next seed well)
    if nm_cells_volume > 0:
        p1000 += 1

    return p50, p200, p1000


def _validate(
    transfers: list[list],
    dest_well_list: list[str],
    monitoring_well_list: list[str],
    seed_well: str,
    next_seed_well: str,
) -> None:
    """Validate iteration parameters before the workflow is built and queued.

    Raises AssertionError with a descriptive message if any constraint is
    violated. Failures here prevent bad workflows from reaching the approval
    queue.

    :param transfers: Parsed transfer array
    :param dest_well_list: Destination wells for this iteration
    :param monitoring_well_list: All wells to include in OD600 monitoring
    :param seed_well: Seed well on experiment plate
    :param next_seed_well: Next round seed well (can be empty string to skip)
    """
    assert len(transfers) <= _MAX_TRANSFERS, (
        f"Too many transfers ({len(transfers)}): max is {_MAX_TRANSFERS}. "
        "Reduce the number of conditions or reagents per iteration."
    )

    assert len(dest_well_list) > 0, (
        "dest_wells is empty. Provide at least one destination well."
    )
    assert len(dest_well_list) <= 96, (
        f"dest_wells has {len(dest_well_list)} entries — exceeds plate capacity (96)."
    )

    # Every dest well referenced in transfer_array must be listed in dest_wells
    transfer_dests = {t[1] for t in transfers}
    unlisted = transfer_dests - set(dest_well_list)
    assert not unlisted, (
        f"transfer_array references wells not in dest_wells: {sorted(unlisted)}. "
        "Add them to dest_wells or remove them from transfer_array."
    )

    assert len(monitoring_well_list) > 0, (
        "monitoring_wells is empty. Include at least the dest_wells from this iteration."
    )

    assert seed_well, "seed_well cannot be empty."
    assert seed_well not in dest_well_list, (
        f"seed_well '{seed_well}' is also listed in dest_wells — seed wells live in "
        "column 1 and should not overlap with experimental wells."
    )

    # All volumes must be positive integers
    for i, (src, dst, vol) in enumerate(transfers):
        assert isinstance(vol, (int, float)) and vol > 0, (
            f"Transfer [{i}]: volume must be a positive number, got {vol!r} "
            f"(src={src}, dst={dst})."
        )


# ── Workflow definition ──────────────────────────────────────────────────────

def build_definition(
    plate_barcode: str,
    # ── Agent outputs — set these each iteration ───────────────────────────
    transfer_array: str = "[]",
    dest_wells: str = '["A2","B2","C2","D2","E2","F2","G2","H2"]',
    monitoring_wells: str = '["A2","B2","C2","D2","E2","F2","G2","H2"]',
    # ── Seeding — advance one row per iteration ────────────────────────────
    seed_well: str = "A1",
    next_seed_well: str = "B1",
    nm_cells_source_well: str = "A2",
    # ── Plate selection ────────────────────────────────────────────────────
    reagent_type: str = "GD Compound Stock Plate",
    # ── Monitoring window ──────────────────────────────────────────────────
    monitoring_readings: int = 9,
    monitoring_interval_minutes: int = 10,
) -> WorkflowDefinitionDescriptor:
    """Hackathon closed-loop media optimization — one iteration.

    Register this definition once per session; instantiate it per iteration
    by passing fresh inputs to instantiate_workflow().

    One complete iteration:
      Phase 1 — Liquid handling: transfer reagents from stock plate to
                 experimental wells, seed cells from warm seed well,
                 pre-warm next seed well with NM+Cells.
      Phase 2 — OD600 monitoring: read absorbance at fixed intervals for
                 the duration of the monitoring window.

    :param plate_barcode: Barcode of the experiment plate (96-well flat).
    :param transfer_array: JSON string of reagent transfers:
        [[source_well, dest_well, vol_uL], ...]
        Source wells are on the reagent plate; dest wells on the experiment
        plate. Max 30 entries. Novel Bio (D1) should use the largest volume;
        supplements (A1, B1, C1) fill the remainder.
    :param dest_wells: JSON list of experiment plate wells being filled this
        iteration. Usually 8 wells in one column, e.g. ["A2"..."H2"].
    :param monitoring_wells: JSON list of ALL wells to measure via OD600 —
        cumulative across iterations. Grows by ~8 wells each round.
    :param seed_well: Warm seed well on the experiment plate (col 1).
        Iteration 1 → "A1", iteration 2 → "B1", ..., iteration 8 → "H1".
    :param next_seed_well: Experiment plate well to pre-warm for the next
        iteration. Usually seed_well + 1 row. Pass "" to skip on last round.
    :param nm_cells_source_well: Well on the REAGENT plate containing
        pre-mixed Novel Media + cells (used to warm next_seed_well).
    :param reagent_type: Tag used to identify the stock plate in the Monomer
        system. Default matches the pre-prepared GD compound plate.
        Custom plates: use the tag you assigned at plate registration.
    :param monitoring_readings: Number of OD600 reads in the monitoring
        window (default 9 = 90 min at 10-min intervals).
    :param monitoring_interval_minutes: Minutes between OD600 reads.
    """
    # ── Parse JSON inputs ────────────────────────────────────────────────────
    transfers: list[list] = json.loads(transfer_array) if transfer_array else []
    dest_well_list: list[str] = json.loads(dest_wells)
    monitoring_well_list: list[str] = json.loads(monitoring_wells)
    nm_cells_volume = _NM_CELLS_VOL_UL if next_seed_well else 0

    # ── Validate ─────────────────────────────────────────────────────────────
    _validate(transfers, dest_well_list, monitoring_well_list, seed_well, next_seed_well)

    # ── Compute tip consumption ───────────────────────────────────────────────
    p50_tips, p200_tips, p1000_tips = _compute_tip_counts(
        transfers, dest_well_list, nm_cells_volume
    )
    reagent_wells_consumed = len({t[0] for t in transfers}) + (1 if nm_cells_volume > 0 else 0)

    # ── Build workflow ────────────────────────────────────────────────────────
    workflow = WorkflowDefinitionDescriptor(
        description=(
            f"Hackathon GD iteration: {len(dest_well_list)} wells, "
            f"{len(transfers)} transfers, seed={seed_well}"
        ),
    )

    # Phase 1: Liquid handling
    # Transfers reagents from the stock plate, seeds cells from the warm seed
    # well, and pre-warms the next seed well with NM+Cells.
    liquid_handling = RoutineReference(
        routine_name="GD Iteration Combined",
        routine_parameters={
            "experiment_plate_barcode": plate_barcode,
            "reagent_type": reagent_type,
            "transfer_array": json.dumps(transfers),
            "seed_well": seed_well,
            "seed_dest_wells": json.dumps(dest_well_list),
            "dest_column_index": 2,            # unused when seed_dest_wells is set
            "seed_transfer_volume": _SEED_TRANSFER_UL,
            "nm_cells_source_well": nm_cells_source_well,
            "nm_cells_volume": nm_cells_volume,
            "next_seed_well": next_seed_well or seed_well,  # fallback (nm_cells_volume=0)
            "mix_volume": _SEED_MIX_VOL_UL,
            "mix_reps": _SEED_MIX_REPS,
            "p50_tips_to_consume": p50_tips,
            "p200_tips_to_consume": p200_tips,
            "p1000_tips_to_consume": p1000_tips,
            "reuse_tips_for_same_source": True,
            "reagent_wells_to_consume": reagent_wells_consumed,
        },
    )
    workflow.add_routine("liquid_handling", liquid_handling)

    # Phase 2: OD600 monitoring loop
    # Reads all wells (cumulative across iterations) at fixed intervals.
    monitoring_keys: list[str] = []
    for i in range(monitoring_readings):
        key = f"od600_{i + 1}"
        workflow.add_routine(
            key,
            RoutineReference(
                routine_name="Measure Absorbance",
                routine_parameters={
                    "culture_plate_barcode": plate_barcode,
                    "method_name": "96wp_od600",
                    "wells_to_process": monitoring_well_list,
                },
            ),
        )
        monitoring_keys.append(key)

    # Space monitoring reads evenly across the window
    workflow.space_out_routines(
        monitoring_keys,
        Time(f"{monitoring_interval_minutes} minutes"),
    )

    # First read starts 30 s after liquid handling completes
    workflow.add_time_constraint(
        MoreThanConstraint(
            from_start="liquid_handling",
            to_start=monitoring_keys[0],
            value=Time("30 seconds"),
        )
    )

    return workflow
