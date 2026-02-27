# Monomer Bio Hackathon — Testing Patterns and Strategy

## Current Testing Infrastructure

### Configuration
- **Framework:** pytest (declared in `pyproject.toml` as dev dependency)
- **Version:** `pytest>=7.0`
- **Code quality:** `ruff>=0.4` (linter, pre-commit hook likely configured)
- **Python version:** `requires-python = ">=3.11"`

**From `pyproject.toml`:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.4",
]
```

### Current State
- **No test files present:** The codebase structure has no `tests/` directory
- **No fixtures or mocks:** No `conftest.py` exists
- **All tests to be written:** Testing infrastructure is available but unused

---

## Testable Components

### 1. `monomer.mcp_client.McpClient`
**Type:** Integration (mocked HTTP)
**Responsibility:** JSON-RPC 2.0 communication over HTTP

**Key methods to test:**
- `__init__()` — Client initialization with custom/default URLs
- `connect()` — Session initialization handshake
- `call_tool()` — Tool invocation, JSON parsing, error handling

**Test cases:**
```
test_mcp_client_init_default_url()
test_mcp_client_init_custom_url()
test_mcp_client_connect_success()
test_mcp_client_connect_missing_session_id()
test_mcp_client_call_tool_success()
test_mcp_client_call_tool_structured_content()
test_mcp_client_call_tool_text_content()
test_mcp_client_call_tool_json_decode_error()
test_mcp_client_call_tool_mcp_error()
test_mcp_client_auto_connect_on_first_call()
```

**Mocking strategy:**
- Mock `requests.post()` to return SSE-formatted responses
- Test both `structuredContent` (preferred) and `content[0].text` (fallback) paths
- Verify session ID handling and header construction

---

### 2. `monomer.transfers` — Media Composition
**Type:** Unit tests (pure functions, no I/O)
**Responsibility:** Media composition calculations and transfer array generation

#### 2.1 `compute_novel_bio()`
**Pure function:** Takes supplements dict, returns integer volume

**Test cases:**
```
test_compute_novel_bio_full_novel_bio()          # supplements={}, result=180
test_compute_novel_bio_with_supplements()        # {Glucose: 20, NaCl: 10}, result=150
test_compute_novel_bio_custom_well_volume()      # well_volume=200, result varies
test_compute_novel_bio_three_supplements()       # Glucose+NaCl+MgSO4
```

**Validation:**
- Result is always (well_volume - sum(supplements.values()))
- No negative values

#### 2.2 `apply_constraints()`
**Complex validation logic:** Enforces min/max supplement volumes, ensures Novel_Bio minimum

**Test cases:**
```
test_apply_constraints_clamping()                # vol < min → 0, vol > max → max
test_apply_constraints_novel_bio_minimum()       # Reduces supplements if Novel_Bio < min
test_apply_constraints_all_zeros()               # Empty supplements → all Novel_Bio
test_apply_constraints_boundary_at_min()         # Min supplement value (1)
test_apply_constraints_boundary_at_max()         # Max supplement value (90)
test_apply_constraints_rounding()                # Float inputs rounded to int
test_apply_constraints_sum_equals_well_volume()  # Sum always = well_volume
test_apply_constraints_respects_delta()          # Uses delta to reduce supplements
test_apply_constraints_partial_constraints()     # Only some supplements provided
```

**Edge cases:**
- Supplements sum to > well_volume initially
- One supplement at max (90 µL), others need to be reduced
- Empty input dict
- All zeros input

#### 2.3 `make_perturbed()`
**Single-axis perturbation:** Creates center + delta on one supplement

**Test cases:**
```
test_make_perturbed_glucose_up()                 # center={G:20,...}, delta=+10 → G:30
test_make_perturbed_nacl_up()
test_make_perturbed_mgso4_up()
test_make_perturbed_applies_constraints()        # Result satisfies constraints
test_make_perturbed_no_mutation()                # Original center unchanged (deepcopy)
test_make_perturbed_violates_max()               # G:80 + delta:10 → clamped to 90
```

#### 2.4 `generate_transfer_array()`
**Array generation:** Creates transfer list from composition and column

**Test cases:**
```
test_generate_transfer_array_structure()         # Result is [[src, dst, vol], ...]
test_generate_transfer_array_column_1()          # Column 1 = A1, A2, ..., H1
test_generate_transfer_array_column_2()          # Column 2 = A2, B2, ..., H2
test_generate_transfer_array_control_well()      # Row A always 180 µL Novel_Bio
test_generate_transfer_array_center_point()      # Row B is center composition
test_generate_transfer_array_perturbations()     # Rows C-H are perturbations
test_generate_transfer_array_novel_bio_first()   # Novel_Bio transfers grouped first (tip reuse)
test_generate_transfer_array_source_order()      # Novel_Bio, MgSO4, NaCl, Glucose
test_generate_transfer_array_zero_volumes()      # Omits transfers with 0 µL
test_generate_transfer_array_empty_center()      # center={Glucose:0, NaCl:0, MgSO4:0}
test_generate_transfer_array_custom_delta()      # delta parameter affects perturbations
test_generate_transfer_array_custom_reagent_wells() # Non-default REAGENT_WELLS
```

**Assertions:**
- All dest wells are in format `<Row><Col>`
- All source wells are in REAGENT_WELLS keys
- All volumes > 0 µL
- Sum of volumes for each dest well ≤ well_volume
- Row A always has largest volume (180 µL)

#### 2.5 `compute_tip_consumption()`
**Tip counting:** Calculates pipette requirements from transfer array

**Test cases:**
```
test_compute_tip_consumption_p50_only()         # All volumes ≤ 50 µL
test_compute_tip_consumption_p200_only()        # All volumes 51-200 µL
test_compute_tip_consumption_p1000_only()       # All volumes > 200 µL
test_compute_tip_consumption_mixed()            # All three pipette types
test_compute_tip_consumption_reuse_tips()       # Novel_Bio well: 1 tip, multiple transfers
test_compute_tip_consumption_single_tips()      # Other sources: 1 tip per transfer
test_compute_tip_consumption_empty_array()      # transfers=[]
test_compute_tip_consumption_custom_reuse_wells() # Override REUSE_TIP_SOURCE_WELLS
```

**Validation:**
- p50 tip count ≥ 0, p200 ≥ 0, p1000 ≥ 0
- Reuse wells contribute 1 tip per source well per pipette type
- Single-use wells contribute 1 tip per transfer

---

### 3. `monomer.datasets` — OD600 Result Fetching
**Type:** Integration (mocked HTTP, MCP client mock)
**Responsibility:** Query REST API, parse OD600 readings

#### 3.1 `get_plate_uuid()`
**Lookup function:** Finds plate UUID by barcode

**Test cases:**
```
test_get_plate_uuid_found()                      # Plate exists, UUID returned
test_get_plate_uuid_not_found()                  # RuntimeError raised
test_get_plate_uuid_multiple_plates()            # Returns first match
test_get_plate_uuid_empty_response()             # plates=[]
```

**Mocking:**
- Mock `client.call_tool("list_culture_plates", {})`

#### 3.2 `fetch_absorbance_results()`
**REST API query:** Fetches OD600 readings from dataset API

**Test cases:**
```
test_fetch_absorbance_results_baseline_endpoint() # Returns {baseline: {...}, endpoint: {...}}
test_fetch_absorbance_results_column_filtering()  # Filters to target column only
test_fetch_absorbance_results_multiple_datasets() # Picks earliest and latest
test_fetch_absorbance_results_no_data()          # RuntimeError if no OD600 datasets
test_fetch_absorbance_results_partial_wells()    # Some wells missing data
test_fetch_absorbance_results_single_timepoint()  # baseline = endpoint if only 1 reading
test_fetch_absorbance_results_custom_column()    # column_index parameter
test_fetch_absorbance_results_custom_rows()      # ROWS parameter
```

**Mocking:**
- Mock `client.call_tool("list_culture_plates", {})` → returns plates with UUID
- Mock `requests.get()` to return dataset API response
- Test metadata filtering (wavelength=600, plate UUID match)

**Response structure validation:**
- `resultMetadata.measurementWavelength` = 600
- `plateMetadata.uuid` matches plate UUID
- `structuredData.resultsByWell` has target column wells

#### 3.3 `parse_od_results()`
**Parsing:** Converts baseline+endpoint readings to delta OD

**Test cases:**
```
test_parse_od_results_delta_calculation()        # endpoint - baseline for each well
test_parse_od_results_control_well()             # Row A (control)
test_parse_od_results_center_well()              # Row B (center)
test_parse_od_results_perturbations()            # Rows C-H (2 reps × 3 supplements)
test_parse_od_results_missing_baseline()         # Handles missing wells gracefully (0.0)
test_parse_od_results_zero_growth()              # endpoint = baseline → delta = 0
test_parse_od_results_absolute_values()          # abs_control_od, abs_center_od
test_parse_od_results_custom_column()            # column_index parameter
test_parse_od_results_structure()                # Output has all required keys
```

**Assertions:**
- `control_od`, `center_od` are floats
- `perturbed_ods` dict has keys for each supplement
- Each supplement value is [rep1_delta, rep2_delta]
- All delta values are non-negative (optional constraint)

---

### 4. `monomer.workflows` — Workflow Management
**Type:** Integration (mocked MCP client)
**Responsibility:** Register, instantiate, poll workflows

#### 4.1 `register_workflow()`
**Workflow upload and registration:** Uploads definition file, creates named record

**Test cases:**
```
test_register_workflow_file_upload()             # Calls create_workflow_definition_file
test_register_workflow_db_registration()         # Calls register_workflow_definition
test_register_workflow_definition_lookup()       # Calls list_workflow_definitions and finds match
test_register_workflow_not_found()               # RuntimeError if definition name not found after registration
test_register_workflow_custom_name()             # Custom workflow name parameter
test_register_workflow_returns_definition_id()   # Result is int ID
```

**Mocking:**
- Mock `client.call_tool()` for all three calls
- Simulate sequential call chain (upload → register → lookup)

#### 4.2 `instantiate_workflow()`
**Workflow instantiation:** Creates instance with given inputs

**Test cases:**
```
test_instantiate_workflow_merges_inputs()        # plate_barcode + extra_inputs merged
test_instantiate_workflow_no_extra_inputs()      # extra_inputs=None
test_instantiate_workflow_returns_uuid()         # Result is string UUID
test_instantiate_workflow_uuid_not_found()       # RuntimeError if uuid missing from response
test_instantiate_workflow_with_reason()          # reason parameter passed to MCP
test_instantiate_workflow_inputs_structure()     # Calls instantiate_workflow with correct dict
```

**Mocking:**
- Mock `client.call_tool("instantiate_workflow", {...})`
- Return dict with `uuid` key

#### 4.3 `poll_workflow_completion()`
**Polling loop:** Waits for workflow to complete

**Test cases:**
```
test_poll_workflow_completed()                   # Immediate return if status="completed"
test_poll_workflow_failed()                      # Returns on status="failed"
test_poll_workflow_cancelled()                   # Returns on status="cancelled"
test_poll_workflow_timeout()                     # TimeoutError after max_time
test_poll_workflow_polling_interval()            # Uses poll_interval parameter
test_poll_workflow_on_status_callback()          # Calls on_status(status, elapsed) each poll
test_poll_workflow_status_progression()          # Polls multiple times before completion
test_poll_workflow_returns_instance_data()       # Returns full instance dict
```

**Mocking:**
- Mock `client.call_tool("get_workflow_instance_details", {...})`
- Return status=pending initially, then status=completed
- Mock `time.time()` and `time.sleep()` for timeout/interval tests

---

### 5. `track-2a-closed-loop.examples.basic_agent` — Integration Test
**Type:** End-to-end test (all mocks, local execution)
**Responsibility:** Full agent loop for one iteration

**Test cases:**
```
test_basic_agent_one_iteration()                 # Single iteration completes
test_basic_agent_registers_workflow()            # Workflow definition registered
test_basic_agent_generates_transfers()           # Transfer array generated
test_basic_agent_instantiates_workflow()         # Workflow instantiated with correct inputs
test_basic_agent_polls_completion()              # Waits for workflow completion
test_basic_agent_fetches_results()               # OD600 results fetched
test_basic_agent_computes_gradient()             # Gradient computation correct
test_basic_agent_updates_center()                # Center composition updated
test_basic_agent_applies_constraints()           # Updated center satisfies constraints
test_basic_agent_multi_iteration()               # 3+ iterations run sequentially
test_basic_agent_plate_full()                    # Stops when column_index > 12
test_basic_agent_saves_history()                 # History JSON written
```

**Mocking:**
- Mock all MCP client calls
- Mock `requests.get()` for datasets REST API
- Return realistic OD600 readings (baseline, growth signal)

---

## Mocking Strategy

### MCP Client Mock
```python
# In conftest.py or test fixtures

@pytest.fixture
def mock_mcp_client(monkeypatch):
    """Mock McpClient to return controlled responses."""
    def mock_call_tool(tool_name, arguments):
        if tool_name == "list_culture_plates":
            return [
                {"barcode": "GD-R1-20260314", "uuid": "plate-uuid-123"},
            ]
        elif tool_name == "list_workflow_definitions":
            return [
                {"id": 1, "name": "Hackathon GD Agent"},
            ]
        # ... more tool responses

    client = MagicMock()
    client.call_tool = mock_call_tool
    client.base_url = "http://192.168.68.55:8080"
    return client
```

### HTTP Mocking (requests)
```python
@pytest.fixture
def mock_requests_get(monkeypatch):
    """Mock requests.get for REST API calls."""
    def mock_get(url, **kwargs):
        response = MagicMock()
        response.json.return_value = {
            "results": [
                {
                    "metadata": {
                        "resultMetadata": {"measurementWavelength": 600},
                        "plateMetadata": {"uuid": "plate-uuid-123"},
                    },
                    "structuredData": {
                        "resultsByWell": {
                            "2025-01-01T10:00:00Z": {
                                "A2": 0.05, "B2": 0.05, ...
                            },
                            "2025-01-01T11:00:00Z": {
                                "A2": 1.2, "B2": 0.9, ...
                            },
                        }
                    }
                }
            ]
        }
        return response

    monkeypatch.setattr("requests.get", mock_get)
```

### Time Mocking (for polling tests)
```python
@pytest.fixture
def mock_time(monkeypatch):
    """Mock time.time() and time.sleep()."""
    times = [0, 30, 60, 90]  # Elapsed times on each call
    time_iter = iter(times)

    def mock_time_func():
        return next(time_iter)

    monkeypatch.setattr("time.time", mock_time_func)
    monkeypatch.setattr("time.sleep", lambda x: None)
```

---

## Test Organization

### File Structure
```
tests/
  __init__.py
  conftest.py                  # Shared fixtures

  unit/
    test_transfers.py          # All transfers.py tests
    test_datasets_parsing.py    # parse_od_results, etc.

  integration/
    test_mcp_client.py         # MCP client with mocked HTTP
    test_workflows.py          # Workflow management
    test_datasets_api.py       # REST API integration

  e2e/
    test_basic_agent.py        # Full closed-loop agent
```

### Parametrization Pattern
```python
@pytest.mark.parametrize("column_index,expected_wells", [
    (1, ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1"]),
    (2, ["A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2"]),
    (12, ["A12", "B12", "C12", "D12", "E12", "F12", "G12", "H12"]),
])
def test_generate_transfer_array_column_index(column_index, expected_wells):
    """Test transfer array generation for different columns."""
    ...
```

---

## Coverage Goals

| Module | Target | Focus |
|--------|--------|-------|
| `transfers.py` | 95% | All composition constraints, boundary conditions |
| `datasets.py` | 90% | API parsing, error cases |
| `mcp_client.py` | 85% | Connection, error handling, JSON parsing |
| `workflows.py` | 85% | Registration, instantiation, polling |
| `basic_agent.py` | 80% | Full iteration loop, gradient computation |

**Exclusions from coverage:**
- `__main__` blocks (CLI entry points)
- Logging statements
- Error paths that raise exceptions (sufficient to test they raise)

---

## Testing Best Practices for This Codebase

### 1. Test Pure Functions First
Start with `transfers.py` unit tests — no dependencies, fast, isolated.

### 2. Mock External I/O
- MCP client calls → mock `client.call_tool()`
- REST API calls → mock `requests.get()`
- Time-based polling → mock `time.time()` and `time.sleep()`

### 3. Test Error Cases Explicitly
```python
def test_apply_constraints_novel_bio_too_low():
    """Supplements so high Novel_Bio would be < min — must reduce."""
    result = apply_constraints({
        "Glucose": 70,
        "NaCl": 70,
        "MgSO4": 70,
    }, min_novel_bio=90)
    assert result["Novel_Bio"] >= 90
```

### 4. Use Fixtures for Complex Setup
```python
@pytest.fixture
def sample_transfers():
    """Standard transfer array for testing."""
    return [
        ["D1", "A2", 180],
        ["D1", "B2", 150],
        ["A1", "B2", 20],
        # ...
    ]
```

### 5. Test Boundary Conditions
- Min/max values (supplement 1 µL, 90 µL)
- Empty inputs
- Single-element lists
- Column boundaries (col 1 vs col 12)

### 6. Validate Data Structure Invariants
```python
def test_generate_transfer_array_invariants():
    """Verify all transfer array invariants."""
    transfers = generate_transfer_array(center, column_index=2)

    for src, dst, vol in transfers:
        assert vol > 0, "All volumes must be positive"
        assert re.match(r"[A-Z]\d+", dst), f"Invalid dest well: {dst}"

    # Sum volumes per well doesn't exceed well volume
    # (Note: Some wells will have multiple transfers from different sources)
```

---

## Pre-Commit Testing

**Recommended pre-commit hook configuration:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/
        language: system
        types: [python]
        pass_filenames: false
        always_run: true

      - id: ruff
        name: ruff lint
        entry: ruff check
        language: system
        types: [python]
```

---

## Future Test Enhancements

1. **Property-based testing:** Use Hypothesis to generate random compositions and verify constraints
2. **Performance testing:** Benchmark transfer array generation with large arrays
3. **Fixture library:** Build realistic OD600 readings and workflow response fixtures
4. **Snapshot testing:** Capture transfer arrays and parsing results as snapshots
5. **Coverage enforcement:** Fail CI if coverage drops below threshold

