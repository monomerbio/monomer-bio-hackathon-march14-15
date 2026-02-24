"""Workflow management helpers for Monomer Bio workcells.

Handles workflow definition upload/registration, instantiation, and
polling for completion — all via the MCP client.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monomer.mcp_client import McpClient

from monomer.transfers import REAGENT_WELLS, compute_tip_consumption

# Defaults
DAEMON_POLL_INTERVAL = 30  # seconds between status checks
WORKFLOW_TIMEOUT_MINUTES = 180  # max wait per workflow (3 hours)


def write_workflow_definition(
    template_path: Path,
    output_dir: Path,
    transfer_array: list,
    column_index: int,
    iteration: int,
    seed_params: dict | None = None,
) -> Path:
    """Write an iteration-specific workflow definition file.

    Copies the template and replaces iteration-specific constants using regex.
    Returns the path to the written file.
    """
    template = template_path.read_text()

    tip_counts = compute_tip_consumption(transfer_array)
    # Reagent well counter: count supplement wells (exclude Novel_Bio D1)
    supplement_wells_used = len(
        set(t[0] for t in transfer_array) - {REAGENT_WELLS["Novel_Bio"]}
    )

    def replace_const(name: str, value):
        nonlocal template
        template = re.sub(
            rf"^({re.escape(name)}\s*=\s*).*$",
            rf"\g<1>{value}",
            template,
            flags=re.MULTILINE,
        )

    # Core parameters
    replace_const("TRANSFER_ARRAY", json.dumps(json.dumps(transfer_array)))
    replace_const("DEST_COLUMN_INDEX", str(column_index))

    # Seed parameters (for combined routine template)
    if seed_params:
        replace_const("SEED_WELL", f'"{seed_params["seed_well"]}"')
        replace_const("NEXT_SEED_WELL", f'"{seed_params["next_seed_well"]}"')
        replace_const("NM_CELLS_VOLUME", str(seed_params["nm_cells_volume"]))

    # Tip consumption — extras for combined routine
    p50_extra = 1 if seed_params else 0
    p200_extra = 1 if seed_params else 0
    p1000_count = (
        1 if seed_params and seed_params["nm_cells_volume"] > 0 else 0
    )
    reagent_extra = (
        1 if seed_params and seed_params["nm_cells_volume"] > 0 else 0
    )

    replace_const("P50_TIPS_TO_CONSUME", str(tip_counts["p50"] + p50_extra))
    replace_const("P200_TIPS_TO_CONSUME", str(tip_counts["p200"] + p200_extra))
    replace_const(
        "P1000_TIPS_TO_CONSUME",
        str(tip_counts.get("p1000", 0) + p1000_count),
    )
    replace_const(
        "REAGENT_WELLS_TO_CONSUME",
        str(supplement_wells_used + reagent_extra),
    )

    # Write iteration-specific file
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "workflow_definition.py"
    output_path.write_text(template)

    return output_path


def register_workflow(
    client: McpClient,
    workflow_path: Path,
    iteration: int,
    name_prefix: str = "Gradient Descent Iteration",
) -> int:
    """Register a workflow definition via MCP (upload file + create DB record).

    Returns the workflow definition database ID.
    """
    file_name = f"gradient_descent_iteration_r{iteration}.py"
    workflow_name = f"{name_prefix} {iteration}"

    # Step 1: Upload the workflow definition file
    code_content = workflow_path.read_text()
    client.call_tool(
        "create_workflow_definition_file",
        {"file_name": file_name, "code_content": code_content},
    )

    # Step 2: Register the workflow definition (creates DB record)
    client.call_tool(
        "register_workflow_definition",
        {"name": workflow_name, "file_name": file_name},
    )

    # Step 3: Look up the definition ID
    definitions = client.call_tool("list_workflow_definitions", {})
    for d in definitions:
        if d["name"] == workflow_name:
            return d["id"]

    raise RuntimeError(f"Definition '{workflow_name}' not found after registration")


def instantiate_workflow(
    client: McpClient,
    definition_id: int,
    plate_barcode: str,
    reason: str = "",
) -> str:
    """Create a workflow instance via MCP. Returns the instance UUID.

    With auto_approve_pending_instances=True on the workcell, the workflow
    starts immediately.
    """
    result = client.call_tool(
        "instantiate_workflow",
        {
            "definition_id": definition_id,
            "inputs": {"plate_barcode": plate_barcode},
            "reason": reason,
        },
    )

    uuid = result.get("uuid")
    if not uuid:
        raise RuntimeError(
            f"MCP instantiate_workflow did not return UUID: {result}"
        )
    return uuid


def poll_workflow_completion(
    client: McpClient,
    uuid: str,
    timeout_minutes: int = WORKFLOW_TIMEOUT_MINUTES,
    poll_interval: int = DAEMON_POLL_INTERVAL,
    on_status: callable | None = None,
) -> dict:
    """Poll via MCP until a workflow instance completes.

    Args:
        client: MCP client instance.
        uuid: Workflow instance UUID.
        timeout_minutes: Max wait time.
        poll_interval: Seconds between polls.
        on_status: Optional callback(status, elapsed_seconds) called each poll.

    Returns the workflow instance data dict.
    """
    start_time = time.time()
    deadline = start_time + timeout_minutes * 60

    while time.time() < deadline:
        instance = client.call_tool(
            "get_workflow_instance_details", {"instance_uuid": uuid}
        )
        status = instance.get("status", "unknown")

        if status in ("completed", "failed", "cancelled", "canceled"):
            return instance

        if on_status:
            on_status(status, int(time.time() - start_time))

        time.sleep(poll_interval)

    raise TimeoutError(
        f"Workflow {uuid} did not complete within {timeout_minutes} minutes"
    )
