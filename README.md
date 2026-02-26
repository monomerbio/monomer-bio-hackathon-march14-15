# Monomer Bio AI Scientist Hackathon — March 14–15, 2026

**Venue:** 1338 Mission St, San Francisco
**Theme:** Build scientific agents to run closed-loop automation on real biology
**Cell line:** *Vibrio natriegens* (fastest-growing BSL-1 organism, ~20 min doubling time)
**Scoring:** Maximize total biomass = **Σ (wells × OD600 absorbance)**

---

## What You're Building

You'll design experiments to find the optimal growth media for *V. natriegens*, then automate those experiments on a real robotic workcell. The workcell reads OD600 absorbance every 10 minutes — your AI agent can observe results and decide what to run next, closing the loop in real time.

## Tracks

| Track | Focus | Lead |
|-------|-------|------|
| [Track 1: Research](./track-1-research/) | Use Elnora AI to research protocols and design your experiment | Carmen Kivisild (Elnora) |
| [Track 2A: Closed Loop](./track-2a-closed-loop/) | Build an autonomous agent using Monomer MCP to iterate media optimization | Carter Allen (Monomer) |
| [Track 2B: Protocol Dev](./track-2b-protocol-dev/) | Use AI coding tools to write protocols for Hamilton STARlet + Cephla microscope | Rick Wierenga (Retro Bio) |
| [Track 2C: Physical AI](./track-2c-physical-ai/) | Program a UR10e arm to automate flask-based cell culture | TBD |

**Track 1 is mandatory** — all participants start here to design their experiment, then continue in a Track 2.

---

## Quick Start

### 1. Connect to the Platform

The staging environment is at `cloud-staging.monomerbio.com`. Get credentials from a Monomer team member.

For AI tools (Cursor, Claude Code, etc.): see [Track 2A Setup](./track-2a-closed-loop/README.md#mcp-setup) to install the MCP server.

### 2. Install This Library

```bash
pip install -e .
```

### 3. Set Your Workcell Connection

```bash
export WORKCELL_HOST=192.168.68.55
export WORKCELL_PORT=8080
```

Or use the defaults if on the local network.

### 4. Try a Quick Check

```python
from monomer.mcp_client import McpClient

client = McpClient()
plates = client.call_tool("list_culture_plates", {})
print(plates)
```

---

## Repository Structure

```
monomer/                  # Python client library
  mcp_client.py           # MCP HTTP client (JSON-RPC over HTTP)
  workflows.py            # Register, instantiate, and poll workflows
  datasets.py             # Fetch OD600 absorbance results
  transfers.py            # Transfer array generation (media composition)

track-1-research/         # Biology context, research questions, Elnora guide
track-2a-closed-loop/     # Monomer MCP agent examples and workflow reference
track-2b-protocol-dev/    # Hamilton STARlet + Cephla microscope protocols
track-2c-physical-ai/     # UR10e robotic arm automation
```

---

## Scoring

Growth is measured as OD600 absorbance in each well of a 96-well plate. Final score:

```
score = number_of_wells_with_growth × mean_OD600_across_those_wells
```

A well "has growth" if OD600 > baseline (pre-seeding read). The team with the highest score wins.

---

## Hardware on the Workcell

| Instrument | Role |
|-----------|------|
| Opentrons Flex | Liquid handling (P1000 single-channel, P1000 8-Channel, Gripper) |
| Tecan Infinite | Plate reader |
| Liconic STX-220 (37°C) | Incubation |
| Liconic STX-110 (4°C) | Reagent storage |
| Liconic LPX-220 | Room Temperature Storage |
| PAA KX-2 | Robotic arm (plate transport) |

---

## Key Contacts

- **Carter Allen** — carter@monomerbio.com (Track 2A, overall)
- **Carmen Kivisild** — carmen.kivisild@elnora.ai (Track 1, Elnora)
- **Rick Wierenga** — rick@retro.bio (Track 2B)
