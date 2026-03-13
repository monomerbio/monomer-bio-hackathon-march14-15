# Track A: Build an Autonomous Closed-Loop Agent

**Leads:** Carter Allen ([carter@monomerbio.com](mailto:carter@monomerbio.com)) / Carmen Kivisild (Elnora)

**Goal:** Build an AI agent that runs media optimization experiments autonomously on real cells

---

# Setup: Onboard to Monomer Bio

If you haven't already been onboarded to our system, we will need your email. Monomer staff will stop by after Phase 1 to collect your information, and shortly after this you will receive an email invitation to the [Monomer Culture Monitor](https://cloud-staging.monomerbio.com/).

**NOTE:** If you have a Google account, you may navigate directly to the [Culture Monitor](https://cloud-staging.monomerbio.com/), click **Log In** and then select **Continue with Google**. You will still need to give your email to Monomer Staff so that we can add you to the correct team.

Please make sure you are fully onboarded before proceeding to the next step.

## Connect to the MCP

Monomer's MCP servers are your primary method for interacting with and learning about the Monomer system. There are two MCP servers you will use during the hackathon:

1. **Monomer Cloud MCP** - this MCP is what you will use to interact with your plate data.
2. **Monomer Automation MCP** - this MCP is what you will use to interact with the automated workcell.

We have provided instructions for multiple different ways to connect to our MCP. If you are unfamiliar with these, we recommend following **Option A: Cursor**

### Option A: Cursor

1. Download [Cursor](https://cursor.com/download)
2. Open Cursor → Settings → Tools & MCP → Add Custom MCP
3. Replace the text in this file with the following:

```json
{
  "mcpServers": {
    "monomer-cloud": {
      "type": "http",
      "url": "https://backend-staging.monomerbio.com/mcp"
    },
    "monomer-autoplat": {
      "type": "http",
      "url": "https://desktop-nrh3hvl.tapir-decibel.ts.net/mcp"
    }
  }
}
```

1. Save and close this file.
2. Next to monomer-cloud in the settings, click 'Connect' and go through the authentication flow.

### Option B: Claude Code (requires subscription)

1. Set up Claude Code using the instructions from their [Get Started page](https://code.claude.com/docs/en/overview#get-started).
2. In your terminal, run the following command to set up the **monomer cloud** MCP:

```bash
claude mcp add --scope user --transport http monomer-cloud https://backend-staging.monomerbio.com/mcp
```

1. In your terminal, run the following command to set up the **monomer automation platform** MCP:

```bash
claude mcp add --scope user --transport http monomer-autoplat https://desktop-nrh3hvl.tapir-decibel.ts.net/mcp
```

1. Open a new claude session (type `claude` in your terminal to start).
2. Type `/mcp` and navigate to monomer-cloud using arrow keys. Press enter twice, and then follow the authentication flow in your browser.

### Option C: Claude API

Add the following to your Claude MCP config (`~/.claude.json`):

```json
{
  "mcpServers": {
    "monomer-cloud": {
      "type": "http",
      "url": "https://backend-staging.monomerbio.com/mcp"
    },
    "monomer-autoplat": {
      "type": "http",
      "url": "https://desktop-nrh3hvl.tapir-decibel.ts.net/mcp"
    }
  }
}
```

### Option D: Any MCP-compatible tool

The workcell speaks standard MCP (JSON-RPC 2.0 over HTTP POST). See `CLAUDE.md` for the full tool list and MCP Resources (DSL guides, schema references, and a working example workflow your AI can read directly).

# Tutorial

## Part 1: Workcell Tutorial: Grow Cells with an Automated Workflow via Monomer MCP

Monomer Staff will provide you with an empty 96-well **Experiment** plate, a 24-deep well v-bottom **Reagent Plate** filled with Novel Media, and a 24-well flat-bottom **Cell Culture Stock Plate** with live Vibrio Natriegens in Well A1.

You will complete the following steps to use the MCP to run an experiment to determine the correct seeding density to get the most growth:

### Start: Explore the MCPs

Ask your MCP client (Claude Code, Cursor, etc.) to tell you about the `monomer-cloud` MCP and the `monomer-autoplat` MCP, and what they can be used for.

### Build: Generate a Simple Transfer Workflow on your test plate

Ask Monomer Staff for the name of your `<Reagent Plate>` and `<Cell Culture Stock Plate>`.
Use those inputs to modify the following prompt: 

```
Before creating the workflow, I need you to double check that the wells you choose to transfer from in the <Reagent Plate> contain reagents (Novel Media) in them so that the experiment can work properly. This should be done using a tool from monomer-autoplat to get the latest status and details on the reagent plate.

On top of that, help me check that the well you use to transfer cell stock from on the plate <Cell Culture Stock Plate> has enough culture stock available.

Once that is done, create a workflow to transfer different volumes of Novel Media from <Reagent Plate> and different percentages
of cell stock solution from well A1 of <Cell Culture Stock Plate> into different wells of the 96-well
experiment plate using the hackathon_transfer_samples Routine, make triplicates of percentages from 50% to 5%;
measure absorbance of the plate immediately before the transfer routine and then immediately
after the transfer routine, then every 10 minutes. Instantiate the workflow once it is validated.
```

And then paste this into cursor, claude code, or the MCP client of your choice.

### Analyze: Ask Monomer Cloud for data to help build a graph of Delta OD600 that continuously updates

We are trying to optimize for the biggest change in growth for a given media, not just Max OD600, so it behooves us to capture this delta. Once your plate has finished the liquid handling step, your workflow will continuously take plate reads. You can log in to our [Culture Monitor](https://cloud-staging.monomerbio.com/) (the Monomer Cloud) to view your plate data.

## Part 2: Hackathon Experimentation (Team Experiments)

### Provided Materials

Monomer will provide tips for the opentrons flex, cell culture stocks of growing vibrio natriegens, stock reagent solutions (as described in our [Reagent Database](https://www.notion.so/monomer/2ff8d59ea9ff815a94c7d13e691fe6db?v=2ff8d59ea9ff81c89be7000c0ac066b6)), and three plates to transfer liquids between. For more details beyond constraints of the system, including the scoring system and how to submit requests for filled plates, view the [Track A Experiment and Software Setup](https://www.notion.so/monomer/Track-A-Experiment-and-Software-Setup-3188d59ea9ff8022b5b1da14279f9b7a) 

### Getting Started

A great starting point would be to use the `workflow_definition_template` in the `examples` folder, very similar to the tutorial workflow, to set up your first iteration. 

### Workcell Constraints

- **Workflow approval:** Every workflow goes to `pending_approval` after instantiation. The first few iterations require manual approval from a Monomer team member (~a few minutes). `poll_workflow_completion()` blocks automatically; your agent just waits. If nothing happens after 10 minutes, flag a Monomer team member.
- **One workflow at a time:** The workcell runs workflows sequentially. Wait for the current one to complete before instantiating the next.
- **Tip and reagent tracking:** Handled internally by the workflow template. You don't need to count tips or reagent wells — the template computes consumption from your transfer array.
- **Workcell sharing:** Other teams may be using the workcell. If your workflow is queued but not starting, check with the Monomer team.
- **Volume limits:** P50 handles 1–50 µL, P200 handles 51–200 µL, P1000 handles 201–1000 µL. `apply_constraints()` enforces these in your transfer array.
- **Monitoring frequency:** Minimum 5 minutes between platereader reads. Default in the template is 10 minutes (`monitoring_interval_minutes=10`), which gives a 90-minute window with 9 reads. You can go down to 5 minutes for more granular data.
- **Transferring frequency:** Maximum of **40 transfers** per **90 minutes**, to ensure both teams have enough absorbance data.
- **Reagent plate tag:** Your custom stock plate must be registered on the workcell with a specific `reagent_type` tag before you can use it. Coordinate with the Monomer team when you hand off your plate layout — they'll give you the tag string to use in your workflow.

