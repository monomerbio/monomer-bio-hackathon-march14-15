# Track 1: Research Cell Culture Protocols

**Lead:** Carmen Kivisild (carmen.kivisild@elnora.ai)
**Duration:** Saturday morning (10 AM – 12 PM), all teams
**Output:** A concrete experimental plan to take into Track 2

---

## Objective

Use Elnora (or your preferred AI tool) to research *Vibrio natriegens* growth optimization and arrive at a specific plan:
- Which media components to vary and at what concentrations
- How many conditions you can test in 96 wells
- What order to run experiments (DOE vs. iterative)
- What passaging strategy to use for the overnight race

This is collaborative — all teams share findings before splitting into Track 2.

---

## Setup: Elnora

Elnora is an AI research assistant trained on scientific literature. It can answer biology questions, help design DOEs, and critique experimental plans.

1. Get your team's Elnora org credentials from a Monomer team member (each team has $500 credits)
2. Connect via Elnora's MCP or API — ask Carmen for the current setup guide
3. Start with the research questions below

---

## The Biology in Brief

See [biology.md](./biology.md) for full details. Key facts:
- *V. natriegens* doubles every ~20 minutes — you can see 3–4 doublings in a 60-minute experiment
- You're growing in 96-well plates, 180 µL per well
- Base media is **Novel Bio** — must be ≥ 90 µL per well
- Three supplementable nutrients: **Glucose**, **NaCl**, **MgSO4** (0–90 µL each)
- OD600 is measured every 10 minutes; scoring is Σ(wells × OD600)

---

## Research Questions

These are the questions to work through in Track 1. See [research-questions.md](./research-questions.md) for detailed prompts to use with Elnora.

### Biology
1. What is the role of Glucose, NaCl, and MgSO4 in *V. natriegens* growth?
2. What concentration ranges are typical in marine media formulations?
3. How does osmolarity (driven by NaCl) interact with growth rate?
4. What is the expected growth ceiling (max OD600) in 180 µL?

### Experimental Design
5. Given 96 wells and 3 supplements at ~5 concentration levels each: how many conditions can you test in one plate?
6. Is a full-factorial DOE feasible? What about a Latin Hypercube, central composite, or Sobol design?
7. What's the minimum number of controls to include (no supplements, just Novel Bio)?
8. How many replicates per condition do you need to detect a real effect?

### Passaging Strategy (Track 2 / Overnight Race)
9. Given a 20-min doubling time, when should you passage to keep cells in exponential growth?
10. What split ratio (volume transferred vs. fresh media) maximizes total biomass over 24 hours?
11. Can an AI agent decide when to passage based on real-time OD600 data?

---

## Deliverable

At 12 PM, each team presents a 5-minute plan covering:
- Top 2–3 media components to optimize and concentration ranges
- Plate layout (how you'll allocate 96 wells)
- Workflow sequence (first experiment → feedback loop → overnight)
- Hypothesis: what do you expect to be the winning formulation and why?

Track leads (Carter, Carmen) will review for feasibility before you run anything on the workcell.
