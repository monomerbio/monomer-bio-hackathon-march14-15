"""Workflow management helpers for Monomer Bio workcells.

Handles workflow definition upload/registration, instantiation, and
polling for completion — all via the MCP client.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monomer.mcp_client import McpClient

# Defaults
DAEMON_POLL_INTERVAL = 30  # seconds between status checks
WORKFLOW_TIMEOUT_MINUTES = 180  # max wait per workflow (3 hours)


def register_workflow(
    client: McpClient,
    workflow_path: Path,
    name: str = "Hackathon GD Agent",
) -> int:
    """Register a workflow definition via MCP. Call this ONCE per session.

    Uploads the workflow definition file and creates a named database record.
    Returns the workflow definition ID for use in instantiate_workflow().

    :param client: Connected MCP client.
    :param workflow_path: Path to the workflow_definition_template.py file.
    :param name: Human-readable name shown in the Monomer UI approval queue.
    :returns: Workflow definition database ID.
    """
    file_name = workflow_path.name
    code_content = workflow_path.read_text()

    # Upload the file to the workcell
    client.call_tool(
        "create_workflow_definition_file",
        {"file_name": file_name, "code_content": code_content},
    )

    # Create the named DB record
    client.call_tool(
        "register_workflow_definition",
        {"name": name, "file_name": file_name},
    )

    # Return the assigned ID
    definitions = client.call_tool("list_workflow_definitions", {})
    for d in definitions:
        if d["name"] == name:
            return d["id"]

    raise RuntimeError(f"Definition '{name}' not found after registration")


def instantiate_workflow(
    client: McpClient,
    definition_id: int,
    plate_barcode: str,
    extra_inputs: dict | None = None,
    reason: str = "",
) -> str:
    """Create a workflow instance via MCP. Returns the instance UUID.

    :param client: Connected MCP client.
    :param definition_id: ID returned by register_workflow().
    :param plate_barcode: Barcode of the experiment plate (always required).
    :param extra_inputs: Additional inputs declared in build_definition() —
        e.g. transfer_array, dest_wells, monitoring_wells, seed_well.
        These are merged with plate_barcode into the inputs dict.
    :param reason: Plain-English reason shown to the operator in the
        approval queue. Be descriptive — e.g. "Iteration 2, center=[...]".
    :returns: Workflow instance UUID.
    """
    inputs = {"plate_barcode": plate_barcode, **(extra_inputs or {})}
    result = client.call_tool(
        "instantiate_workflow",
        {
            "definition_id": definition_id,
            "inputs": inputs,
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
