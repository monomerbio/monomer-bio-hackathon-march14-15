# Monomer Bio Hackathon — AI Agent Context

This file gives AI coding assistants (Claude Code, Cursor, etc.) all the context needed to help a hackathon contestant build an autonomous biology agent.

## What This Is

A 2-day hackathon (March 14–15, 2026) where teams build AI-driven experiments on a real robotic workcell. The goal: find the optimal growth media for *Vibrio natriegens* by running automated experiments, reading absorbance, and iterating.

**Scoring:** total biomass = Σ (number of growing wells × OD600 absorbance per well). Higher is better.

---

## The Biology

### Cell Line: *Vibrio natriegens*
- Fastest naturally occurring BSL-1 organism — ~20 min doubling time, ~50 min to confluence
- Grown in 96-well plates, 180 µL per well
- OD600 absorbance is the readout (platereader every 10 minutes)
- A typical growth curve goes from ~0.05 (seeded) to 0.5–1.5+ (confluent) in 60–90 min

### Growth Media
Each well contains a total of **180 µL** composed of:

| Component | Role | Range |
|-----------|------|-------|
| Novel Bio (base media) | Carbon/nitrogen source, required | 90–180 µL (min 90 µL) |
| Glucose | Carbon supplement | 0–90 µL |
| NaCl | Osmolarity | 0–90 µL |
| MgSO4 | Cofactor supplement | 0–90 µL |

Constraints:
- Novel Bio must be ≥ 90 µL (floor to maintain viability)
- All volumes are integers (µL resolution)
- Sum of all components = exactly 180 µL
- Supplements drawn from a reagent plate loaded onto the workcell (default: GD Compound Stock Plate)

### Reagent Well Map (reagent plate)
```
A1 = Glucose stock
B1 = NaCl stock
C1 = MgSO4 stock
D1 = Novel Bio (base media)
```

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

Contestants do not call these directly — they are wired up inside `workflow_definition_template.py`. The template handles all parameter mapping, tip computation, and scheduling constraints.

A workflow is a sequence of routine references, defined as a Python file registered once per session and instantiated per iteration via MCP.

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
```
list_available_routines         # See all routines and their signatures
get_routine_details             # Detailed signature for one routine
list_workflow_definitions       # All registered workflow definitions
create_workflow_definition_file # Upload a workflow .py file to workcell
register_workflow_definition    # Register uploaded file as a named definition
list_workflow_instances         # All instances and their statuses
instantiate_workflow            # Launch a workflow (returns instance UUID)
get_workflow_instance_details   # Poll instance status
cancel_workflow_instance        # Cancel a running or pending instance
list_culture_plates             # List all plates on the workcell
check_plate_availability        # Check if a plate barcode is available
list_future_routines            # Upcoming scheduled routines
```

### Monitor MCP (Cloud — read-only observation)
- **URL:** `https://backend-staging.monomerbio.com/mcp`
- **Auth:** `Authorization: Bearer YOUR_TOKEN` (get token from cloud-staging.monomerbio.com)
- **Transport:** Same JSON-RPC 2.0

#### Available Tools
```
list_cultures                   # All culture plates being tracked
get_culture_details             # Plate metadata + latest readings
list_culture_statuses           # Status summary of all cultures
get_plate_observations          # Time-series OD600 readings for a plate
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
client.connect()  # optional — auto-connects on first call

# Explore what's on the workcell
plates = client.call_tool("list_culture_plates", {})
routines = client.call_tool("list_available_routines", {})
definitions = client.call_tool("list_workflow_definitions", {})
```

For registering and running workflows, use the higher-level `monomer/workflows.py` helpers — they handle file upload, ID lookup, input merging, and polling.

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

# Seed/column helpers
iteration = 1
column_index  = iteration + 1                                        # 2
dest_wells    = [f"{r}{column_index}" for r in ROWS]                 # ["A2".."H2"]
seed_well     = f"{ROWS[iteration - 1]}1"                            # "A1"
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

Workflows require manual approval from a Monomer team member before execution. Keep workflows under 30 minutes per iteration.

---

## Track 1: Research Goal

Use Elnora AI (or any AI) to answer these questions before designing your experiment:
1. Which of Glucose, NaCl, MgSO4 most significantly affects *V. natriegens* growth?
2. What concentration ranges are biologically meaningful?
3. Is a DOE (design of experiments) the right approach, or iterative gradient descent?
4. What passaging strategy maximizes total biomass over 24 hours?
5. What pipetting or timing factors could confound results?

Output: a specific experimental plan (which concentrations, how many wells, what workflow sequence).

## Track 2A: Closed Loop Agent Goal

Build an agent that:
1. Reads current OD600 results from the workcell
2. Decides what media composition to test next (gradient descent, Bayesian optimization, etc.)
3. Generates a transfer array and instantiates the workflow with those inputs via MCP
4. Waits for operator approval and workflow completion
5. Loops back to step 1

The `monomer/` library handles steps 3–4. Register `workflow_definition_template.py` once; your agent generates `transfer_array` and other inputs each iteration and passes them to `instantiate_workflow(extra_inputs={...})`.

---

## Useful REST Endpoints

The workcell also exposes a REST API (in addition to MCP):

```
GET  /api/datasets/?verbose=1&ordering=-createdAt   # All datasets (OD600 readings)
GET  /api/culture-plates/                            # All plates
```

Headers required: `X-Monomer-Client: desktop-frontend`

See `monomer/datasets.py` for a working example of REST + MCP together.
