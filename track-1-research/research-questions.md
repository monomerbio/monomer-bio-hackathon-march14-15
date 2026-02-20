# Research Questions for Track 1

Copy-paste these prompts into Elnora (or Claude, GPT-4, etc.) to research your experimental plan.

---

## Starter Prompt (give this to Elnora first)

```
I'm participating in a cell culture hackathon. I'm optimizing growth media for
Vibrio natriegens in 96-well plates. Each well is 180 µL total. The base media
is "Novel Bio" marine broth (must be ≥ 90 µL per well). I can supplement with
up to 90 µL each of: Glucose (stock solution), NaCl (stock solution), and
MgSO4 (stock solution). Scoring is total biomass = sum of OD600 readings
across all 96 wells. I have about 2 hours per experiment, with OD600 measured
every 10 minutes.

Help me design the optimal experimental strategy.
```

---

## Biology Questions

### 1. Component Impact
```
For Vibrio natriegens grown in marine broth:
- Which supplement typically has the biggest positive effect on growth rate:
  Glucose, NaCl, or MgSO4?
- What is the mechanism of each supplement's effect?
- Are there known concentration thresholds where each becomes inhibitory?
```

### 2. Concentration Ranges
```
For Vibrio natriegens, what are the literature-supported optimal concentration
ranges for:
- Glucose (as a carbon supplement added to marine broth)
- NaCl (added to marine broth that already contains salt)
- MgSO4 (as a cofactor supplement)

Express as mM concentrations AND as µL of a 1x stock solution in 180 µL total.
```

### 3. Interactions
```
Are there known synergistic or antagonistic interactions between Glucose, NaCl,
and MgSO4 for Vibrio natriegens growth? Specifically:
- Does glucose metabolism acidify the media enough to matter at these volumes?
- Does excess NaCl inhibit Mg2+ uptake?
- Is there a Glucose × MgSO4 interaction (ribosomes + carbon)?
```

---

## Experimental Design Questions

### 4. DOE vs. Gradient Descent
```
I have 96 wells to test 3 nutrients (Glucose, NaCl, MgSO4) at 0–90 µL each.
Compare these approaches:
1. Full factorial DOE (all combinations at 5 levels each = 125 conditions —
   too many for 96 wells, needs fractional)
2. Central composite design (CCD) — fits in ~20 wells for 3 factors
3. Latin hypercube sampling — space-filling design
4. Gradient descent starting from a center point — iterative, 8 wells per step
5. Bayesian optimization

Which approach would you recommend for maximizing information per plate given
we can run 3–4 plates over a 6-hour window?
```

### 5. Plate Layout
```
Design a 96-well plate layout for a 3-factor DOE (Glucose, NaCl, MgSO4) that:
- Includes at least 4 control wells (Novel Bio only)
- Tests each factor at 5 concentration levels
- Maximizes coverage of the design space
- Includes replicates for the most promising conditions

Output the layout as a table: well position → composition (µL of each component).
```

### 6. Controls
```
What controls should I include in each plate run for Vibrio natriegens growth?
- Positive control: what media composition reliably grows well?
- Negative control: just media, no cells?
- Baseline control: cells in Novel Bio only?
How many wells should I allocate to controls vs. experimental conditions?
```

---

## Passaging Strategy Questions

### 7. Passage Timing
```
Vibrio natriegens has a 20-minute doubling time. I'm monitoring OD600 every
10 minutes. An AI agent can trigger a passaging routine in real-time.

At what OD600 threshold should the agent decide to passage?
Consider:
- We want to keep cells in exponential growth (not stationary)
- Passaging too early wastes time and dilutes cells too much
- Passaging too late means growth has already slowed

Give a specific OD600 threshold recommendation with reasoning.
```

### 8. Split Ratio
```
For an overnight experiment (6 PM Saturday to 4 PM Sunday, 22 hours):
- If I passage 20 µL of cells into 160 µL of fresh media (1:9 split),
  how many passages can I complete?
- What split ratio (volume transferred) maximizes total OD600 × wells at
  the 4 PM endpoint?
- Should I use a fixed split ratio or adapt it based on current OD600?
```

### 9. AI Decision Policy
```
I'm building an AI agent that monitors OD600 and decides when to passage.
Design a simple decision policy for this agent:
- What input features should it observe? (current OD600, time since last
  passage, growth rate estimate, etc.)
- What action should it take? (passage now, wait, adjust split ratio)
- How should it handle wells that aren't growing at all?

Output a pseudocode decision function.
```

---

## Synthesis Question

After answering the above, ask:

```
Based on everything above, give me:
1. The single best starting media composition to test (Glucose µL, NaCl µL,
   MgSO4 µL, Novel Bio µL)
2. A 96-well plate layout for the first experiment
3. A passaging timing rule for the overnight race
4. The biggest uncertainty in this plan and how to resolve it with data from
   the first experiment
```
