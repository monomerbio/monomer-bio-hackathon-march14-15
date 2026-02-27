# Monomer Bio Hackathon — Code Conventions

## Overview
This codebase follows modern Python conventions with emphasis on clarity, type safety, and domain-specific documentation. The project is organized as a Python library (`monomer/`) with example applications, designed to run against a remote workcell MCP server.

---

## Python Style and Formatting

### PEP 8 Compliance
- **Line length:** 88 characters (implicit from usage, no explicit ruler found)
- **Indentation:** 4 spaces (no tabs)
- **Import style:** `from __future__ import annotations` at top of every module for forward references

### Type Hints
- **Mandatory for public APIs:** All function signatures in public modules include type hints
- **Optional for internal helpers:** Internal functions (prefix `_`) may use hints sparingly
- **Late-binding imports:** Use `TYPE_CHECKING` blocks to avoid circular dependencies at runtime

**Example from `workflows.py`:**
```python
if TYPE_CHECKING:
    from monomer.mcp_client import McpClient

def register_workflow(
    client: McpClient,
    workflow_path: Path,
    name: str = "Hackathon GD Agent",
) -> int:
```

### Docstrings
- **Module level:** All files start with a module docstring describing purpose and context
- **Google-style docstrings:** Functions use inline documentation with sections
- **Inline examples:** Code examples in docstrings use `::` notation

**Example from `mcp_client.py`:**
```python
class McpClient:
    """MCP client that calls tools via HTTP Streamable Transport.

    The workcell's FastMCP server is mounted at /mcp and accepts JSON-RPC 2.0
    tool calls over HTTP POST. Each session requires an initialize handshake.

    Usage::

        client = McpClient("http://192.168.68.55:8080")
        client.connect()
        plates = client.call_tool("list_culture_plates", {})
    """
```

---

## Naming Conventions

### Module and Package Names
- **Lowercase with underscores:** `mcp_client`, `transfers`, `datasets`
- **Public vs. internal:** No `__` prefix; internal helpers use `_` prefix
- **`__all__` exports:** All public modules export an explicit `__all__` list

From `__init__.py`:
```python
__all__ = [
    "McpClient",
    "fetch_absorbance_results",
    "parse_od_results",
    ...
]
```

### Constants
- **Uppercase with underscores:** `ROWS`, `WELL_VOLUME_UL`, `MAX_SUPPLEMENT_UL`
- **Domain-specific suffixes:** Constants include units (`_UL` for microliters, `_MINUTES` for time)
- **Grouped at module top:** All module-level constants appear before function definitions

From `transfers.py`:
```python
ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]
WELL_VOLUME_UL = 180
MIN_SUPPLEMENT_UL = 1
MAX_SUPPLEMENT_UL = 90
DELTA_UL = 10
```

### Function and Variable Names
- **Snake_case:** `generate_transfer_array()`, `compute_tip_consumption()`, `parse_od_results()`
- **Verb-first for actions:** `fetch_absorbance_results()`, `apply_constraints()`
- **Descriptive parameters:** `well_volume`, `supplement_names`, `column_index` (not `wv`, `supp`, `col`)

### Class Names
- **PascalCase:** `McpClient`, `RoutineReference`, `WorkflowDefinitionDescriptor`

---

## Organization and Structure

### Module Organization
**Logical grouping within files:**

1. **Imports** (with `from __future__` first)
2. **Module docstring**
3. **Constants** (uppercase)
4. **Helper functions** (private, prefixed with `_`)
5. **Public API functions** (exported in `__all__`)

**Example from `transfers.py`:**
```
[module docstring]
[imports]
[constants: ROWS, ROW_LABELS, REAGENT_WELLS, SUPPLEMENT_NAMES, volume constraints]
[composition helpers: compute_novel_bio, apply_constraints, make_perturbed]
[transfer array generation: generate_transfer_array, compute_tip_consumption]
```

### File Structure
```
monomer/
  __init__.py          # Package exports, __all__ list
  mcp_client.py        # Low-level MCP communication (JSON-RPC 2.0)
  workflows.py         # Register, instantiate, poll workflows
  transfers.py         # Media composition and transfer array generation
  datasets.py          # OD600 result fetching and parsing

track-2a-closed-loop/examples/
  basic_agent.py       # Full closed-loop agent example
  workflow_definition_template.py  # Workflow definition template (runs on workcell)
```

---

## Error Handling

### Exceptions
- **Raises on missing data:** Functions raise `RuntimeError` with descriptive messages when required data is absent

**From `datasets.py`:**
```python
def get_plate_uuid(client: McpClient, plate_barcode: str) -> str:
    """Look up a culture plate's UUID from its barcode via MCP."""
    plates = client.call_tool("list_culture_plates", {})
    for p in plates:
        if p.get("barcode") == plate_barcode:
            return p.get("uuid", "")
    raise RuntimeError(f"Plate '{plate_barcode}' not found on workcell")
```

- **Assertion validation:** Workflow validation uses `assert` with descriptive messages

**From `workflow_definition_template.py`:**
```python
assert len(transfers) <= _MAX_TRANSFERS, (
    f"Too many transfers ({len(transfers)}): max is {_MAX_TRANSFERS}. "
    "Reduce the number of conditions or reagents per iteration."
)
```

- **Custom exception handling:** MCP client catches and re-raises with context

**From `mcp_client.py`:**
```python
if result.get("isError"):
    error_text = result.get("content", [{}])[0].get("text", "Unknown error")
    raise RuntimeError(f"MCP tool error: {error_text}")
```

---

## Comments and Documentation

### Comment Style
- **Inline comments:** Use `#` with space, brief and on same line or above
- **Section headers:** Use `# ── Title ────` format for visual separation

**From `basic_agent.py`:**
```python
# ── Paths ────────────────────────────────────────────────────────────────────
WORKFLOW_TEMPLATE = Path(__file__).parent / "workflow_definition_template.py"

# ── Agent parameters ─────────────────────────────────────────────────────────
LEARNING_RATE = 5    # µL to adjust per unit gradient
DELTA_UL = 10        # perturbation size for gradient estimation
```

### Domain Context Comments
- **Lengthy explanations in docstrings:** Detailed logic lives in module/function docstrings
- **Why-focused:** Comments explain intent, not obvious code

**From `workflow_definition_template.py`:**
```python
# Phase 1 — Liquid handling: transfer reagents from stock plate to
# experimental wells, seed cells from warm seed well,
# pre-warm next seed well with NM+Cells.
```

---

## Conventions for Domain-Specific Code

### Media Composition
- **Wells and volumes:** All well references use `<Row><Col>` format (e.g., `A1`, `H12`)
- **Volumes in microliters:** Always include `_UL` suffix in constant names
- **Composition dicts:** Use supplement names as keys (e.g., `{"Glucose": 20, "NaCl": 10}`)

From `transfers.py`:
```python
SUPPLEMENT_NAMES = ["Glucose", "NaCl", "MgSO4"]
center = {"Glucose": 20, "NaCl": 10, "MgSO4": 15}
```

### Transfer Arrays
- **Format:** Always `[[source_well, dest_well, volume_uL], ...]`
- **Source wells:** Reagent plate locations (e.g., `A1`, `D1`)
- **Destination wells:** Experiment plate locations (e.g., `A2`, `H12`)
- **JSON serialization:** Transfer arrays are serialized with `json.dumps()` when passed to workflows

From `basic_agent.py`:
```python
transfers = generate_transfer_array(center, column_index=column_index, delta=DELTA_UL)
extra_inputs={
    "transfer_array": json.dumps(transfers),
    ...
}
```

### Workflow Parameters
- **JSON strings for arrays:** Complex types (`transfer_array`, `dest_wells`, `monitoring_wells`) are JSON-serialized
- **Plain strings for scalars:** Plate barcodes and well IDs are passed as plain strings
- **Explicit defaults:** All optional parameters have explicit defaults in function signatures

From `workflow_definition_template.py`:
```python
def build_definition(
    plate_barcode: str,
    transfer_array: str = "[]",
    dest_wells: str = '["A2","B2","C2","D2","E2","F2","G2","H2"]',
    monitoring_wells: str = '["A2","B2","C2","D2","E2","F2","G2","H2"]',
    ...
) -> WorkflowDefinitionDescriptor:
```

---

## Logging and Output

### Logger Setup
- **Per-module loggers:** Each example script sets up a logger with `logging.getLogger(__name__)`
- **INFO level default:** Logging starts at `INFO` level, showing key milestones

**From `basic_agent.py`:**
```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

log.info("Registering workflow definition...")
log.info("Registered workflow definition ID: %d", def_id)
```

### User Output
- **No print() statements:** All output goes through logging
- **Structured logging:** Use `%` formatting with appropriate types (int, float, str)

---

## Import Conventions

### Standard Organization
1. `from __future__ import annotations`
2. Standard library imports (alphabetical)
3. Third-party imports (alphabetical)
4. Local imports (alphabetical)
5. TYPE_CHECKING blocks

**From `datasets.py`:**
```python
from __future__ import annotations

from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from monomer.mcp_client import McpClient
```

### Absolute Imports
- **Always used:** Relative imports (`.` prefix) are not used
- **Package-qualified:** All imports reference the full `monomer.` namespace

---

## Testing Conventions (Observed)

### Current State
- **No test files found:** The codebase contains `pytest` in `dev` dependencies but no test files
- **Test framework configured:** `pyproject.toml` declares `pytest>=7.0` but tests don't exist yet

### Expected Test Structure (if added)
Based on configuration and code organization:

```
tests/
  test_mcp_client.py       # MCP client connection and error handling
  test_transfers.py        # Media composition and transfer array generation
  test_workflows.py        # Workflow registration and instantiation
  test_datasets.py         # OD600 parsing and result fetching
  conftest.py              # Pytest fixtures (mocked MCP client)
```

**Implicit testing expectations:**
- Unit tests for pure functions (`apply_constraints`, `generate_transfer_array`, `parse_od_results`)
- Integration tests for MCP client (mocked HTTP)
- Parametrized tests for composition constraints (boundary cases, edge cases)

---

## Summary of Key Principles

| Aspect | Convention |
|--------|-----------|
| **Line length** | 88 characters |
| **Type hints** | Mandatory for public APIs, use TYPE_CHECKING for circular deps |
| **Docstrings** | Module and function level, Google-style with examples |
| **Constants** | UPPERCASE_WITH_UNDERSCORES, include units |
| **Functions** | snake_case, verb-first, descriptive parameters |
| **Error handling** | RuntimeError for missing data, assert for validation |
| **Logging** | INFO level, no print() statements |
| **Comments** | Section headers with dashes, why-focused explanations |
| **Domain code** | Well references `<Row><Col>`, volumes with `_UL` suffix |
| **Transfer arrays** | Always JSON-serialized when passed to workflows |
| **Imports** | Absolute, future annotations first, TYPE_CHECKING blocks |

