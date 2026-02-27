# Monomer Bio Hackathon — Directory Structure & Conventions

---

## Project Root Layout

```
/Users/carter/monomer-bio-hackathon-march14-15/
├── .git/                          # Git repository (commit history)
├── .gitignore                      # Git ignore rules
├── .claude/                        # Claude Code config
├── .conductor/                     # Conductor/automation tools (unused)
├── .planning/                      # Planning & analysis docs
│   └── codebase/                   # This directory
│       ├── ARCHITECTURE.md         # System design & layers
│       └── STRUCTURE.md            # This file
│
├── monomer/                        # MAIN: Python client library
│   ├── __init__.py                 # Public API exports
│   ├── mcp_client.py               # MCP communication (JSON-RPC over HTTP)
│   ├── workflows.py                # Workflow registration & instantiation
│   ├── transfers.py                # Media composition & transfer generation
│   ├── datasets.py                 # OD600 result fetching
│   └── __pycache__/                # Python bytecode cache (ignored)
│
├── track-1-research/               # Research track (placeholder)
│   ├── README.md
│   ├── biology.md                  # Biology references
│   └── research-questions.md
│
├── track-2a-closed-loop/           # ACTIVE: Gradient descent agent
│   ├── README.md                   # Track 2A full documentation
│   └── examples/
│       ├── basic_agent.py          # Main entry point (minimal optimizer)
│       ├── workflow_definition_template.py  # Workcell-side workflow DSL
│       └── __pycache__/
│
├── track-2b-protocol-dev/          # Protocol dev track (placeholder, TBD)
│   └── README.md
│
├── track-2c-physical-ai/           # Physical AI track (placeholder, TBD)
│   └── README.md
│
├── pyproject.toml                  # Python package metadata & dependencies
├── README.md                        # Repository overview
└── CLAUDE.md                        # AI assistant context (platform, constraints, MCP tools)
```

---

## Core Library: `monomer/`

Pure Python client library for workcell communication and media optimization.

### `__init__.py` (35 lines)
**Purpose:** Public API exports

**Exports:**
- `McpClient` — HTTP JSON-RPC client for workcells
- `fetch_absorbance_results`, `parse_od_results` — Data acquisition
- `register_workflow`, `instantiate_workflow`, `poll_workflow_completion` — Workflow control
- `ROWS`, `SUPPLEMENT_NAMES`, `ROWS`, `generate_transfer_array`, `compute_tip_consumption`, `compute_novel_bio`, `apply_constraints`, `make_perturbed` — Media composition

**Pattern:** Re-exports from submodules for clean API surface.

### `mcp_client.py` (132 lines)
**Purpose:** Low-level workcell communication via JSON-RPC 2.0 over HTTP

**Key Class:** `McpClient`

**Methods:**
- `__init__(base_url=None)` — Initialize (default: `http://192.168.68.55:8080`). No network call yet.
- `connect()` — Perform MCP initialize handshake, obtain session ID. Called automatically on first `call_tool()`.
- `call_tool(tool_name, arguments, timeout=30)` — Call a workcell tool, parse SSE response, return result.

**Implementation Details:**
- Uses `requests` library for HTTP POST to `/mcp` endpoint
- Session ID obtained from response header `mcp-session-id`
- Parses SSE (Server-Sent Events) response: extracts `data: {...}` lines
- Handles both `structuredContent` and text `content` response formats
- Auto-reconnect on first call if no session yet exists
- Raises `RuntimeError` on MCP errors or malformed responses

**Error Handling:**
- `resp.raise_for_status()` — HTTP error codes
- `RuntimeError` — Missing session ID, MCP tool errors, unparseable responses

**Example Usage:**
```python
from monomer.mcp_client import McpClient

client = McpClient("http://192.168.68.55:8080")
plates = client.call_tool("list_culture_plates", {})
```

### `workflows.py` (135 lines)
**Purpose:** High-level workflow orchestration

**Functions:**

1. **`register_workflow(client, workflow_path, name="Hackathon GD Agent")`** (26 lines)
   - Upload workflow Python file via `create_workflow_definition_file`
   - Register named DB record via `register_workflow_definition`
   - Poll `list_workflow_definitions` until newly registered definition appears
   - Return `definition_id` (integer)
   - **Called once per session**

   **Error Handling:** Raises `RuntimeError` if definition not found after registration

2. **`instantiate_workflow(client, definition_id, plate_barcode, extra_inputs=None, reason="")`** (34 lines)
   - Create workflow instance with inputs dict: `{"plate_barcode": ..., **extra_inputs}`
   - Call MCP tool `instantiate_workflow`
   - Extract and return instance `uuid` (string)
   - **Called once per iteration**

   **Error Handling:** Raises `RuntimeError` if UUID not returned

3. **`poll_workflow_completion(client, uuid, timeout_minutes=180, poll_interval=30, on_status=None)`** (38 lines)
   - Poll `get_workflow_instance_details(instance_uuid=uuid)` every `poll_interval` seconds
   - Check status field: terminal if in `("completed", "failed", "cancelled", "canceled")`
   - Optional callback: `on_status(status, elapsed_seconds)` called each poll
   - Block until terminal state or timeout (default 180 min = 3 hours)
   - Return final instance dict
   - **Blocks entire function**

   **Error Handling:** Raises `TimeoutError` if deadline exceeded

**Defaults:**
```python
DAEMON_POLL_INTERVAL = 30        # seconds between polls
WORKFLOW_TIMEOUT_MINUTES = 180   # 3 hours max per iteration
```

**Example Usage:**
```python
from monomer.workflows import register_workflow, instantiate_workflow, poll_workflow_completion

def_id = register_workflow(client, Path("workflow_template.py"), name="My Agent")
uuid = instantiate_workflow(client, def_id, "GD-R1-20260314",
                            extra_inputs={"transfer_array": "[[...]]"})
result = poll_workflow_completion(client, uuid, timeout_minutes=180)
```

### `transfers.py` (212 lines)
**Purpose:** Pure computation for media composition and transfer array generation

**Constants:**
```python
ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]

ROW_LABELS = {
    "A": "control",
    "B": "center",
    "C": "glucose_rep1", "D": "glucose_rep2",
    "E": "nacl_rep1",    "F": "nacl_rep2",
    "G": "mgso4_rep1",   "H": "mgso4_rep2",
}

REAGENT_WELLS = {
    "Glucose": "A1",
    "NaCl": "B1",
    "MgSO4": "C1",
    "Novel_Bio": "D1",
}

SUPPLEMENT_NAMES = ["Glucose", "NaCl", "MgSO4"]

# Volume constraints (µL)
WELL_VOLUME_UL = 180
MIN_SUPPLEMENT_UL = 1
MAX_SUPPLEMENT_UL = 90
MIN_NOVEL_BIO_UL = 90

DELTA_UL = 10                              # Default perturbation size
REUSE_TIP_SOURCE_WELLS = ["D1"]            # Novel_Bio only
```

**Functions:**

1. **`compute_novel_bio(supplements, well_volume=180)`** (1 line)
   - Return remaining volume: `well_volume - sum(supplements.values())`
   - Assumes supplements dict contains Glucose, NaCl, MgSO4 keys

2. **`apply_constraints(supplements, supplement_names, min_ul, max_ul, min_novel_bio, well_volume, delta)`** (33 lines)
   - Clamp each supplement to [0] ∪ [min_ul, max_ul] (default [0] ∪ [1, 90])
   - Ensure Novel Bio >= min_novel_bio (default 90)
   - If constraint violated, iteratively reduce largest supplement by delta until valid
   - Return adjusted composition dict

3. **`make_perturbed(center, supplement_name, delta)`** (6 lines)
   - Create perturbed composition: copy center, add delta to one supplement
   - Apply constraints to ensure validity
   - Return perturbed dict

4. **`generate_transfer_array(center, column_index, delta=10, reagent_wells, supplement_names)`** (68 lines)
   - Generate complete set of transfers for one column (8 rows)
   - Layout:
     - Row A: Control (180 µL Novel Bio)
     - Row B: Center point
     - Rows C-H: 6 perturbations (2 reps × 3 supplements)
   - Sort transfers by source well: Novel Bio (reuse 1 tip) then supplements
   - Return list of `[source_well, dest_well, volume_µL]` triples

   **Transfer Grouping Logic:**
   - Novel_Bio (D1) first → all transfers grouped for single tip reuse
   - Then MgSO4 (C1), NaCl (B1), Glucose (A1) → fresh tips per transfer

5. **`compute_tip_consumption(transfer_array, reuse_source_wells=None)`** (34 lines)
   - Determine pipette for each unique source well: p50 (≤50 µL), p200 (51–200 µL), p1000 (>200 µL)
   - Count reused tips (one per source in reuse_set) + single-use tips (one per transfer)
   - Return dict: `{"p50": count, "p200": count, "p1000": count}`

   **Example:**
   ```
   Novel Bio at 150 µL → p200, reused (1 tip)
   Glucose at 20 µL, 25 µL → p50 (2 tips, separate sources or single reuse)
   NaCl at 80 µL × 8 wells → p200 (8 single-use tips, not reused)
   ```

**Design Principles:**
- All values are **integers** (µL resolution)
- All functions **pure** (no side effects, no I/O)
- Constraints enforced consistently to prevent hardware errors
- Transfer ordering optimized for tip efficiency

### `datasets.py` (152 lines)
**Purpose:** Fetch and parse OD600 growth measurements from workcell REST API

**Constants:**
```python
API_HEADERS = {
    "Content-Type": "application/json",
    "X-Monomer-Client": "desktop-frontend",  # Required by API middleware
}

ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]
SUPPLEMENT_NAMES = ["Glucose", "NaCl", "MgSO4"]
```

**Functions:**

1. **`get_plate_uuid(client, plate_barcode)`** (6 lines)
   - Call MCP `list_culture_plates`
   - Find plate matching barcode
   - Return UUID string
   - **Raises RuntimeError** if not found

2. **`fetch_absorbance_results(client, plate_barcode, column_index, rows)`** (32 lines)
   - Get plate UUID via `get_plate_uuid()`
   - Query REST API: `GET /api/datasets/?verbose=1&ordering=-createdAt`
   - Filter for OD600 datasets (wavelength=600 nm) matching plate UUID
   - Extract well data for target column (column_index)
   - Return dict: `{"baseline": {well: od600}, "endpoint": {well: od600}}`

   **Error Handling:**
   - Raises `RuntimeError` if no OD600 datasets found
   - Raises `RuntimeError` if no readings for target column

3. **`parse_od_results(absorbance_results, column_index, rows, supplement_names)`** (44 lines)
   - Compute delta OD: `endpoint - baseline` for each well
   - Extract:
     - `control_od` — delta for well A{col} (Row A, target column)
     - `center_od` — delta for well B{col} (Row B)
     - `perturbed_ods` — deltas for C-H, grouped by supplement (2 reps each)
     - `abs_control_od` — absolute endpoint for logging
     - `abs_center_od` — absolute endpoint for logging
   - Return structured dict

   **Row Mapping:**
   - Rows C, D → Glucose perturbations
   - Rows E, F → NaCl perturbations
   - Rows G, H → MgSO4 perturbations

**Example Response:**
```python
{
    "baseline": {
        "A2": 0.05, "B2": 0.06, "C2": 0.05, "D2": 0.06,
        "E2": 0.05, "F2": 0.06, "G2": 0.05, "H2": 0.06,
    },
    "endpoint": {
        "A2": 1.6, "B2": 2.3, "C2": 2.5, "D2": 2.4,
        "E2": 1.2, "F2": 1.3, "G2": 1.9, "H2": 1.8,
    },
}

# After parse_od_results:
{
    "control_od": 1.55,           # 1.6 - 0.05
    "center_od": 2.24,            # 2.3 - 0.06
    "perturbed_ods": {
        "Glucose": [2.45, 2.34],  # (2.5-0.05), (2.4-0.06)
        "NaCl": [1.15, 1.24],
        "MgSO4": [1.85, 1.74],
    },
    "abs_control_od": 1.6,
    "abs_center_od": 2.3,
}
```

---

## Track 2A: Closed-Loop Agent

### `track-2a-closed-loop/README.md` (244 lines)
**Purpose:** Track 2A complete documentation and setup guide

**Sections:**
1. The Flow — 5-step iteration overview
2. Cold reagent handling — Temperature considerations
3. MCP Setup — Config for Claude Code, Cursor, other tools
4. Quick Start — Install & test connectivity
5. Building Your Agent — Design, generate, register, instantiate, read results, loop
6. Workflow Definition Format — Parameter documentation
7. Workcell Constraints — Approval, concurrency, volume limits, reagent tracking

**Key Sections for Agents:**
- Step 1–5 of iteration loop (generate → submit → wait → read → update)
- Gradient descent example implementation
- Workflow parameter definitions
- Tip consumption & constraints

### `track-2a-closed-loop/examples/basic_agent.py` (205 lines)
**Purpose:** Minimal closed-loop gradient descent optimizer (main entry point)

**Flow:**
1. Parse command-line args: `--plate`, `--iterations`, `--workcell`
2. Create MCP client
3. Register workflow definition **once** (line 61–66)
4. Loop N iterations:
   - Generate transfer array (line 97–99)
   - Instantiate workflow (line 106–121)
   - Poll for completion (line 126–131)
   - Fetch OD600 results (line 135–136)
   - Compute gradient & update center (line 157–169)
5. Save run history to `runs/history.json`

**Agent Parameters:**
```python
LEARNING_RATE = 5      # µL adjustment per unit gradient
DELTA_UL = 10          # Perturbation size
```

**State Tracking:**
- `center` — Current best media composition (dict)
- `monitoring_wells` — Cumulative list of wells read so far
- `history` — Record of all iterations (list of dicts)

**Logging:**
- INFO level, ASCII-formatted timestamps
- Iteration summaries, gradient computations, status updates

**Output:**
- `runs/history.json` — Full iteration history with compositions, OD600 results

**Usage:**
```bash
python examples/basic_agent.py --plate GD-R1-20260314 --iterations 5 --workcell http://192.168.68.55:8080
```

**Exit Behavior:**
- Logs final center composition
- Returns `(center, history)` tuple
- Exits with code 0 on success

### `track-2a-closed-loop/examples/workflow_definition_template.py` (~300+ lines)
**Purpose:** Workcell-side workflow definition (Python DSL, executed on workcell)

**WARNING:** Not meant to be run locally (imports resolve only on workcell).

**Key Components:**

1. **Docstring (97 lines)** — Comprehensive usage guide
   - HOW TO USE — Register once, instantiate many times
   - WHAT YOUR AGENT MUST PRODUCE — Transfer array, dest_wells, monitoring_wells, seed_well, next_seed_well, reagent_type
   - PLATE LAYOUT CONVENTIONS — Reagent well map, experiment plate columns
   - IMPORTANT: WELL REUSE — Agent responsible for tracking occupied wells

2. **Internal Helpers (97 lines)**
   - `_compute_tip_counts()` — Calculate P50/P200/P1000 tip consumption from transfer array
   - `_validate()` — Pre-submission validation (transfer count, well conflicts, volumes)

3. **`build_definition()` function**
   - **Parameters:**
     - `plate_barcode` — Always required
     - `transfer_array` — JSON string of transfers (default: empty)
     - `dest_wells` — JSON string of destination wells (default: column 2)
     - `monitoring_wells` — JSON string of all wells to read (default: column 2)
     - `seed_well` — Warm seed well on experiment plate (default: "A1")
     - `next_seed_well` — Well to pre-warm for next round (default: "B1")
     - `nm_cells_source_well` — Source for pre-warming (default: "A2")
     - `reagent_type` — Stock plate tag (default: "GD Compound Stock Plate")
     - `monitoring_readings` — Number of OD600 reads (default: 9 = 90 min window)
     - `monitoring_interval_minutes` — Interval between reads (default: 10 min)

   - **Returns:** `WorkflowDefinitionDescriptor`
   - **Execution:** Runs on workcell, not locally

   - **Routine Sequence:**
     - Validate inputs
     - Compute tip consumption
     - Generate routine reference for **GD Iteration Combined**:
       - Transfers reagents from stock to experiment wells
       - Seeds cells from warm well
       - Pre-warms next seed well with NM+Cells
     - Generate routine reference for **Measure Absorbance** (9 reads, 10 min intervals)
     - Return workflow descriptor with routines

4. **Constants**
   ```python
   _SEED_TRANSFER_UL = 20          # µL seeded per well
   _SEED_MIX_VOL_UL = 100          # µL used to resuspend
   _SEED_MIX_REPS = 5              # pipette mix reps
   _NM_CELLS_VOL_UL = 220          # µL for next seed well
   _MAX_TRANSFERS = 40             # Hard cap per iteration
   ```

**Validation Enforced:**
- Transfer count <= 40
- dest_wells non-empty, <= 96 wells
- All dest_wells referenced in transfer_array
- monitoring_wells non-empty
- seed_well non-empty, not in dest_wells
- All volumes positive

---

## Supporting Files

### `pyproject.toml` (20 lines)
**Purpose:** Python package metadata

**Key Fields:**
- `name = "monomer"` — Package name
- `version = "0.1.0"` — Version
- `requires-python = ">=3.11"` — Python 3.11+
- **Dependencies:** `requests>=2.28`, `python-dotenv>=1.0`
- **Dev Dependencies:** `pytest>=7.0`, `ruff>=0.4`

### `README.md` (44 lines)
**Purpose:** Repository overview

**Sections:**
1. Intro — Q1 2026 AI Scientist Hackathon, Track 2
2. Tracks — Links to Track 1 (Elnora), Track 2A (Monomer MCP), Track 2B (Hamilton), Track 2C (UR10e)
3. Track 2A: Monomer MCP Setup — Install, start here
4. Repository Structure — Directory layout & file descriptions

### `CLAUDE.md` (250+ lines)
**Purpose:** AI assistant context (API tokens, constraints, platform details)

**Sections:**
1. Media Composition — Component volumes, reagent well map, constraints
2. Platform Primitives — Workflow hierarchy, available routines, plate barcode convention
3. MCP Connection — Two endpoints (Autoplat, Monitor), tool list, MCP resources, REST endpoints
4. Python Library — McpClient, workflows.py, datasets.py, transfers.py usage
5. Workcell Constraints — Concurrent workflow limit, transfer limit, pipette ranges, tip reuse, reagent storage

**Audience:** AI models (Claude Code, Cursor, etc.) assisting contestants

---

## Naming Conventions

### Well Coordinates
- **Format:** `{ROW}{COLUMN}` (uppercase, no separators)
  - Row: A–H (8 rows in 96-well plate)
  - Column: 1–12 (12 columns, but only 2–12 used for experiments)
- **Examples:** "A1", "H12", "B2"
- **Special:** Column 1 reserved for seed wells; columns 2–12 for iterations

### Plate Barcodes
- **Format:** `{PREFIX}-R{ROUND}-{YYYYMMDD}`
- **Example:** `GD-R1-20260314` (Gradient Descent, Round 1, March 14 2026)

### Reagent Type Tags
- **Example:** `"GD Compound Stock Plate"`
- **Meaning:** Custom reagent plate registered on workcell
- **Usage:** Passed as `reagent_type` parameter to workflows
- **Coordination:** Monomer team registers tag when plate is loaded

### Supplement Names
- **Standard:** `"Glucose"`, `"NaCl"`, `"MgSO4"` (exact spelling, capital first letter)
- **Defined in:** `SUPPLEMENT_NAMES` constant

### Column Indexing (Iteration Mapping)
- **Iteration 1** → Column 2 (Column 1 = seed wells)
- **Iteration N** → Column N+1
- **Formula:** `column_index = iteration + 1`

---

## Code Style & Patterns

### Import Organization
- Standard library first
- Third-party (requests, etc.)
- Type hints via `from __future__ import annotations` (top of file)
- `TYPE_CHECKING` for import-time type hints only

**Example:**
```python
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from monomer.mcp_client import McpClient
```

### Function Docstrings
- Triple-quoted, NumPy-style
- Include Usage section (examples)
- Specify error conditions & raises
- Document parameter types & default values

**Example:**
```python
def register_workflow(
    client: McpClient,
    workflow_path: Path,
    name: str = "Hackathon GD Agent",
) -> int:
    """Register a workflow definition via MCP.

    :param client: Connected MCP client.
    :param workflow_path: Path to workflow_definition_template.py.
    :param name: Human-readable name shown in Monomer UI.
    :returns: Workflow definition database ID.
    """
```

### Constants
- UPPERCASE_WITH_UNDERSCORES for module-level constants
- Grouped with comments (`# ── Section Name ──`)
- Document constraints & units

### Type Hints
- Use type hints for function signatures
- Support Python 3.11+ (no pipe unions in annotations)
- Avoid `Any` if possible; prefer `dict` or `list`

---

## Execution Model

### Session Lifecycle
1. **Import:** `from monomer import McpClient, register_workflow, ...`
2. **Connect:** `client = McpClient(url)` (no network yet)
3. **Register:** `def_id = register_workflow(client, path)` (uploads file, registers, returns ID)
4. **Iterate Loop:**
   - Generate transfers
   - `instantiate_workflow(client, def_id, ...)`
   - `poll_workflow_completion(client, uuid)`
   - Fetch results, compute gradient
5. **Cleanup:** Save history, log results

### Per-Iteration Timing (Typical)
- Generate transfers: < 1 sec
- Instantiate: 1–5 sec (approval queue, may require operator action)
- Approval wait: 5–30 min (operator must approve first few iterations)
- Workflow execution: 60–90 min (liquid handling + 90 min monitoring)
- Fetch results: 5–10 sec
- Gradient update: < 1 sec
- **Total per iteration:** ~2 hours (bottleneck: biological growth + operator approval)

### Error Recovery
- **Network error:** Automatic retry on next `call_tool()` (reconnect handshake)
- **Workflow fails:** Instance status set to "failed", `poll_workflow_completion()` returns immediately
- **Timeout:** `TimeoutError` raised after deadline
- **Agent should:** Check workflow details, fix input, resubmit (new iteration)

---

## Testing Approach

### Unit Testable (Pure Functions)
- `apply_constraints()` — Clamping logic
- `generate_transfer_array()` — Transfer generation
- `make_perturbed()` — Perturbation logic
- `compute_tip_consumption()` — Tip counting

**Example:**
```python
def test_apply_constraints():
    result = apply_constraints({"Glucose": 100, "NaCl": 100, "MgSO4": 100})
    assert result["Glucose"] == 90  # Max 90 µL
    assert result["NaCl"] == 90
    assert result["MgSO4"] == 0     # Reduced to fit 90 µL Novel Bio minimum
    assert sum(result.values()) + 90 == 180  # Total 180 µL
```

### Integration Testable (With Mock Workcell)
- `McpClient.call_tool()` — Mock HTTP responses
- `register_workflow()`, `instantiate_workflow()`, `poll_workflow_completion()` — Mock MCP calls
- Full agent loop — Simulate MCP responses, verify request sequence

### Not Testable Offline
- `fetch_absorbance_results()` — Requires live REST API
- `poll_workflow_completion()` timeout behavior — Requires waiting
- Hardware execution (transfers, reads) — Requires physical workcell

---

## File Sizes (Approximate)

| File | Lines | Purpose |
|------|-------|---------|
| `mcp_client.py` | 132 | HTTP JSON-RPC client |
| `workflows.py` | 135 | Workflow orchestration |
| `transfers.py` | 212 | Media composition & transfer generation |
| `datasets.py` | 152 | OD600 fetching & parsing |
| `__init__.py` | 35 | Public API |
| **Subtotal: `monomer/`** | **666** | **Core library** |
| `basic_agent.py` | 205 | Minimal optimizer |
| `workflow_definition_template.py` | 300+ | Workcell DSL (partial read) |
| **Subtotal: `track-2a-closed-loop/examples/`** | **500+** | **Agent implementation** |
| **Track 2A README** | 244 | Documentation |
| **CLAUDE.md** | 250+ | AI context |
| **Repository README** | 44 | Overview |

---

## Entry Points for Contestants

### For Python Development
- **Start:** `python examples/basic_agent.py --plate GD-R1-20260314 --iterations 5`
- **Extend:** Copy `basic_agent.py`, implement custom optimization algorithm
- **Debug:** Inspect `runs/history.json`, use MCP tools directly via `McpClient`

### For Interactive Development
- **CLI:** Use `python -c "from monomer import *; ..."` or Jupyter notebook
- **MCPTools:** Call tools directly via `client.call_tool()`
- **Monitoring:** Check workcell UI, query REST API at `http://192.168.68.55:8080/api/datasets/`

### For Debugging
- **Workflow validation:** Call `client.call_tool("validate_workflow_definition_file", {"file_name": "..."})`
- **Plate status:** Call `client.call_tool("list_culture_plates", {})`
- **Reagent availability:** Call `client.call_tool("list_reagent_plates", {})`
- **Pending workflows:** Call `client.call_tool("list_pending_workflows", {})`
