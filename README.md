# Monomer Bio Hackathon — Software Setup

This repo is the software companion for Track 2 of the March 14–15 AI Scientist Hackathon. For logistics, format, scoring, and the full track overview, see the [Notion setup page](https://www.notion.so/Q1-2026-AI-Scientist-Hackathon-Setup-2ff8d59ea9ff81d5acbbeb45f38a743b).

---

## Tracks

| Track | Directory | Status |
|-------|-----------|--------|
| Track 1: Research (Elnora) | — | See Notion for Elnora setup |
| Track 2A: Closed Loop (Monomer MCP) | [`track-2a-closed-loop/`](./track-2a-closed-loop/) | Ready — start here |
| Track 2B: Protocol Dev (Hamilton + Cephla) | [`track-2b-protocol-dev/`](./track-2b-protocol-dev/) | Setup TBD |
| Track 2C: Physical AI (UR10e) | [`track-2c-physical-ai/`](./track-2c-physical-ai/) | Setup TBD |

---

## Track 2A: Monomer MCP Setup

Install the Python client library:

```bash
pip install -e .
```

Then follow the [Track 2A README](./track-2a-closed-loop/README.md) for MCP connection, workflow registration, and agent examples.

---

## Repository Structure

```
monomer/                  # Python client library
  mcp_client.py           # MCP HTTP client (JSON-RPC over HTTP)
  workflows.py            # Register, instantiate, and poll workflows
  datasets.py             # Fetch OD600 absorbance results
  transfers.py            # Transfer array generation (media composition)

track-1-research/         # Placeholder — see Notion for Elnora setup
track-2a-closed-loop/     # Monomer MCP agent examples and workflow reference
track-2b-protocol-dev/    # Placeholder — Hamilton STARlet + Cephla setup TBD
track-2c-physical-ai/     # Placeholder — UR10e arm setup TBD
```
