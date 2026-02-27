# Codebase Concerns & Technical Debt

Last Updated: 2026-02-27

## Summary

This is a hackathon project for the Monomer Bio Track 2A (closed-loop AI agent for gradient descent media optimization). The codebase is lightweight, focused, and relatively clean. However, there are several areas of concern ranging from missing error handling to hardcoded values and architectural gaps.

---

## Critical Issues (High Priority)

### 1. Hardcoded Workcell IP Address

**Severity:** HIGH - Production blocker

**Location:**
- `/Users/carter/monomer-bio-hackathon-march14-15/monomer/mcp_client.py:14-15`
- Multiple examples reference `192.168.68.55`

**Issue:**
```python
DEFAULT_HOST = os.getenv("WORKCELL_HOST", "192.168.68.55")
DEFAULT_PORT = int(os.getenv("WORKCELL_PORT", "8080"))
```

The IP is hardcoded as a fallback. While there's an environment variable path, this requires pre-configuration. The default will fail if:
- Workcell IP changes (network reconfiguration)
- Code runs on a different network
- Multiple workcells are needed

**Recommendation:**
- Make the environment variable required (no hardcoded fallback) OR
- Use service discovery / configuration file
- Document required env vars in setup instructions

---

### 2. Brittle MCP Response Parsing

**Severity:** HIGH - Runtime fragility

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/monomer/mcp_client.py:107-131`

**Issue:**
```python
for line in body.split("\n"):
    if line.startswith("data: "):
        payload = json.loads(line[6:])
        result = payload.get("result", {})
        if result.get("isError"):
            error_text = (
                result.get("content", [{}])[0].get("text", "Unknown error")
            )
            raise RuntimeError(f"MCP tool error: {error_text}")

        # Prefer structuredContent, fall back to content[0].text
        sc = result.get("structuredContent", {}).get("result")
        if sc is not None:
            return sc
        content = result.get("content", [])
        if content and content[0].get("text"):
            try:
                return json.loads(content[0]["text"])
            except (json.JSONDecodeError, KeyError):
                return content[0]["text"]
        return result

raise RuntimeError(f"Could not parse MCP response: {body[:500]}")
```

**Problems:**
1. **No SSE parsing library** - Manual line-by-line parsing is fragile to whitespace changes
2. **Silent fallthrough** - If no "data: " line found, raises generic error (last line)
3. **Nested dict access without guards** - `content[0].get(...)` could fail if content structure changes
4. **JSON parse exception silently returns text** - Masks parsing errors
5. **Only shows 500 chars of body** - Truncates debugging information
6. **Assumes at least one data line exists** - No validation

**Recommendation:**
- Use `sseclient-py` or equivalent library
- Add detailed logging at each parse step
- Validate response structure upfront
- Return full body on parse failure (up to size limit)

---

### 3. Missing Workflow Registration State Handling

**Severity:** HIGH - Data loss risk

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/monomer/workflows.py:21-57`

**Issue:**
```python
def register_workflow(
    client: McpClient,
    workflow_path: Path,
    name: str = "Hackathon GD Agent",
) -> int:
    """Register a workflow definition via MCP. Call this ONCE per session."""
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
```

**Problems:**
1. **No idempotency** - Calling twice creates duplicate definitions or overwrites files
2. **Assumes name is unique** - If multiple agents use same name, behavior is undefined
3. **Network partition risk** - If file uploads successfully but DB registration fails, orphaned file left on workcell
4. **No transaction semantics** - Cannot roll back partial failure
5. **Slow lookup** - Queries all definitions to find one by name

**Recommendation:**
- Check if definition already registered before uploading
- Use file hash or UUID to avoid duplicates
- Log file upload + DB registration separately
- Consider returning both file_name and definition_id

---

### 4. Incomplete Well Overlap Validation

**Severity:** MEDIUM-HIGH - Silent data corruption

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/track-2a-closed-loop/examples/workflow_definition_template.py:166-221`

**Issue:**
Comment on line 86-87:
```python
"""IMPORTANT: WELL REUSE
---------------------
This template does NOT check for well conflicts across iterations.
Your agent is responsible for ensuring dest_wells don't overlap with
wells used in previous iterations.
```

**Problems:**
1. **No persistent tracking** - Agent must manually track used wells across restarts
2. **Suggested recovery method is fragile** - Querying OD600 to infer used wells only works if reads succeeded
3. **Silent failures** - If agent reuses wells, data silently overwrites (no error raised)
4. **No plate state query** - No tool to check "which wells are occupied on this plate?"
5. **Column arithmetic is implicit** - `column_index = iteration + 1` is easy to get wrong

**Recommendation:**
- Add validation in `_validate()` to check if dest_wells were already used
- Require agent to pass list of previously-used wells, or query plate metadata
- Consider raising AssertionError if well reuse detected
- Add helper function `next_available_column(plate_barcode)` to MCP client

---

## Major Issues (Medium Priority)

### 5. No Connection Retry Logic

**Severity:** MEDIUM - Transient failures cause complete abort

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/monomer/mcp_client.py:44-79` and throughout

**Issue:**
```python
def connect(self) -> None:
    """Initialize the MCP session."""
    resp = requests.post(...)
    resp.raise_for_status()
    # ...
```

**Problems:**
1. **No retry on transient 5xx errors** - Network hiccup fails entire workflow registration
2. **No backoff strategy** - Retrying immediately may overload struggling server
3. **No timeout configuration** - Uses hardcoded 15/10 second timeouts
4. **Workflow polls have timeouts but no retries** - If poll request fails, workflow is abandoned

**Recommendation:**
- Use `urllib3.util.Retry` + `requests.adapters.HTTPAdapter`
- Implement exponential backoff with jitter
- Make timeouts configurable per operation type
- Add retry logic to workflow polling

---

### 6. Unsafe JSON Parsing in Workflow Definition Template

**Severity:** MEDIUM - Input validation gap

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/track-2a-closed-loop/examples/workflow_definition_template.py:276-279`

**Issue:**
```python
transfers: list[list] = json.loads(transfer_array) if transfer_array else []
dest_well_list: list[str] = json.loads(dest_wells)
monitoring_well_list: list[str] = json.loads(monitoring_wells)
```

**Problems:**
1. **No try/except** - Malformed JSON from agent crashes the workflow definition build
2. **Minimal validation** - Transfer array structure not validated until later
3. **Silent empty case** - `transfer_array` defaults to `[]` if not provided
4. **Type checking deferred** - Assumes parsed lists contain correct types

**Recommendation:**
- Add try/except with descriptive error messages
- Validate transfer array structure in a dedicated helper
- Consider using Pydantic for schema validation

---

### 7. Plate Barcode Coupling

**Severity:** MEDIUM - Brittle to barcode format changes

**Location:**
Multiple files reference plate barcode format: `{PREFIX}-R{ROUND}-{YYYYMMDD}`

**Issue:**
- No validation of barcode format anywhere
- If barcode doesn't exist on workcell, `get_plate_uuid()` only discovered at data fetch time
- Assumes barcode uniqueness (not validated)

**Recommendation:**
- Add `validate_plate_barcode()` helper
- Call on workflow instantiation, not just data fetch
- Document barcode format requirements

---

## Moderate Issues (Lower Priority)

### 8. Incomplete Error Messages

**Severity:** LOW-MEDIUM - Debugging difficulty

**Location:** Throughout

**Examples:**
- `mcp_client.py:131` - Shows only 500 chars of response body
- `mcp_client.py:117` - MCP tool errors only show content[0].text, not full response
- `datasets.py:31, 75, 88-90` - Generic RuntimeError messages without context

**Recommendation:**
- Include request/response full bodies in logs (sanitized)
- Add request IDs to trace failures
- Log at DEBUG level for detailed output

---

### 9. Hardcoded Protocol Constants

**Severity:** LOW-MEDIUM - Inflexible to biology changes

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/track-2a-closed-loop/examples/workflow_definition_template.py:110-118`

**Code:**
```python
_SEED_TRANSFER_UL = 20      # µL of seed culture added to each experimental well
_SEED_MIX_VOL_UL = 100     # µL used to resuspend seed well before seeding
_SEED_MIX_REPS = 5         # pipette mix repetitions on seed well
_NM_CELLS_VOL_UL = 220     # µL of NM+Cells transferred to pre-warm next seed well
_MAX_TRANSFERS = 40         # hard cap on reagent transfer steps per iteration
```

**Problems:**
1. **Not configurable** - Biology may require different seed volumes
2. **_MAX_TRANSFERS is arbitrary** - No comment explaining why 40, not 30 or 50
3. **Not available as parameters** - Can't adjust per-experiment without editing code

**Recommendation:**
- Make these available as workflow definition parameters with defaults
- Document biological/physical constraints that set these values
- Add validation that seed volume + supplements fit in well (180 µL)

---

### 10. Type Hints Are Incomplete

**Severity:** LOW - Reduces IDE support

**Location:**
- `mcp_client.py:81` - `timeout: int = 30` but should be `float`
- `workflows.py:102` - `on_status: callable | None = None` should be `Callable[[str, int], None] | None`
- Multiple `list` instead of `list[SomeType]`

**Recommendation:**
- Add `from typing import Callable` imports
- Use `Callable[[Args], ReturnType]` syntax throughout
- Verify with `mypy --strict`

---

### 11. No Logging Configuration

**Severity:** LOW-MEDIUM - Harder to debug in production

**Location:**
- `basic_agent.py:37-38` uses `logging.basicConfig()`
- No logging in library code (`mcp_client.py`, `datasets.py`, `workflows.py`)

**Problems:**
1. **Library code is silent** - HTTP requests, MCP calls, parsing failures not logged
2. **Agent-only logging** - Can't debug library issues without modifying agent code
3. **basicConfig not idempotent** - Multiple calls don't reconfigure (common mistake)

**Recommendation:**
- Add `logger = logging.getLogger(__name__)` to each module
- Log at DEBUG level: HTTP requests, responses (truncated)
- Log at INFO level: workflow state transitions, plate lookups
- Log at WARNING level: retries, slow operations

---

### 12. Reagent Plate State Not Validated

**Severity:** MEDIUM - Silent failures when reagents depleted

**Location:**
- No check if reagent wells have sufficient volume
- Transfer array assumes reagent wells are pre-loaded and full

**Issue:**
```python
# From CLAUDE.md protocol:
# A1 = Glucose stock
# B1 = NaCl stock
# D1 = Novel Bio (base media)
```

No code validates:
- These wells exist on the reagent plate
- They contain sufficient volume for all transfers
- Reagent types match what routine expects

**Recommendation:**
- Query reagent plate state before instantiating workflow
- Sum all transfers by source well and check against available volumes
- Raise AssertionError if insufficient reagent

---

### 13. No Graceful Handling of Missing OD600 Data

**Severity:** MEDIUM - Silent failures in agent loop

**Location:**
`/Users/carter/monomer-bio-hackathon-march14-15/monomer/datasets.py:74-91`

**Code:**
```python
if not absorbance_datasets:
    raise RuntimeError(f"No OD600 datasets found for plate {plate_barcode}")

# ...

if not column_readings:
    raise RuntimeError(
        f"No OD600 readings found for column {column_index} wells "
        f"on plate {plate_barcode}"
    )

sorted_timestamps = sorted(column_readings.keys())
earliest_well_data = column_readings[sorted_timestamps[0]]  # IndexError if empty!
latest_well_data = column_readings[sorted_timestamps[-1]]
```

**Problems:**
1. **Assumes sorted_timestamps has elements** - If `column_readings` somehow becomes empty after check, IndexError
2. **No partial data handling** - If only some wells have readings, function still fails
3. **No retry logic** - If readings not yet available (experiment still running), agent must handle timeout

**Recommendation:**
- Check `len(sorted_timestamps) >= 2` before accessing indices
- Handle case where some wells have no data (interpolate or skip)
- Add optional `max_retries` parameter for polling incomplete reads

---

## Minor Issues (Informational)

### 14. No Unit Tests

**Severity:** LOW - Acceptable for hackathon, risky for production

**Issue:**
- No test files in repository
- No mock workcell tests
- `apply_constraints()` and `generate_transfer_array()` untested

**Recommendation:**
- Add pytest tests for `transfers.py` (pure functions, easy to test)
- Mock MCP client for `datasets.py`, `workflows.py`
- Use `pytest-vcr` to record HTTP interactions

---

### 15. Unused Imports and Dead Code

**Severity:** LOW - Code cleanliness

**Location:**
- `workflows.py` has `from typing import TYPE_CHECKING` but types only used in docstrings
- No obvious dead code, but `TYPE_CHECKING` pattern is verbose for this codebase

---

### 16. Python 3.11 Requirement

**Severity:** LOW - Reasonable but note for deployment

**Issue:**
`pyproject.toml:9` requires `>=3.11`
- Uses `str | None` syntax (PEP 604, requires 3.10+)
- Uses `from __future__ import annotations` everywhere (future-proofing)

**Concern:**
- Production workcell may run older Python
- Document Python version requirement in deployment docs

---

## Security Concerns

### 17. Credentials in Environment Variables (No Secrets Storage)

**Severity:** MEDIUM - For monitoring MCP

**Issue:**
CLAUDE.md mentions `Authorization: Bearer YOUR_TOKEN` for cloud monitoring:
```json
{
  "Authorization": "Bearer YOUR_TOKEN_HERE"
}
```

**Problems:**
1. Token in plaintext in config file
2. No guidance on secret rotation
3. No authentication for local MCP (no issue on private network, but worth noting)

**Recommendation:**
- Use environment variables for tokens (e.g., `MONOMER_MONITOR_TOKEN`)
- Document: "Never commit tokens to git"
- Add `.env.example` with placeholder

---

### 18. No Input Sanitization in Agent Parameters

**Severity:** LOW - Local network only

**Issue:**
Agent-provided parameters (plate barcode, well names, reagent types) are passed directly to workcell without sanitization.

**Concern:**
- If workcell code is injectable (e.g., Python code generation), malicious input could exploit
- Unlikely on local network, but good practice

**Recommendation:**
- Validate plate barcode format (alphanumeric + hyphen)
- Validate well names (A-H + 1-12)
- Document constraints

---

## Infrastructure & Deployment Concerns

### 19. No Docker/Environment Specs

**Severity:** LOW - Hackathon project, but note for production

**Issue:**
- No Dockerfile
- No `docker-compose.yml`
- Assumes workcell is always at `192.168.68.55:8080`

**Recommendation:**
- Add `.dockerignore` if deploying as service
- Document local vs. remote workcell setup

---

### 20. No Monitoring or Observability

**Severity:** MEDIUM - For long-running experiments

**Issue:**
- No metrics collection (workflow duration, transfer count, etc.)
- No alerts for workflow failures
- No experiment progress dashboard

**Recommendation:**
- Add optional Prometheus metrics export
- Log structured JSON for log aggregation
- Document how to integrate with monitoring systems

---

## Documentation Gaps

### 21. Vague Constraint Descriptions

**Location:**
`CLAUDE.md` documents constraints, but some lack detail:

- "Tip reuse policy: one tip per unique source well" — Unclear if this applies per-iteration or globally
- "Reagent wells must be populated before workflow instantiation" — No API to verify
- "Column arithmetic: column_index = iteration + 1" — What about iterations > 10 (plate full)?

**Recommendation:**
- Add explicit examples: "Iteration 1 uses column 2, Iteration 2 uses column 3, etc."
- Document what happens when plate is full (error? wrapping?)

---

### 22. No Migration Guide for Protocol Changes

**Severity:** LOW - For future iterations

**Issue:**
If biological parameters (seed volume, incubation time, etc.) change, workflow definition must be manually updated.

**Recommendation:**
- Version the workflow definition template
- Document how to update vs. create new definitions

---

## Summary Table

| Issue | Severity | Category | Status |
|-------|----------|----------|--------|
| Hardcoded IP address | HIGH | Config | Requires fix |
| MCP response parsing fragility | HIGH | Reliability | Requires refactor |
| Workflow registration state | HIGH | Data integrity | Requires fix |
| Well overlap validation missing | HIGH | Data corruption | Design fix needed |
| No connection retry logic | MEDIUM | Reliability | Should add |
| Unsafe JSON parsing in template | MEDIUM | Input validation | Should add guards |
| Plate barcode validation | MEDIUM | Robustness | Should add |
| Incomplete error messages | MEDIUM | Debugging | Should improve |
| Hardcoded protocol constants | MEDIUM | Flexibility | Nice to have |
| Type hints incomplete | LOW | Code quality | Nice to have |
| No logging in libraries | MEDIUM | Observability | Should add |
| Reagent state not validated | MEDIUM | Robustness | Should add |
| Missing OD600 error handling | MEDIUM | Reliability | Should improve |
| No unit tests | LOW | Quality | Acceptable for hackathon |
| Credentials in config | MEDIUM | Security | Should document |
| No monitoring/observability | MEDIUM | Operations | Should add |

---

## Quick Wins (Low Effort, High Value)

1. Add `.env.example` with required variables
2. Add basic logging to `mcp_client.py` and `workflows.py`
3. Validate plate barcode format in `basic_agent.py`
4. Add docstring to `_MAX_TRANSFERS` explaining its derivation
5. Use `requests.Session` with retry adapter for connection resilience

---

## Blocking Issues for Production

Before deploying to production (off-network or with multiple agents), address:

1. **Hardcoded IP address** — Use config file or service discovery
2. **Workflow registration idempotency** — Check for duplicates
3. **Well overlap validation** — Prevent data corruption
4. **MCP response parsing robustness** — Use proper SSE library
5. **Connection retry logic** — Handle transient failures gracefully
