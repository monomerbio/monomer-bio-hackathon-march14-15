"""Minimal closed-loop gradient descent agent for Track 2A.

This example runs one full iteration:
  1. Generate transfer array from current media composition
  2. Write a workflow definition file
  3. Register + instantiate the workflow on the workcell
  4. Poll until complete
  5. Fetch OD600 results and compute gradient
  6. Update center point for next iteration

Usage:
    python examples/basic_agent.py --plate GD-R1-20260314 --iterations 5
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from monomer.datasets import fetch_absorbance_results, parse_od_results
from monomer.mcp_client import McpClient
from monomer.transfers import (
    SUPPLEMENT_NAMES,
    apply_constraints,
    generate_transfer_array,
)
from monomer.workflows import (
    instantiate_workflow,
    poll_workflow_completion,
    register_workflow,
    write_workflow_definition,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# ── Agent parameters ────────────────────────────────────────────────────────

LEARNING_RATE = 5          # µL to adjust per unit gradient
DELTA_UL = 10              # perturbation size for gradient estimation
WORKFLOW_TEMPLATE = Path(__file__).parent.parent / "track-2a-closed-loop" / "examples" / "workflow_definition_template.py"


def run_agent(
    plate_barcode: str,
    n_iterations: int = 5,
    workcell_url: str = "http://192.168.68.55:8080",
):
    client = McpClient(workcell_url)

    # Starting composition: center of the design space
    center = apply_constraints({"Glucose": 20, "NaCl": 10, "MgSO4": 15})
    log.info("Starting composition: %s", center)

    history = []

    for iteration in range(1, n_iterations + 1):
        log.info("=== Iteration %d ===", iteration)
        log.info("Center: %s", center)

        column_index = iteration  # use one column per iteration (cols 1–12)
        if column_index > 12:
            log.warning("Out of columns — resetting or stopping")
            break

        # ── Step 1: Generate transfers ───────────────────────────────────────
        transfers = generate_transfer_array(center, column_index=column_index, delta=DELTA_UL)
        log.info("Generated %d transfers for column %d", len(transfers), column_index)

        # ── Step 2: Write workflow definition ────────────────────────────────
        output_dir = Path(f"runs/iteration_{iteration:02d}")
        workflow_path = write_workflow_definition(
            template_path=WORKFLOW_TEMPLATE,
            output_dir=output_dir,
            transfer_array=transfers,
            column_index=column_index,
            iteration=iteration,
        )
        log.info("Wrote workflow definition: %s", workflow_path)

        # ── Step 3: Register + instantiate ──────────────────────────────────
        def_id = register_workflow(client, workflow_path, iteration=iteration)
        log.info("Registered workflow definition ID: %d", def_id)

        uuid = instantiate_workflow(
            client,
            definition_id=def_id,
            plate_barcode=plate_barcode,
            reason=f"GD iteration {iteration}, center={json.dumps(center)}",
        )
        log.info("Instantiated workflow: %s", uuid)

        # ── Step 4: Wait for completion ──────────────────────────────────────
        log.info("Polling for completion (this takes 60–90 min)...")
        result = poll_workflow_completion(
            client,
            uuid,
            timeout_minutes=180,
            on_status=lambda s, t: log.info("  %dm elapsed: status=%s", t // 60, s),
        )
        log.info("Workflow completed: status=%s", result.get("status"))

        # ── Step 5: Fetch results ────────────────────────────────────────────
        raw = fetch_absorbance_results(client, plate_barcode, column_index=column_index)
        parsed = parse_od_results(raw, column_index=column_index)

        log.info(
            "Results — control: %.3f | center: %.3f",
            parsed["control_od"],
            parsed["center_od"],
        )
        for supp, (r1, r2) in parsed["perturbed_ods"].items():
            log.info("  %s: %.3f, %.3f (avg %.3f)", supp, r1, r2, (r1 + r2) / 2)

        history.append({"iteration": iteration, "center": dict(center), "parsed": parsed})

        # ── Step 6: Gradient update ──────────────────────────────────────────
        new_center = dict(center)
        for supp in SUPPLEMENT_NAMES:
            r1, r2 = parsed["perturbed_ods"][supp]
            avg_perturbed = (r1 + r2) / 2
            gradient = avg_perturbed - parsed["center_od"]
            adjustment = int(LEARNING_RATE * gradient)
            new_center[supp] = center[supp] + adjustment
            log.info(
                "  Gradient %s: %.3f → adjust %+d µL", supp, gradient, adjustment
            )

        center = apply_constraints(new_center)
        log.info("Updated center: %s", center)

    log.info("=== Agent finished after %d iterations ===", len(history))
    log.info("Final center composition: %s", center)

    # Save history
    output_dir = Path("runs")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "history.json").write_text(json.dumps(history, indent=2))
    log.info("History saved to runs/history.json")

    return center, history


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gradient descent media optimization agent")
    parser.add_argument("--plate", required=True, help="Plate barcode (e.g. GD-R1-20260314)")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations to run")
    parser.add_argument("--workcell", default="http://192.168.68.55:8080", help="Workcell base URL")
    args = parser.parse_args()

    run_agent(
        plate_barcode=args.plate,
        n_iterations=args.iterations,
        workcell_url=args.workcell,
    )
