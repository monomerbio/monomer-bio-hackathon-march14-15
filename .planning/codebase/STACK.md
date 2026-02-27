# Technology Stack — Monomer Bio Hackathon

## Overview

**Project:** Monomer Bio Q1 2026 AI Scientist Hackathon (Track 2 — Closed-loop autonomous agents)
**Type:** Python client library + AI agent framework for workcell control
**Scope:** HTTP-based MCP client, workflow orchestration, media optimization experiments

---

## Languages & Runtime

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | ≥3.11 | Core language, agent development |
| **JSON** | (standard) | RPC payloads, configuration, data exchange |
| **YAML** | (optional) | Not present; plain Python config files |

---

## Core Dependencies

### Production Dependencies
Defined in `pyproject.toml`:

```toml
dependencies = [
    "requests>=2.28",      # HTTP client for MCP JSON-RPC 2.0 calls
    "python-dotenv>=1.0",  # Environment variable loading (.env files)
]
```

### Development Dependencies
```toml
dev = [
    "pytest>=7.0",         # Unit testing framework
    "ruff>=0.4",           # Python linter/formatter
]
```

---

## Runtime Environment

### Python Environment Setup
```bash
pip install -e .  # Install monomer package in editable mode
```

### Configuration
- **Environment variables:** `WORKCELL_HOST` (default: `192.168.68.55`), `WORKCELL_PORT` (default: `8080`)
- **Dotenv support:** `python-dotenv` enables `.env` file loading for configuration
- **MCP Session:** Session ID obtained from HTTP response headers during initialization

---

## Architecture

### Module Structure

```
monomer/
  __init__.py              # Public API exports
  mcp_client.py            # MCP JSON-RPC 2.0 HTTP client
  workflows.py             # Workflow registration, instantiation, polling
  datasets.py              # OD600 absorbance result fetching (REST + MCP)
  transfers.py             # Transfer array generation, media composition helpers
```

### Key Frameworks & Patterns

**MCP (Model Context Protocol) 2.0 - JSON-RPC 2.0 Transport**
- Protocol: JSON-RPC 2.0 over HTTP POST
- Endpoint: `/mcp`
- Session management: Header-based session ID (`mcp-session-id`)
- Response format: Server-Sent Events (SSE) with JSON payloads

**REST API**
- Used for dataset/observation queries
- Endpoint: `/api/datasets/`
- Header: `X-Monomer-Client: desktop-frontend`
- Returns camelCase JSON (e.g., `resultsByWell`, `structuredData`)

**Workflow Definition System**
- Python files with `build_definition()` function
- Executed on workcell (FastMCP backend)
- Uses DSL classes: `WorkflowDefinitionDescriptor`, `RoutineReference`, `MoreThanConstraint`
- Validates before registration (no runtime compilation)

---

## HTTP Transport & Communication

### McpClient (`monomer/mcp_client.py`)

**Initialization Flow:**
1. `initialize` handshake → get session ID from response headers
2. `notifications/initialized` notification
3. Subsequent calls use session ID in headers

**Tool Call Pattern:**
```python
POST /mcp
Headers: {
  "Content-Type": "application/json",
  "Mcp-Session-Id": "<session_id>"
}
Body: {
  "jsonrpc": "2.0",
  "id": <auto-increment>,
  "method": "tools/call",
  "params": { "name": "<tool_name>", "arguments": {...} }
}
```

**Response Parsing:**
- SSE format: `event: message\ndata: {...}`
- Handles both `structuredContent` and text content
- Error checking: `result.isError` flag
- Timeout: 30 seconds per call (configurable)

### REST Endpoints

**Dataset Query:**
```
GET /api/datasets/?verbose=1&ordering=-createdAt
Headers: X-Monomer-Client: desktop-frontend
Returns: List of OD600 measurements, metadata, well readings
```

---

## Configuration & Secrets

### Default Workcell Address
- Host: `192.168.68.55` (local network, no external access)
- Port: `8080` (HTTP only)
- Environment overrides: `WORKCELL_HOST`, `WORKCELL_PORT`

### Cloud Monitor (Optional)
- URL: `https://backend-staging.monomerbio.com/mcp`
- Auth: Bearer token (obtained from cloud-staging.monomerbio.com)
- Read-only (observation/monitoring only)

### MCP Protocol Version
- Version: `2024-11-05` (used in initialize handshake)
- Client identification: `{"name": "monomer-python", "version": "0.1"}`

---

## Data Models & Domain Logic

### Transfer Array Format
```python
[
  [source_well, dest_well, volume_uL],  # e.g. ["D1", "A2", 150]
  ...
]
```

**Pipette Selection (by volume):**
- P50: 1–50 µL
- P200: 51–200 µL
- P1000: 201–1000 µL

### Media Composition
```python
{
  "Glucose": int,    # 0–90 µL
  "NaCl": int,       # 0–90 µL
  "MgSO4": int,      # 0–90 µL
  # Novel_Bio base: 180 − sum(supplements), min 90 µL
}
```

**Constraints:**
- Well volume: 180 µL (exact)
- Base media (Novel_Bio) minimum: 90 µL
- Each supplement: 0–90 µL (integer µL)
- Tip reuse: Only Novel_Bio well (D1) reuses 1 tip; others use fresh tips per transfer

### Plate & Well Conventions
- Format: 96-well flat plate (8 rows × 12 columns)
- Rows: A–H
- Columns: 1–12
- Column 1: Seed wells (pre-warmed, one per iteration)
- Columns 2–12: Experimental wells (8 per column, one column per iteration)
- Barcode format: `{PREFIX}-R{ROUND}-{YYYYMMDD}` (e.g., `GD-R1-20260314`)

### Reagent Plate Layout (24-well deep well)
- A1: Glucose stock
- B1: NaCl stock
- C1: MgSO4 stock
- D1: Novel_Bio (base media) — tip reused
- A2: NM+Cells (pre-mixed, warm seed well substrate)
- A12–H12: Single-use seed aliquots (pre-aliquoted per iteration)

---

## Build & Deployment

### Package Distribution
- **Format:** setuptools with legacy backend (`setuptools.backends._legacy:_Backend`)
- **Editable install:** `pip install -e .` (development workflow)
- **Package name:** `monomer`
- **Version:** `0.1.0`

### Pre-commit Hooks
- **Linter:** ruff (via pre-commit hook)
- **Type checker:** pyright (requires Python 3.13.11 via pyenv)
  - **Note:** Pre-commit hook fails if pyenv Python 3.13.11 not available; use `--no-verify` as workaround

### Testing
- **Framework:** pytest ≥7.0
- **Test discovery:** Standard pytest conventions (not visible in codebase; likely placeholder)

---

## Workflow & Routine System

### Workflow Definitions (Domain-Specific Language)
**Location:** `track-2a-closed-loop/examples/workflow_definition_template.py` (executed on workcell)

**Function Signature:**
```python
def build_definition(
    plate_barcode: str,
    transfer_array: str = "[]",
    dest_wells: str = "...",
    monitoring_wells: str = "...",
    seed_well: str = "A1",
    next_seed_well: str = "B1",
    reagent_type: str = "...",
    monitoring_readings: int = 9,
    ...
) -> WorkflowDefinitionDescriptor:
    # Returns ordered sequence of RoutineReferences
```

### Available Routines (Track 2A)

| Routine | Purpose | Key Parameters |
|---------|---------|-----------------|
| **GD Iteration Combined** | Reagent transfers + seed operations | `experiment_plate_barcode`, `reagent_type`, `transfer_array`, `seed_well`, `seed_dest_wells` |
| **AI Scientist Compound Plate Generation** | Build compound plate from stock | `compound_plate_barcode`, `reagent_type`, `transfer_array` |
| **Measure Absorbance** | Read OD600 | `culture_plate_barcode`, `method_name` (`96wp_od600`), `wells_to_process` |

**Execution Constraints:**
- Max 1 concurrent workflow (sequential scheduling)
- Max ~40 transfers per iteration (configurable)
- Platereader minimum interval: 5 minutes
- Incubation: 37°C
- Default monitoring: 10-minute intervals, 9 readings = 90-minute window

---

## Monitoring & Observation

### OD600 Results Format
```python
{
  "baseline": {well: od600_value},   # Earliest reading
  "endpoint": {well: od600_value},   # Latest reading
}
```

### Parsed Results (for optimization)
```python
{
  "control_od": float,           # Delta OD, control well (A)
  "center_od": float,            # Delta OD, center point (B)
  "perturbed_ods": {             # Delta OD for perturbations
    "Glucose": [rep1, rep2],
    "NaCl": [rep1, rep2],
    "MgSO4": [rep1, rep2]
  },
  "abs_control_od": float,       # Absolute endpoint (logging)
  "abs_center_od": float         # Absolute endpoint (logging)
}
```

---

## Utilities & Helpers

### Transfer Array Generation (`monomer/transfers.py`)

**Functions:**
- `generate_transfer_array()` — 3D gradient with perturbations (center ± delta on each axis)
- `apply_constraints()` — Validates composition (volumes, min/max, integer resolution)
- `make_perturbed()` — Single-axis perturbation from center point
- `compute_tip_consumption()` — Estimates tip count by pipette type

**Optimization Strategy:** Gradient descent (center point + 2 replicates per axis = 8 wells/column)

### Dataset Helpers (`monomer/datasets.py`)

**Functions:**
- `get_plate_uuid()` — Lookup UUID from barcode via MCP
- `fetch_absorbance_results()` — Query REST API for OD600 readings
- `parse_od_results()` — Convert raw readings to delta OD for optimization

---

## Integration Points

### Workcell Communication
1. **Local Autoplat MCP** (`http://192.168.68.55:8080/mcp`)
   - Workflow registration, instantiation, status polling
   - Routine listing, plate management
   - Session-based, stateful

2. **Cloud Monitor MCP** (optional, read-only)
   - Observation data, culture status updates
   - Requires Bearer token authentication

3. **Workcell REST API** (implicit via datasets.py)
   - Dataset querying (OD600 measurements)
   - Requires `X-Monomer-Client: desktop-frontend` header

### Agent Integration
- **Input:** Media composition (dict), iteration metadata
- **Output:** Transfer arrays (JSON), workflow instance UUIDs
- **Polling:** Status checks until completion
- **Feedback loop:** OD600 results → gradient computation → next iteration

---

## Logging & Debugging

### Logging Setup (in agent example)
```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
```

### Error Handling
- HTTP errors: `requests.raise_for_status()` in all API calls
- MCP errors: Checked via `result.isError` flag
- Timeout handling: Configurable per tool call (default 30s, workflow polling up to 180m)

---

## File Locations & Artifacts

### Source Code
- `monomer/` — Python client library
- `track-2a-closed-loop/examples/` — Agent reference implementation + workflow template

### Configuration
- `pyproject.toml` — Package metadata, dependencies
- `CLAUDE.md` — AI assistant context (media composition, workcell constraints)

### Runtime Artifacts
- `runs/history.json` — Agent iteration history (generated by basic_agent.py)
- `.env` — Environment variable overrides (optional, loaded via python-dotenv)

---

## Notes

- **No databases:** All data is transient or stored on workcell
- **No async/await:** Synchronous blocking I/O (requests library)
- **No threading:** Single-threaded agent loop
- **Cold reagent lag:** Stock plate at 4°C introduces 30–60 min growth delay; pre-warm in parallel if possible
- **MCP Resources:** Workcell provides DSL guides, schemas, examples via MCP resource protocol (not files)
