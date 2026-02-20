# Track 2C: Physical AI — Automate Flask-Based Cell Culture

**Lead:** TBD
**Goal:** Program a UR10e robotic arm to manipulate manual instruments and automate large-volume cell culture in T-flasks

---

## Hardware Available

| Instrument | Specs |
|-----------|-------|
| **Universal Robot UR10e** | 6-axis arm, 12.5 kg payload, 1300 mm reach |
| **RobotIQ 2F-85 Gripper** | Parallel gripper, 85 mm stroke |
| Manual incubator | Standard bench-top |
| Nikon Eclipse TS2 Inverted Microscope | Manual, inverted |
| T-75 Flasks | Large volume cell culture |
| Serological pipette controller | AccuHelp |
| Serological pipettes | 10 mL, Oxford Lab Products |
| Automated bottle opener | Giaretti LA CASA |

---

## What to Build

An automated workflow for flask-based *V. natriegens* culture:
1. Arm picks up flask from incubator
2. Arm operates pipette to add/remove media
3. Arm places flask under microscope for imaging
4. Agent decides next action based on image/OD

This is the highest difficulty track — ideal for robotics or CV engineers.

---

## Getting Started

The UR10e is programmed via URScript (native) or Python wrappers. Ask a Monomer team member for:
- UR10e access and safety briefing (mandatory before touching the arm)
- URScript documentation
- RobotIQ gripper SDK

**Safety:** The UR10e has a 12.5 kg payload and 1300 mm reach. Always run in simulation mode first, and have a team member present during first physical tests.
