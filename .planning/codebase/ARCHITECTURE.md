# Monomer Bio Hackathon — Codebase Architecture

**Project:** Track 2A Closed-Loop Media Optimization Agent
**Focus:** Autonomous AI-driven gradient descent experiments on workcells
**Language:** Python 3.11+

---

## Overview

This is a **client-side AI agent framework** for running autonomous closed-loop experiments on Monomer Bio workcells. The agent controls a liquid-handling robot to perform gradient descent optimization of microbial growth media composition, reading OD600 growth measurements and updating experimental parameters in real-time.

The architecture follows a **task-driven, MCP-mediated design**:
1. Agent decides media compositions via optimization algorithm
2. Agent generates transfer arrays (liquid handling instructions)
3. Agent submits workflows to workcell via MCP (Monomer Control Protocol)
4. Workcell executes workflows, takes OD600 measurements
5. Agent fetches results and updates optimization model

---

## System Layers

### Layer 1: Communication (MCP Client)
**File:** `monomer/mcp_client.py`

Lightweight JSON-RPC 2.0 HTTP client for workcell communication.

- **Protocol:** HTTP Streamable Transport (POST to `/mcp` endpoint)
- **Session:** Ephemeral per client instance; requires `initialize` handshake on first call
- **Error Handling:** Parses SSE (Server-Sent Events) responses, extracts structured or text results
- **Auto-Connect:** Lazy initialization on first `call_tool()` invocation

**Key Class:** `McpClient`
- `__init__(base_url)` — Create client, default to workcell at `192.168.68.55:8080`
- `connect()` — Perform MCP initialize handshake, obtain session ID
- `call_tool(tool_name, arguments, timeout)` — Call an MCP tool, parse response

**Usage Pattern:**
```python
client = McpClient("http://192.168.68.55:8080")
plates = client.call_tool("list_culture_plates", {})
```

### Layer 2: Workflow Management
**File:** `monomer/workflows.py`

High-level workflow orchestration: registration, instantiation, polling.

Three functions manage the workflow lifecycle:

1. **`register_workflow(client, workflow_path, name)`**
   - Uploads workflow definition Python file to workcell via `create_workflow_definition_file`
   - Registers named DB record via `register_workflow_definition`
   - Returns integer `definition_id` for reuse across iterations
   - **Called once per session**

2. **`instantiate_workflow(client, definition_id, plate_barcode, extra_inputs, reason)`**
   - Creates workflow instance with runtime inputs
   - Merges `plate_barcode` (always required) with `extra_inputs` (agent-specific data)
   - Returns workflow instance UUID
   - **Called once per iteration**
   - Workflows enter `pending_approval` queue; operators approve in Monomer UI

3. **`poll_workflow_completion(client, uuid, timeout_minutes, poll_interval, on_status)`**
   - Polls via `get_workflow_instance_details` until terminal state
   - Terminal states: `completed`, `failed`, `cancelled`, `canceled`
   - Default timeout: 180 minutes (3 hours per iteration)
   - Optional callback for progress logging
   - **Blocks until completion**

**Data Flow:**
```
Iteration N:
  Transfer array → instantiate_workflow() → instance UUID → poll → result
  Fetch results → Update model → Iteration N+1
```

### Layer 3: Media Composition & Transfer Generation
**File:** `monomer/transfers.py`

Pure computation layer for media optimization (no I/O).

**Constants:**
- `ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]` — 8 rows per 96-well plate
- `SUPPLEMENT_NAMES = ["Glucose", "NaCl", "MgSO4"]` — 3 modifiable components
- `WELL_VOLUME_UL = 180` — Fixed well volume
- `MIN_NOVEL_BIO_UL = 90` — Minimum base media (Novel Bio)
- `DELTA_UL = 10` — Perturbation step size for gradient estimation
- `REAGENT_WELLS = {"Glucose": "A1", "NaCl": "B1", "MgSO4": "C1", "Novel_Bio": "D1"}` — Stock plate layout

**Row Semantics (per iteration):**
- Row A: Control (180 µL Novel Bio only)
- Row B: Center point (current best guess)
- Rows C-D: +delta Glucose (2 replicates)
- Rows E-F: +delta NaCl (2 replicates)
- Rows G-H: +delta MgSO4 (2 replicates)

**Key Functions:**

1. **`apply_constraints(supplements, ...)`**
   - Clamps supplement volumes to valid ranges (0 or [1, 90] µL)
   - Ensures base media >= 90 µL
   - Returns valid composition dict

2. **`generate_transfer_array(center, column_index, delta, ...)`**
   - Returns list of `[source_well, dest_well, volume_µL]` tuples
   - Generates one complete column (8 wells) of transfers
   - Includes control + center + 6 perturbations
   - Transfers sorted by source well (Novel Bio first for tip reuse efficiency)

3. **`make_perturbed(center, supplement_name, delta)`**
   - Create single-axis perturbation: `center[supplement] += delta`
   - Applies constraints to ensure validity

4. **`compute_tip_consumption(transfer_array, ...)`**
   - Counts tips required by pipette size (p50: 1–50 µL, p200: 51–200 µL, p1000: 201–1000 µL)
   - Returns `{"p50": count, "p200": count, "p1000": count}`
   - Used internally by workflow template for hardware resource planning

**Validation Flow:**
```
Agent-chosen composition
  ↓
apply_constraints() → valid center point
  ↓
make_perturbed() × 3 → 6 perturbations
  ↓
generate_transfer_array() → 40 transfers max
  ↓
compute_tip_consumption() → hardware requirements
```

### Layer 4: Data Acquisition (OD600 Results)
**File:** `monomer/datasets.py`

Fetches and parses growth measurements from workcell REST API.

**Architecture:**
- Queries REST API at `{base_url}/api/datasets/` (NOT MCP)
- Filters for OD600 measurements (wavelength=600 nm) matching plate UUID
- Extracts baseline (earliest) and endpoint (latest) readings per well
- Parses growth deltas: `delta_OD = endpoint - baseline`

**Key Functions:**

1. **`get_plate_uuid(client, plate_barcode)`**
   - Looks up plate UUID from barcode via MCP `list_culture_plates`
   - UUID needed for REST API queries

2. **`fetch_absorbance_results(client, plate_barcode, column_index)`**
   - Returns dict with `baseline` and `endpoint` OD600 readings for all 8 wells in target column
   - Column index increments per iteration: iter 1 → col 2, iter 2 → col 3, etc.
   - Column 1 reserved for seed wells

3. **`parse_od_results(absorbance_results, column_index)`**
   - Computes delta OD (growth) for:
     - Control well (A{col})
     - Center well (B{col})
     - Perturbed wells (C{col}–H{col}), grouped by supplement
   - Returns structured dict for gradient computation

**Response Structure:**
```python
{
    "control_od": 0.5,           # delta OD
    "center_od": 1.2,
    "perturbed_ods": {
        "Glucose": [1.5, 1.4],   # 2 replicates
        "NaCl": [0.8, 0.9],
        "MgSO4": [1.0, 1.1],
    },
    "abs_control_od": 1.6,       # absolute endpoint (for logging)
    "abs_center_od": 2.3,
}
```

---

## Data Flow: One Complete Iteration

```
Agent State: current center composition
     ↓
[1] Generate Transfer Array
    - generate_transfer_array(center, column_index, delta)
    - Output: 40 transfers max
     ↓
[2] Instantiate Workflow
    - instantiate_workflow(
        definition_id,
        plate_barcode,
        extra_inputs={
          transfer_array: JSON serialized,
          dest_wells: JSON list (e.g., ["A2", "B2", ..., "H2"]),
          monitoring_wells: JSON list (cumulative),
          seed_well: "A1" (advances per iteration),
          next_seed_well: "B1",
          reagent_type: "GD Compound Stock Plate",
        },
        reason: "Iteration N: center=..."
      )
    - Output: instance UUID, status=pending_approval
     ↓
[3] Poll Workflow Completion
    - poll_workflow_completion(uuid, timeout=180 min)
    - Workcell executes:
      * Transfer reagents from stock plate
      * Seed cultures from warm well
      * Incubate at 37°C
      * Read OD600 every 10 min (9 reads, 90 min window)
      * Pre-warm next seed well with NM+Cells
     ↓
[4] Fetch OD600 Results
    - fetch_absorbance_results(barcode, column_index)
    - parse_od_results(raw, column_index)
    - Output: growth deltas per well
     ↓
[5] Compute Gradient & Update
    - For each supplement: gradient = avg(perturbed) - center
    - new_center[supp] = center[supp] + learning_rate * gradient
    - apply_constraints(new_center)
    - Output: updated center for iteration N+1
     ↓
Loop: Iteration N+1 (go to [1])
```

---

## Abstraction Boundaries

### Workcell Abstraction
The `McpClient` abstracts workcell communication into tool calls. Available tools:

**Workflow Tools (Layer 2 uses these):**
- `create_workflow_definition_file` — Upload workflow Python file
- `register_workflow_definition` — Register named definition
- `list_workflow_definitions` — List all registered definitions
- `instantiate_workflow` — Create instance
- `get_workflow_instance_details` — Poll status

**Plate/Culture Tools:**
- `list_culture_plates` — All plates on workcell
- `get_plate_observations` — OD600 time-series
- (Monitor MCP provides cloud-based read-only access)

**Routine Tools:**
- `list_available_routines` — Available routine types
- `list_future_routines` — Upcoming scheduled work

**Reagent Tools:**
- `list_reagent_plates` — Reagent plate inventory

### Algorithm Abstraction
`transfers.py` is **pure computation** — no I/O, no state. This enables:
- Unit testing without workcell
- Offline simulation
- Multiple optimization strategies without changing workcell code

Agents can swap algorithms (gradient descent, Bayesian opt, etc.) without touching MCP or workflow layers.

### Workflow Abstraction
The workflow definition (`workflow_definition_template.py`) resides on the workcell and is executed there. Agents:
- Upload once via `register_workflow()`
- Instantiate repeatedly with different `extra_inputs`
- Never need to edit or understand the workflow internals

This decouples agent logic from hardware-specific sequencing.

---

## Entry Points

### Primary: Basic Agent (`track-2a-closed-loop/examples/basic_agent.py`)

Minimal closed-loop optimizer demonstrating full 5-step iteration.

```python
def run_agent(plate_barcode, n_iterations=5, workcell_url="http://192.168.68.55:8080"):
    client = McpClient(workcell_url)

    # [Session setup] Register workflow once
    def_id = register_workflow(client, WORKFLOW_TEMPLATE, name="Hackathon GD Agent")

    center = apply_constraints({"Glucose": 20, "NaCl": 10, "MgSO4": 15})

    for iteration in range(1, n_iterations + 1):
        # [Iteration loop]
        transfers = generate_transfer_array(center, column_index=iteration+1, delta=10)
        uuid = instantiate_workflow(client, def_id, plate_barcode, {...})
        poll_workflow_completion(client, uuid)
        results = parse_od_results(fetch_absorbance_results(...), iteration+1)

        # [Gradient update]
        for supp in ["Glucose", "NaCl", "MgSO4"]:
            gradient = (results["perturbed_ods"][supp][0] + results["perturbed_ods"][supp][1]) / 2 - results["center_od"]
            center[supp] += int(5 * gradient)
        center = apply_constraints(center)
```

**Usage:**
```bash
python examples/basic_agent.py --plate GD-R1-20260314 --iterations 5
```

### Secondary: Workflow Template (`track-2a-closed-loop/examples/workflow_definition_template.py`)

Workcell-side workflow definition (Python DSL). Uploaded once, instantiated per iteration.

Contains:
- Parameter parsing and validation
- Routine scheduling (reagent transfer, seeding, monitoring)
- Tip/reagent consumption calculation
- Error messages

Not meant to be run locally (imports fail) — uploaded via `register_workflow()`.

---

## Key Design Decisions

### 1. Lazy MCP Connection
`McpClient.connect()` is called on first `call_tool()`, not in `__init__`. Allows passing around disconnected clients without network cost.

### 2. Workflow Registration Pattern
Register the workflow definition **once** per session, instantiate **many times** per iteration. Avoids re-uploading and re-validating the file on every iteration, keeping cycle time low.

### 3. Pure Composition Layer
`transfers.py` has no dependencies on MCP or I/O. This enables:
- Offline testing and debugging
- Deterministic behavior (important for CI/testing)
- Reusable composition logic across agents

### 4. Column-Based Iteration Tracking
Plate layout uses columns for iterations: column 2 = iter 1, column 3 = iter 2, etc. Column 1 reserved for seed wells. This simplifies bookkeeping and OD600 queries.

### 5. Cumulative Monitoring
`monitoring_wells` grows each iteration (cumulative). This allows later iterations to re-read earlier wells if needed, and ensures no data is lost if a read is missed.

### 6. JSON Serialization for MCP Inputs
Transfer arrays, well lists, and other data structures are JSON-serialized before passing to `instantiate_workflow()`. The workcell DSL parses them on execution. Ensures type safety across HTTP boundary.

---

## Extension Points

### Algorithm Variations
Replace gradient descent with:
- **Bayesian Optimization:** Compute acquisition function instead of gradient, return new composition
- **Random Search:** Random walk in composition space (baseline)
- **DOE:** Design of Experiments for initial exploration, then refinement
- **Evolutionary:** Population-based algorithms

All use same `generate_transfer_array()` → `instantiate_workflow()` pipeline.

### Custom Workflows
Agents can define custom `workflow_definition_*.py` files for:
- Different plate layouts
- Alternative routine sequences
- Custom monitoring strategies
- Multi-plate experiments

Upload via `register_workflow()` with a new `definition_id`.

### Custom Reagents
Modify `REAGENT_WELLS` and stock plate layout:
- Different supplements (KCl, Phosphate, etc.)
- Different concentrations
- Different well assignments

Requires physical stock plate preparation and workcell registration.

---

## Dependencies

**Runtime:**
- `requests>=2.28` — HTTP client for MCP and REST API calls

**Build:**
- `python>=3.11`
- `setuptools>=68.0`

**Dev:**
- `pytest>=7.0` — Unit testing
- `ruff>=0.4` — Code linting

---

## Workcell Constraints (Reflected in Code)

| Constraint | Impact | Code Location |
|-----------|--------|---------------|
| Max 40 transfers/iteration | Transfer array limit | `_MAX_TRANSFERS` in template |
| Max 1 concurrent workflow | Sequential polling | `poll_workflow_completion()` blocks |
| Plate capacity: 96 wells | Column-based layout | Column 2–12 for iterations |
| 180 µL well volume | Supplement limit (max 90 µL each) | `apply_constraints()` |
| Pipette ranges: P50 (1–50), P200 (51–200), P1000 (201–1000) µL | Tip assignment | `compute_tip_consumption()` |
| Base media minimum: 90 µL | Constraint enforcement | `apply_constraints()` |
| Tip reuse: Novel Bio well (D1) only | Transfer ordering | `generate_transfer_array()` sorts D1 first |
| Operator approval required | First iterations may require manual approval | `poll_workflow_completion()` timeout |

---

## File Manifest

```
monomer/
  __init__.py              — Public API exports
  mcp_client.py            — McpClient class (Layer 1)
  workflows.py             — Workflow orchestration (Layer 2)
  transfers.py             — Media composition & transfer generation (Layer 3)
  datasets.py              — OD600 fetching & parsing (Layer 4)

track-2a-closed-loop/
  README.md                — Track 2A documentation
  examples/
    basic_agent.py         — Minimal closed-loop optimizer (Entry point)
    workflow_definition_template.py  — Workcell-side workflow DSL

pyproject.toml             — Package metadata & dependencies
README.md                  — Repository overview
CLAUDE.md                  — AI assistant context (platform details, constraints)
```
