# Track 2A: Build an Autonomous Closed-Loop Agent

**Lead:** Carter Allen (carter@monomerbio.com) / Carmen Kivisild (Elnora)
**Goal:** Build an AI agent that runs media optimization experiments autonomously on real cells

---

## What You're Building

A Python agent that:
1. **Observes** — reads OD600 growth data from the workcell via MCP
2. **Decides** — uses an optimization algorithm to choose the next media composition
3. **Acts** — generates a transfer array, uploads a workflow, and runs it on the workcell
4. **Loops** — waits for results and repeats

This is real biology running on a real robot. Each iteration takes 60–90 minutes.

---

## MCP Setup

### Option A: Claude Code / Claude API

Add this to your Claude MCP config (`~/.claude.json` or `claude mcp add`):

```json
{
  "mcpServers": {
    "monomer-autoplat": {
      "url": "http://192.168.68.55:8080/mcp"
    }
  }
}
```

### Option B: Cursor

1. Download [Cursor](https://cursor.com/download)
2. Open Settings → MCP
3. Add server: `http://192.168.68.55:8080/mcp` (no auth needed on local network)
4. For Monitor MCP (read-only cloud data), add: `https://backend-staging.monomerbio.com/mcp` with `Authorization: Bearer YOUR_TOKEN`

Get your token from `cloud-staging.monomerbio.com` → Profile → API Token.

### Option C: Any MCP-compatible tool

The workcell speaks standard MCP (JSON-RPC 2.0 over HTTP POST). See `CLAUDE.md` for the full protocol spec.

---

## Quick Start

```bash
pip install -e .
```

```python
from monomer.mcp_client import McpClient

# Connect to workcell
client = McpClient("http://192.168.68.55:8080")

# See available routines
routines = client.call_tool("list_available_routines", {})
for r in routines:
    print(r["name"])

# Check what plates are on the workcell
plates = client.call_tool("list_culture_plates", {})
print(plates)
```

---

## Building Your Agent

### Step 1: Design Your Optimization Strategy

The 3 supplements (Glucose, NaCl, MgSO4) define a 3D search space. Good strategies:

| Strategy | Pros | Cons |
|----------|------|------|
| **Gradient descent** | Simple, interpretable, fast convergence near optimum | Can get stuck in local optima |
| **Bayesian optimization** | Handles noise well, sample-efficient | More complex to implement |
| **Random search** | Easy, good baseline | Slow convergence |
| **DOE then refine** | Best for first experiment | Requires more wells |

The `monomer/transfers.py` library implements gradient descent natively — see `generate_transfer_array()`.

### Step 2: Generate a Transfer Array

```python
from monomer.transfers import generate_transfer_array, apply_constraints

# Your current best guess at optimal composition
center = {"Glucose": 20, "NaCl": 10, "MgSO4": 15}
center = apply_constraints(center)  # ensure volumes are valid

# Generate transfers for 8 wells in column 2 (col 1 is reserved for seed wells)
# Layout: A=control, B=center, C/D=+Glucose, E/F=+NaCl, G/H=+MgSO4
transfers = generate_transfer_array(center, column_index=2, delta=10)
```

### Step 3: Register Template and Run Each Iteration

The workflow definition is registered **once** at session start. Each iteration you instantiate it with fresh inputs — no file regeneration needed.

See `examples/basic_agent.py` for a complete working example.

```python
import json
from monomer.workflows import register_workflow, instantiate_workflow, poll_workflow_completion
from monomer.transfers import ROWS
from pathlib import Path

# ── Register ONCE at session start ──────────────────────────────────────────
def_id = register_workflow(
    client,
    Path("examples/workflow_definition_template.py"),
    name="My GD Agent",
)

# ── Each iteration: instantiate with your agent's outputs ───────────────────
iteration = 1
column_index = iteration + 1          # col 1 = seeds; experiments start at col 2
dest_wells = [f"{r}{column_index}" for r in ROWS]
seed_well = f"{ROWS[iteration - 1]}1" # A1 → B1 → C1 ... advances each round
next_seed_well = f"{ROWS[iteration]}1" if iteration < len(ROWS) else ""

uuid = instantiate_workflow(
    client,
    definition_id=def_id,
    plate_barcode="GD-R1-20260314",
    extra_inputs={
        "transfer_array":   json.dumps(transfers),
        "dest_wells":       json.dumps(dest_wells),
        "monitoring_wells": json.dumps(dest_wells),  # grows cumulatively each round
        "seed_well":        seed_well,
        "next_seed_well":   next_seed_well,
    },
    reason=f"Iteration {iteration}: center={json.dumps(center)}",
)

# Wait for completion (~60–90 min)
result = poll_workflow_completion(client, uuid, timeout_minutes=180,
    on_status=lambda s, t: print(f"  {t//60}m: {s}"))
```

### Step 4: Read Results

```python
from monomer.datasets import fetch_absorbance_results, parse_od_results

raw = fetch_absorbance_results(client, "GD-R1-20260314", column_index=1)
parsed = parse_od_results(raw, column_index=1)

print(f"Control OD: {parsed['control_od']:.3f}")
print(f"Center OD:  {parsed['center_od']:.3f}")
for supp, (r1, r2) in parsed['perturbed_ods'].items():
    print(f"{supp} perturbation: {r1:.3f}, {r2:.3f}")
```

### Step 5: Update Your Model and Loop

```python
# Gradient descent update (simplified)
for supp in ["Glucose", "NaCl", "MgSO4"]:
    r1, r2 = parsed["perturbed_ods"][supp]
    avg_perturbed = (r1 + r2) / 2
    gradient = avg_perturbed - parsed["center_od"]
    center[supp] += int(learning_rate * gradient)

center = apply_constraints(center)
# → go to Step 2 with new center
```

---

## Workflow Definition Format

A workflow definition is a Python file with a `build_definition()` function. The function accepts typed parameters — your agent passes them at instantiation time, so you only ever upload the file once.

```python
def build_definition(
    plate_barcode: str,           # always required
    transfer_array: str = "[]",   # your reagent transfers this iteration
    dest_wells: str = "...",      # wells being filled
    monitoring_wells: str = "...",# cumulative — all wells measured so far
    seed_well: str = "A1",        # advances A1 → B1 → C1 ... each round
    next_seed_well: str = "B1",   # pre-warms the next seed well
    reagent_type: str = "...",    # identifies your stock plate
    monitoring_readings: int = 9, # 9 × 10 min = 90 min window
    ...
) -> WorkflowDefinitionDescriptor:
    # builds the routine sequence and returns it
```

The template validates your inputs (transfer count, well conflicts, volumes) before the workflow reaches the approval queue. See `examples/workflow_definition_template.py` for the full implementation and parameter docs.

---

## Workcell Constraints

- **Workflow approval:** A Monomer team member must approve each workflow before it runs. Keep iterations under 30 minutes and don't queue more than 2 at a time.
- **Tip limits:** Each tip rack has 96 tips. Track consumption across iterations.
- **Workcell sharing:** Other teams are using the workcell too. Coordinate with the Monomer team on scheduling.
- **Volume range:** P50 for ≤50 µL, P200 for 51–200 µL. Stay within these.
