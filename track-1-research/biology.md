# Biology Reference: Vibrio natriegens

A quick reference for hackathon contestants. You don't need a biology background — everything you need to design a winning experiment is here.

---

## Why Vibrio natriegens?

*V. natriegens* (also sold as NovaBiotics' "Vmax") is a marine bacterium prized for its speed:
- **Doubling time:** ~20 minutes (vs. ~60 min for *E. coli*)
- **Time to confluence:** ~50 minutes from low seeding density
- **Safety:** BSL-1 — no special containment required
- **Tractable:** grows well in 96-well plates, measurable by OD600

This makes it ideal for a hackathon: you can run 3–4 full growth curves per hour.

---

## Growth in 96-Well Plates

| Parameter | Value |
|-----------|-------|
| Well volume | 180 µL |
| Seeding density | ~OD600 0.05 (low) |
| Confluence | OD600 0.8–1.5+ |
| Growth time (low → confluent) | 50–90 min |
| Platereader interval | Every 10 min |

**OD600** (optical density at 600 nm) is a proxy for cell density — more cells = higher OD600. Readings are taken by the Tecan Infinite or Byonoy platereaders on the workcell.

---

## Media Composition

Each well is 180 µL total. The base is **Novel Bio**, a marine-optimized broth. You supplement it with up to three nutrients:

| Component | Role | Stock well | Min | Max |
|-----------|------|-----------|-----|-----|
| Novel Bio | Base media — carbon, nitrogen, vitamins | D1 | 90 µL | 180 µL |
| Glucose | Additional carbon source | A1 | 0 µL | 90 µL |
| NaCl | Salt / osmolarity adjustment | B1 | 0 µL | 90 µL |
| MgSO4 | Magnesium cofactor, sulfate source | C1 | 0 µL | 90 µL |

**Hard constraints:**
- Novel Bio ≥ 90 µL (below this cells die from nutrient starvation)
- All volumes are integers (1 µL resolution)
- Total = exactly 180 µL

**Example compositions:**

| Name | Novel Bio | Glucose | NaCl | MgSO4 |
|------|-----------|---------|------|-------|
| Control (no supplements) | 180 | 0 | 0 | 0 |
| Glucose-heavy | 90 | 90 | 0 | 0 |
| Balanced | 140 | 15 | 15 | 10 |
| Max NaCl | 90 | 0 | 90 | 0 |

---

## What Affects Growth

Based on published literature for *V. natriegens*:

### Glucose
- Primary carbon supplement — *V. natriegens* metabolizes glucose rapidly
- Moderate amounts (10–30 µL of stock) typically boost growth
- Too much can cause acidification (pH drop inhibits growth)

### NaCl
- *V. natriegens* is marine — it *requires* some salt, but Novel Bio already contains it
- Extra NaCl can improve osmolarity tolerance or inhibit, depending on concentration
- Most sensitive of the three at high concentrations

### MgSO4
- Magnesium is a cofactor for ribosomes and ATP — *V. natriegens* grows fast and needs lots of it
- Often the most positively impactful supplement at low concentrations (5–20 µL)
- Diminishing returns above ~30 µL

### Interactions
Nutrients interact non-linearly. A combination of Glucose + MgSO4 often outperforms either alone. This is why a DOE or gradient descent approach beats one-factor-at-a-time testing.

---

## Scoring

```
score = Σ over all wells:  (1 if OD600 > baseline else 0) × OD600_endpoint
```

Practically: maximize both **how many wells grow** and **how high OD600 gets in each well**.

A strategy that gets 96 wells all to OD600 = 0.5 scores higher than 10 wells at OD600 = 2.0.

---

## Growth Curve Interpretation

A typical OD600 time series looks like:

```
Time (min):  0     10    20    30    40    50    60    70
OD600:       0.05  0.06  0.09  0.18  0.40  0.85  1.20  1.35
```

- **Lag phase** (0–10 min): cells adjusting to environment
- **Exponential phase** (10–50 min): doubling every 20 min
- **Stationary phase** (50+ min): nutrients depleting, growth slows

For the overnight race, you want to passage wells *during exponential phase* — not after stationary — to keep growth maximized.

---

## Passaging

"Passaging" means transferring a small volume of growing cells into fresh media, diluting them back into exponential growth.

| Parameter | Typical range |
|-----------|--------------|
| Transfer volume | 10–30 µL per well |
| Fresh media added | 150–170 µL |
| Timing | When OD600 > 0.4 (mid-exponential) |
| Target post-passage OD600 | ~0.05 |

An AI agent monitoring OD600 in real-time can decide *when* to passage each well independently — this is the Track 2A "closed loop" challenge.
