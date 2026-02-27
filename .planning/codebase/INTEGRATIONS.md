# External Integrations — Monomer Bio Hackathon

## Overview

This document catalogs all external APIs, services, and integration points for the Monomer Bio Q1 2026 AI Scientist Hackathon codebase. All integrations use standard HTTP protocols (JSON-RPC 2.0 and REST).

---

## Workcell Control — Autoplat MCP (Local)

### Overview
Primary integration point for autonomous agent development. Provides complete workflow orchestration, routine management, and plate tracking for closed-loop experiments.

### Connection Details
| Property | Value |
|----------|-------|
| **Protocol** | JSON-RPC 2.0 over HTTP POST |
| **Endpoint** | `http://192.168.68.55:8080/mcp` |
| **Authentication** | None (local network, no external access) |
| **Session Model** | Stateful (session ID in response headers) |
| **Transport** | Server-Sent Events (SSE) for responses |
| **Timeout** | 30 seconds per tool call (configurable) |

### Authentication & Setup

**Initialization (Must be called once per session):**
```
POST /mcp
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "monomer-python", "version": "0.1"}
  }
}
```

**Response:**
- Header: `mcp-session-id: <uuid>` (save this for subsequent calls)
- Returns initialized capability list

**Initialization Notification (Required after initialize):**
```
POST /mcp
Headers: Mcp-Session-Id: <session_id>
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

### Tool Categories

#### Workflow Management (Define & Register)

| Tool | Purpose | Parameters | Usage |
|------|---------|-----------|-------|
| `list_workflow_definitions` | Enumerate all registered workflow definitions | None | Discover available workflows |
| `get_workflow_definition` | Get metadata + validation status | `definition_id: int` | Inspect before instantiation |
| `get_workflow_definition_schedule` | List scheduled nodes with relative execution times | `definition_id: int` | Understand workflow timing |
| `get_workflow_definition_dag` | Get DAG structure (nodes, edges, dependencies) | `definition_id: int` | Visualize workflow logic |
| `list_workflow_definition_files` | Enumerate `.py` files on disk | None | Discover unregistered definitions |
| `create_workflow_definition_file` | Upload a `.py` file to workcell | `file_name: str`, `code_content: str` | First step of registration |
| `validate_workflow_definition_file` | Syntax check + routine validation | `file_name: str`, `inputs: dict?` | Pre-register validation |
| `register_workflow_definition` | Create named database record | `name: str`, `file_name: str` | Complete registration |
| `get_workflow_dsl_schemas` | Simplified schemas for DSL classes | None | Understand definition structure |

#### Workflow Instances (Launch & Monitor)

| Tool | Purpose | Parameters | Usage |
|------|---------|-----------|-------|
| `instantiate_workflow` | Create a new instance (pending operator approval) | `definition_id: int`, `inputs: dict`, `reason: str`, `start_after_minutes: int?` | Launch an experiment iteration |
| `list_workflow_instances` | Enumerate all instances (past, present, pending) | `limit: int?` | Monitor experiment history |
| `get_workflow_instance_details` | Poll instance status + metadata | `instance_uuid: str` | Check completion, errors |
| `list_workflow_routines` | Get scheduled steps for an instance | `instance_uuid: str` | Understand instance execution plan |
| `list_pending_workflows` | Workflows awaiting operator approval | `limit: int?` | Check approval queue |
| `check_workflow_cancellable` | Verify safe to cancel (requires user confirmation) | `instance_uuid: str` | Pre-cancel validation |
| `cancel_workflow_instance` | Cancel a pending/running instance | `instance_uuid: str`, `user_confirmed: bool` | Abort experiment (requires explicit confirmation) |

#### Routine Management (Atomic Actions)

| Tool | Purpose | Parameters | Usage |
|------|---------|-----------|-------|
| `list_available_routines` | All available routines (name, type, signature) | None | Discover executable actions |
| `get_routine_details` | Full routine template + parameter spec | `routine_name: str` | Understand parameter requirements |
| `list_future_routines` | Upcoming scheduled routines | `limit: int?`, `is_queued: bool?`, `scheduled_after: str?`, `scheduled_before: str?` | Monitor near-term work |
| `get_future_routine_details` | Complete future routine + parameters | `uuid: str` | Inspect upcoming action |
| `get_workflow_routine_with_children` | WorkflowRoutine + child FutureRoutines | `uuid: str` | Understand routine–instance hierarchy |
| `trace_future_routine_to_workflow` | Lineage: FutureRoutine → Workflow context | `uuid: str` | Determine if routine is workflow-generated |

#### Plate Management (Physical Assets)

| Tool | Purpose | Parameters | Usage |
|------|---------|-----------|-------|
| `list_culture_plates` | All culture plates on workcell | `limit: int?` | Discover available plates |
| `check_plate_availability` | Verify plate exists, checked-in, not in another workflow | `plate_barcode: str` | Pre-instantiation validation |
| `unlink_culture_plate_from_workflow` | Remove plate from workflow assignment | `plate_barcode: str`, `cancel_workflow: bool?` | Free plate for reuse |
| `list_reagent_plates` | Reagent plates + media types + capacity | `is_checked_in: bool?`, `include_reagents: bool?` | Discover stock plates, media availability |
| `set_reagents_by_well` | Update reagent metadata for a plate | `plate_barcode: str`, `reagents_by_well: dict` | Track reagent state |

#### Track 2A Specific Routines

**Available Routines (Read-Only):**
- **GD Iteration Combined** — Liquid handling (transfers) + seed operations + pre-warm
- **AI Scientist Compound Plate Generation** — Stock plate → compound plate transfers
- **Measure Absorbance** — OD600 platereader (wavelength 600nm)

### Request/Response Format

**Tool Call:**
```json
{
  "jsonrpc": "2.0",
  "id": <auto_increment>,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": { ... }
  }
}
```

**Response (SSE):**
```
event: message
data: {
  "result": {
    "isError": false,
    "structuredContent": {"result": {...}} | null,
    "content": [{"type": "text", "text": "..."}]
  }
}
```

**Error Format:**
```json
{
  "result": {
    "isError": true,
    "content": [{"type": "text", "text": "Error message"}]
  }
}
```

### Common Workflows

#### 1. Register a Workflow Definition
```
1. create_workflow_definition_file(file_name, code_content)
2. validate_workflow_definition_file(file_name, inputs?)
3. register_workflow_definition(name, file_name)
4. list_workflow_definitions() → find by name, extract ID
```

#### 2. Instantiate & Monitor
```
1. check_plate_availability(plate_barcode)
2. instantiate_workflow(definition_id, inputs, reason) → UUID
3. poll: get_workflow_instance_details(uuid) until status in ["completed", "failed", "cancelled"]
```

#### 3. Cancel (with safety check)
```
1. check_workflow_cancellable(uuid) → must be true
2. [REQUIRE USER CONFIRMATION]
3. cancel_workflow_instance(uuid, user_confirmed=true)
```

### Workcell Constraints
- Max 1 concurrent workflow (sequential)
- Max ~40 transfers per iteration
- Tip reuse policy: Only Novel_Bio well (D1) reuses tips; all others use fresh tips
- Incubation: 37°C
- Platereader: minimum 5 min interval, default 10 min (9 reads = 90 min window)

---

## Workcell Observation — Monitor MCP (Cloud, Read-Only)

### Overview
Optional integration for read-only monitoring and culture status tracking. Complementary to local Autoplat MCP (control).

### Connection Details
| Property | Value |
|----------|-------|
| **Endpoint** | `https://backend-staging.monomerbio.com/mcp` |
| **Authentication** | Bearer token (obtained from cloud-staging.monomerbio.com) |
| **Protocol** | JSON-RPC 2.0 (same as Autoplat) |
| **Access** | Read-only (no tool modifications) |
| **Environment** | Staging (not production) |

### Authentication
```
Authorization: Bearer YOUR_TOKEN_HERE
```

**Token Acquisition:**
1. Log in to `https://cloud-staging.monomerbio.com`
2. Navigate to Profile → API Token
3. Copy token, store securely

### Tools (All Read-Only)

| Tool | Purpose | Parameters | Returns |
|------|---------|-----------|---------|
| `list_cultures` | All tracked culture plates | `limit: int?`, `plate_id: str?` | List of cultures with status, latest readings |
| `get_culture_details` | Plate metadata + observation history | `culture_id: str` | Plate info, timestamp-indexed OD600 readings |
| `list_culture_statuses` | Available culture status values | `include_archived: bool?` | System + custom status options |
| `update_culture_status` | Mark wells as contaminated, dead, etc. | `culture_id: str`, `status_id: str`, `wells: list[str]` | Audit trail with user + timestamp |
| `list_plates` | All plates with observation summaries | `limit: int?` | Plate list with aggregate readout stats |
| `get_plate_observations` | Time-series OD600 for a plate | `plate_id: str`, `limit: int?` | All readings grouped by well |
| `export_plate_observations` | CSV export of observations | `plate_id: str`, `limit: int?` | CSV string (matrix: timestamps × wells) |

### Common Workflows

#### Monitor Plate Over Time
```
1. list_plates() → find by barcode
2. get_plate_observations(plate_id) → all readings
3. export_plate_observations(plate_id) → for analysis
```

#### Update Culture Status (Mark contamination, etc.)
```
1. list_culture_statuses() → find "Contaminated" status ID
2. update_culture_status(culture_id, status_id, wells=["A2", "B2"])
3. Creates audit entry with timestamp + user
```

---

## Workcell REST API (Implicit via datasets.py)

### Overview
Used by `monomer/datasets.py` for fetching OD600 measurement results. Separate from MCP (not through MCP protocol).

### Connection Details
| Property | Value |
|----------|-------|
| **Base URL** | `http://192.168.68.55:8080` (same workcell) |
| **Endpoint** | `/api/datasets/` |
| **Protocol** | REST (GET) |
| **Authentication** | Required custom header |
| **Response** | JSON (camelCase) |

### Required Headers
```
Content-Type: application/json
X-Monomer-Client: desktop-frontend
```

**Header Purpose:** ClientIdentifierMiddleware on backend (identifies client type for routing)

### Dataset Query

**Request:**
```
GET /api/datasets/?verbose=1&ordering=-createdAt
```

**Query Parameters:**
| Param | Value | Purpose |
|-------|-------|---------|
| `verbose` | `1` | Include full metadata + structured data |
| `ordering` | `-createdAt` | Newest first |

**Response Format:**
```json
{
  "results": [
    {
      "id": "...",
      "createdAt": "2025-02-27T...",
      "metadata": {
        "resultMetadata": {
          "measurementWavelength": 600
        },
        "plateMetadata": {
          "uuid": "<plate_uuid>"
        }
      },
      "structuredData": {
        "resultsByWell": {
          "<timestamp>": {
            "<well>": <od600_value>,
            ...
          },
          ...
        }
      }
    },
    ...
  ]
}
```

**Data Model:**
- Timestamps (ISO8601) as keys in `resultsByWell`
- Well addresses (A1–H12) as keys
- OD600 values as floats
- Multiple datasets per plate (one per reading cycle)

### Usage (via monomer/datasets.py)

```python
from monomer.datasets import fetch_absorbance_results, parse_od_results

# Get baseline + endpoint OD600 for column 2, row A-H
raw = fetch_absorbance_results(client, plate_barcode="GD-R1-20260314", column_index=2)
# Returns:
# {
#   "baseline": {"A2": 0.05, "B2": 0.08, ...},
#   "endpoint": {"A2": 1.2, "B2": 1.3, ...}
# }

# Parse into delta OD for optimization
parsed = parse_od_results(raw, column_index=2)
# Returns:
# {
#   "control_od": 1.15,    # delta A2
#   "center_od": 1.22,     # delta B2
#   "perturbed_ods": {
#     "Glucose": [1.3, 1.2],
#     "NaCl": [0.9, 0.95],
#     "MgSO4": [1.1, 1.05]
#   }
# }
```

---

## Databases & Persistence

### On-Workcell Database
- **System:** Unknown (likely SQLite or PostgreSQL on workcell)
- **Schema:** Workflow definitions, instances, routines, plate registry, consumables tracking
- **Access:** Via MCP tools only (no direct SQL access)
- **Persistence:** Survives workcell restarts

### Cloud Database (Monitor MCP)
- **System:** Unknown (staging environment)
- **Data:** Culture plates, observations (time-series OD600), culture statuses
- **Access:** Read-only via Monitor MCP
- **Replication:** From workcell to cloud (async)

### No Direct Database Access
- No environment variables with connection strings
- No database client imports (requests + JSON-RPC only)
- All data flows through HTTP APIs

---

## File System Integration

### Workcell Filesystem
- **Accessed via MCP:** `create_workflow_definition_file()`, `list_workflow_definition_files()`
- **Directory:** Workcell-specific subdirectory (e.g., `workcell/workflow_definitions/{workcell_name}/`)
- **File format:** Python `.py` files with `build_definition()` function
- **No local direct access:** Upload/validate via MCP only

### Local Development Filesystem
- **No remote file sync:** Files are uploaded, not mirrored
- **Example templates:** Included in `track-2a-closed-loop/examples/`
- **Artifacts:** `runs/history.json` generated by agent (local storage)

---

## External Dependencies (Network)

### HTTP Dependencies
| Library | Version | Purpose | Targets |
|---------|---------|---------|---------|
| `requests` | ≥2.28 | HTTP client | Workcell MCP + REST + Cloud Monitor |
| `python-dotenv` | ≥1.0 | .env loading | Local config (not external API) |

### No External APIs
- No third-party cloud services (AWS, GCP, Azure, etc.)
- No public APIs (PubChem, KEGG, etc. for research)
- No AI/LLM APIs (Claude, ChatGPT, etc. — agent runs locally)
- No data warehouse (BigQuery, Snowflake, etc.)

---

## Authentication & Secrets Management

### Workcell Authentication
- **Local Autoplat MCP:** No authentication (local network only)
- **Workcell REST API:** Custom header `X-Monomer-Client` (not a secret)
- **Credentials:** No API keys or bearer tokens needed for local workcell

### Cloud Authentication
- **Monitor MCP:** Bearer token
- **Token Source:** Manual login to cloud-staging.monomerbio.com
- **Storage:** Must be passed at runtime (not in codebase)
- **Security Note:** Do NOT commit token to version control

### Environment Variables
| Variable | Default | Usage |
|----------|---------|-------|
| `WORKCELL_HOST` | `192.168.68.55` | Workcell IP address |
| `WORKCELL_PORT` | `8080` | Workcell port |
| (No token env var) | — | Pass as `Authorization` header at runtime |

**Recommended Pattern:**
```python
import os
from monomer.mcp_client import McpClient

client = McpClient("http://192.168.68.55:8080")  # uses env vars if needed

# For Monitor MCP:
token = os.getenv("MONOMER_TOKEN")  # set externally
# Pass token in MCP connection
```

---

## Event & Webhook System

### No Webhooks
- No push notifications or event subscriptions
- All monitoring is **pull-based** (agent polls for status)
- Polling interval: 30 seconds (default in `workflows.py`)

### Status Polling Loop
```python
while status not in ("completed", "failed", "cancelled"):
    instance = client.call_tool("get_workflow_instance_details", {"instance_uuid": uuid})
    status = instance.get("status")
    time.sleep(30)  # DAEMON_POLL_INTERVAL
```

---

## Rate Limiting & Quotas

### Known Constraints
- **Workflow concurrency:** Max 1 active workflow (sequential)
- **Transfer limit:** ~40 transfers per iteration (enforced by validation)
- **Platereader interval:** Minimum 5 minutes (typically 10 min)
- **API timeout:** 30 seconds per tool call

### No Explicit Rate Limits
- No per-second request throttling documented
- No request quota per user/session
- Local network (no public rate limits)

---

## Integration Checklist for Developers

### Before First Run
- [ ] Workcell is on local network (192.168.68.55:8080 reachable)
- [ ] Monomer team has loaded your stock plate + registered `reagent_type` tag
- [ ] Python 3.11+ installed locally
- [ ] Dependencies: `pip install -e .`

### For Closed-Loop Agent
- [ ] Write `build_definition()` workflow template
- [ ] Register template once: `register_workflow(client, Path("..."), name="...")`
- [ ] For each iteration:
  1. Generate transfer array (2–40 transfers)
  2. Instantiate workflow with iteration inputs
  3. Poll for completion (typically 60–90 min)
  4. Fetch OD600 results via datasets API
  5. Compute gradient, update center point, repeat

### For Monitoring (Optional)
- [ ] Obtain cloud-staging token
- [ ] Configure Monitor MCP in code
- [ ] Use `list_cultures()`, `get_plate_observations()` for post-hoc analysis

### Safety
- [ ] Always call `check_workflow_cancellable()` before `cancel_workflow_instance()`
- [ ] Require explicit user confirmation for cancellation
- [ ] Check plate availability before instantiation
- [ ] Validate workflow definition before registration

---

## Troubleshooting Integration Issues

### MCP Connection Fails
- **Check:** Workcell IP reachable (ping 192.168.68.55)
- **Check:** Port 8080 open (telnet 192.168.68.55 8080)
- **Check:** Session ID captured in response headers after initialize

### Tool Call Timeout
- **Check:** Workcell processing (may be running a routine)
- **Check:** Network latency (MCP default 30s; increase if needed)
- **Check:** Tool argument validation (missing required params?)

### Dataset Query Returns No Results
- **Check:** Plate barcode matches exactly (case-sensitive)
- **Check:** Column index is correct (iteration N → column N+1)
- **Check:** OD600 measurement has completed (workflow still running?)

### Cloud Monitor Token Invalid
- **Check:** Token is fresh (re-login to cloud-staging.monomerbio.com)
- **Check:** Bearer token format: `Bearer YOUR_TOKEN` (not bare token)

---

## Summary Table

| Integration | Type | Authentication | Access | Location |
|-------------|------|---|--------|----------|
| **Autoplat MCP** | JSON-RPC 2.0 | None (local) | Full (CRUD) | `http://192.168.68.55:8080/mcp` |
| **Monitor MCP** | JSON-RPC 2.0 | Bearer token | Read-only | `https://backend-staging.monomerbio.com/mcp` |
| **Workcell REST API** | REST (GET) | Custom header | Read-only | `http://192.168.68.55:8080/api/datasets/` |
| **Workcell Database** | (unknown) | MCP tools | Indirect | On-workcell |
| **Cloud Database** | (unknown) | Monitor MCP | Indirect | Cloud staging |
| **File System** | MCP tools | None (local) | Upload/validate | Workcell disk |
| **HTTP Client** | Python `requests` | Library | — | Network |
