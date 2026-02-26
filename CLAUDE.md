# Monomer Bio Hackathon — AI Agent Context

This file gives AI coding assistants (Claude Code, Cursor, etc.) the technical context needed to help a contestant build a Track 2A closed-loop agent on the Monomer workcell.

---

## Media Composition

Each experimental well is **180 µL** total:

| Component | Role | Range |
|-----------|------|-------|
| Novel Bio (base media) | Required base | 90–180 µL (min 90 µL) |
| Glucose | Carbon supplement | 0–90 µL |
| NaCl | Osmolarity | 0–90 µL |
| MgSO4 | Cofactor supplement | 0–90 µL |

- All volumes are integers (µL resolution)
- Sum must equal exactly 180 µL
- `apply_constraints()` in `monomer/transfers.py` enforces these rules

### Reagent Well Map (reagent plate)
```
A1      = Glucose stock
B1      = NaCl stock
C1      = MgSO4 stock
D1      = Novel Bio (base media) — 1 tip reused across all transfers from this well
A2      = NM+Cells (pre-mixed Novel Media + cells, for next-round warm seed well)
A12–H12 = single-use seed aliquots, one row per iteration (pre-aliquoted at plate prep)
```

> **Pre-loaded by Monomer team** — the reagent plate (including NM+Cells in A2 and seed aliquots in col 12) is prepared and loaded before the experiment starts. Your agent does not need to manage plate loading.

> **Seed wells (col 1 of experiment plate)** — A1–H1 are used as warm seed wells, one per iteration. The workflow pre-warms each one by transferring NM+Cells from the reagent plate during the previous iteration. Iteration 1 uses A1 (pre-seeded by Monomer), and each subsequent iteration uses the next row.

---

## Platform Primitives

### Hierarchy
```
WorkflowDefinition  →  contains ordered RoutineReferences
WorkflowInstance    →  a running execution of a definition
Routine             →  atomic instrument action (incubate, pipette, read)
CulturePlate        →  tracked plate with barcode, history of readings
```

### Available Routines (Track 2A)

| Routine Name | Purpose | Key Parameters |
|---|---|---|
| **GD Iteration Combined** | Reagent transfers + seed cells from warm well + pre-warm next seed well | `experiment_plate_barcode`, `reagent_type`, `transfer_array`, `seed_well`, `seed_dest_wells` |
| **Measure Absorbance** | Read OD600 from a set of wells | `culture_plate_barcode`, `method_name` (`96wp_od600`), `wells_to_process` |

Don't call these directly — they're wired up inside `workflow_definition_template.py`, which handles parameter mapping, tip computation, and scheduling constraints.

### Plate Barcode Convention
```
{PREFIX}-R{ROUND}-{YYYYMMDD}
e.g. GD-R1-20260314
```

---

## MCP Connection

### Autoplat MCP (Workcell — workflow control)
- **URL:** `http://192.168.68.55:8080/mcp`
- **Auth:** None (local network)
- **Transport:** JSON-RPC 2.0 over HTTP POST with SSE response

#### Available Tools

**Workflow Definitions**
```
list_workflow_definitions         # All registered workflow definitions
get_workflow_definition           # Detailed info about a specific definition
get_workflow_definition_schedule  # Scheduled nodes with relative execution times
get_workflow_definition_dag       # DAG structure showing nodes and dependencies
list_workflow_definition_files    # Workflow definition files on disk
get_workflow_dsl_schemas          # Simplified schemas for DSL classes
create_workflow_definition_file   # Upload a workflow .py file to workcell
validate_workflow_definition_file # Validate definition before registration ← use this
register_workflow_definition      # Register validated file as a named definition
```

**Workflow Instances**
```
list_workflow_instances           # All instances and their statuses
get_workflow_instance_details     # Poll instance status
list_workflow_routines            # Scheduled steps for a specific instance
list_pending_workflows            # Workflows awaiting operator approval
instantiate_workflow              # Launch a workflow (returns instance UUID)
check_workflow_cancellable        # Check if workflow can be safely cancelled
cancel_workflow_instance          # Cancel a running or pending instance
```

**Routines**
```
list_available_routines           # All available routines and their signatures
get_routine_details               # Detailed signature for one routine
list_future_routines              # Upcoming scheduled routines
get_future_routine_details        # Complete future routine details
get_workflow_routine_with_children# WorkflowRoutine with child FutureRoutines
trace_future_routine_to_workflow  # Trace a FutureRoutine back to its workflow
check_consumables_for_timeframe   # Consumables needed for upcoming routines
```

**Plates**
```
list_culture_plates               # All culture plates on the workcell
check_plate_availability          # Check if a plate barcode is available
unlink_culture_plate_from_workflow# Unlink a plate from its current workflow
list_reagent_plates               # Reagent plates and their media/well state
```

#### MCP Resources
Read these directly to understand the workflow DSL without guessing:
```
guide://workflows/dsl             # Complete DSL reference with examples ← start here
guide://workflows/creation        # Quick start guide for creating workflows
guide://workflows/concepts        # Workflow concepts and execution flow
example://workflows/ipsc-maintenance # Complete working example workflow file
schema://workflows/dsl-api        # Auto-generated API reference for DSL classes
schema://workflows/models         # Database schema models
guide://future-routines/monitoring# Monitoring guide for AI agents
schema://routines/parameters      # Routine parameter types reference
guide://cultures-and-plates/concepts # Domain concepts explanation
doc://cultures-and-plates/api-usage  # API usage guide with examples
```

### Monitor MCP (Cloud — read-only observation)
- **URL:** `https://backend-staging.monomerbio.com/mcp`
- **Auth:** `Authorization: Bearer YOUR_TOKEN` (get token from cloud-staging.monomerbio.com)
- **Transport:** Same JSON-RPC 2.0

#### Available Tools
```
list_cultures                     # All culture plates being tracked
get_culture_details               # Plate metadata + latest readings
list_culture_statuses             # Status summary of all cultures
update_culture_status             # Update status for one or more wells
list_plates                       # All plates with observation summaries
get_plate_observations            # Time-series OD600 readings for a plate
export_plate_observations         # Export observations as structured data
```

### Install in Cursor
```json
{
  "mcpServers": {
    "monomer-autoplat": {
      "url": "http://192.168.68.55:8080/mcp"
    },
    "monomer-monitor": {
      "url": "https://backend-staging.monomerbio.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

---

## Python Library (`monomer/`)

### `McpClient` — low-level tool calls
```python
from monomer.mcp_client import McpClient

client = McpClient("http://192.168.68.55:8080")

plates = client.call_tool("list_culture_plates", {})
routines = client.call_tool("list_available_routines", {})
definitions = client.call_tool("list_workflow_definitions", {})
```

Use the higher-level helpers in `workflows.py` for registering and running workflows — they handle file upload, ID lookup, input merging, and polling.

### `workflows.py` — register, launch, poll
```python
from monomer.workflows import register_workflow, instantiate_workflow, poll_workflow_completion
import json

# Register the workflow template ONCE per session
def_id = register_workflow(client, Path("examples/workflow_definition_template.py"), name="My GD Agent")

# Each iteration: instantiate with your agent's outputs as extra_inputs
uuid = instantiate_workflow(
    client,
    definition_id=def_id,
    plate_barcode="GD-R1-20260314",
    extra_inputs={
        "transfer_array":   json.dumps(transfers),      # [[src_well, dst_well, vol_uL], ...]
        "dest_wells":       json.dumps(dest_wells),     # wells filled this iteration
        "monitoring_wells": json.dumps(all_wells),      # cumulative — grows each round
        "seed_well":        "A1",                       # advances each iteration
        "next_seed_well":   "B1",
    },
    reason="Iteration 1: testing Glucose=20µL, NaCl=10µL",
)
result = poll_workflow_completion(client, uuid, timeout_minutes=180)
```

### `datasets.py` — fetch OD600 results
```python
from monomer.datasets import fetch_absorbance_results, parse_od_results

# column_index = iteration + 1 (col 1 = seed wells; experiments start at col 2)
raw = fetch_absorbance_results(client, plate_barcode="GD-R1-20260314", column_index=2)
# raw = {"baseline": {"A2": 0.05, ...}, "endpoint": {"A2": 1.2, ...}}

parsed = parse_od_results(raw, column_index=2)
# parsed = {"control_od": 1.1, "center_od": 0.9, "perturbed_ods": {"Glucose": [1.3, 1.2], ...}}
```

### `transfers.py` — media composition helpers
```python
from monomer.transfers import generate_transfer_array, apply_constraints, ROWS

center = {"Glucose": 20, "NaCl": 10, "MgSO4": 5}  # µL
center = apply_constraints(center)  # clamp to valid ranges

# column_index = iteration + 1 (experiments start at col 2, col 1 = seed wells)
transfers = generate_transfer_array(center, column_index=2, delta=10)
# transfers = [["D1", "A2", 180], ["D1", "B2", 145], ["A1", "B2", 20], ...]

iteration = 1
column_index   = iteration + 1
dest_wells     = [f"{r}{column_index}" for r in ROWS]                    # ["A2".."H2"]
seed_well      = f"{ROWS[iteration - 1]}1"                               # "A1"
next_seed_well = f"{ROWS[iteration]}1" if iteration < len(ROWS) else ""  # "B1"
```

---

## Workcell Constraints

| Constraint | Value |
|-----------|-------|
| Max concurrent workflows | 1 (sequential scheduling) |
| Platereader frequency | Every 10 minutes |
| Well volume | 180 µL |
| Incubation temperature | 37°C |
| Tip reuse policy | Novel Bio (D1) reuses 1 tip; all other reagents use fresh tips |
| P50 range | 1–50 µL |
| P200 range | 51–200 µL |
| P1000 range | 201–1000 µL |

Workflows go to `pending_approval` after instantiation and require a Monomer team member to approve before execution. Keep iterations under 30 minutes of liquid handling.

---

## Useful REST Endpoints

The workcell also exposes a REST API alongside MCP:

```
GET  /api/datasets/?verbose=1&ordering=-createdAt   # All datasets (OD600 readings)
GET  /api/culture-plates/                            # All plates
```

Headers required: `X-Monomer-Client: desktop-frontend`

See `monomer/datasets.py` for a working example.
