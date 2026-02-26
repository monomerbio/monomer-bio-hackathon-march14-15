# Track 2A: Build an Autonomous Closed-Loop Agent

**Lead:** Carter Allen (carter@monomerbio.com) / Carmen Kivisild (Elnora)
**Goal:** Build an AI agent that runs media optimization experiments autonomously on real cells

---

## The Flow

### Step 0: Research (Track 1 → Track 2A handoff)

Use Elnora to research *V. natriegens* growth and identify which media components to test and at what concentrations. The [available components are listed in Notion](https://www.notion.so/2ff8d59ea9ff81ca8db1fd1ff80233d0) — you can choose from ~13 options including Glucose, Sodium Chloride, Magnesium Sulfate, Potassium Phosphate (mono/dibasic), Potassium Chloride, Calcium Chloride, Ammonium Sulfate, MOPS, Glycerol, Tryptone, Yeast Extract, and Trace metals solution.

Come out of Track 1 with: which components, which wells they go in, and what stock concentrations you want.

### Step 1: Design your stock plate

You'll get a **24-well deep well plate** to use as your stock plate. Assign one component per well (e.g. A1 = Glucose 1M, B1 = KCl 2M, C1 = MOPS 500mM). The robot will pipette directly from these wells into your experiment plate, so stock concentration determines your working concentration range.

**Transfer limit: max 40 transfers per iteration.** With 8 experimental wells and 4 components, that's 32 transfers — leaving room for a control well of pure base media. Plan your well layout and dilutions before you start.

Submit your plate layout to a Monomer team member. We'll prepare the stock solutions and load the plate onto the workcell, registering it with a tag you'll use in your workflow.

### Step 2: Run the closed loop

Your agent:
1. **Decides** — picks a media composition to test next (gradient descent, Bayesian optimization, etc.)
2. **Acts** — generates a transfer array and instantiates the workflow
3. **Waits** — the first few iterations require Monomer team approval (~a few minutes); later iterations may be pre-approved
4. **Observes** — reads OD600 growth data; platereader runs every 5–10 minutes during the ~90 min monitoring window
5. **Loops** — each iteration is ~2 hours end-to-end; you get ~6–8 iterations over the hackathon

### A note on cold reagents

Your stock plate lives in the 4°C fridge between uses. Cold reagents straight from the fridge will cause a **30–60 min lag before exponential growth** — longer than with pre-warmed reagents. Two approaches:

- **Prepare in parallel:** While your current iteration is running (90 min monitoring window), pull the stock plate out and let it warm to room temp before the next iteration starts.
- **Room temp storage:** If you're doing back-to-back iterations, it may be practical to keep the stock plate at room temp for the day — just flag this with a Monomer team member.

Either way, account for the warm-up effect in your growth model. Consistent plate temperature across iterations matters more than the absolute temperature.

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

The workcell speaks standard MCP (JSON-RPC 2.0 over HTTP POST). See `CLAUDE.md` for the full tool list and MCP Resources (DSL guides, schema references, and a working example workflow your AI can read directly).

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

Before registering, you can call the `validate_workflow_definition_file` MCP tool to catch routine name typos and missing parameters early — check the MCP resource `guide://workflows/creation` for the exact parameter names.

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

# column_index matches the column you filled — iteration 1 → column 2, iteration 2 → column 3, etc.
raw = fetch_absorbance_results(client, "GD-R1-20260314", column_index=2)
parsed = parse_od_results(raw, column_index=2)

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

- **Workflow approval:** Every workflow goes to `pending_approval` after instantiation. The first few iterations require manual approval from a Monomer team member (~a few minutes). `poll_workflow_completion()` blocks automatically; your agent just waits. If nothing happens after 10 minutes, flag a Monomer team member.

- **One workflow at a time:** The workcell runs workflows sequentially. Wait for the current one to complete before instantiating the next.

- **Tip and reagent tracking:** Handled internally by the workflow template. You don't need to count tips or reagent wells — the template computes consumption from your transfer array.

- **Workcell sharing:** Other teams may be using the workcell. If your workflow is queued but not starting, check with the Monomer team.

- **Volume limits:** P50 handles 1–50 µL, P200 handles 51–200 µL, P1000 handles 201–1000 µL. `apply_constraints()` enforces these in your transfer array.

- **Monitoring frequency:** Minimum 5 minutes between platereader reads. Default in the template is 10 minutes (`monitoring_interval_minutes=10`), which gives a 90-minute window with 9 reads. You can go down to 5 minutes for more granular data.

- **Reagent plate tag:** Your custom stock plate must be registered on the workcell with a specific `reagent_type` tag before you can use it. Coordinate with the Monomer team when you hand off your plate layout — they'll give you the tag string to use in your workflow.
