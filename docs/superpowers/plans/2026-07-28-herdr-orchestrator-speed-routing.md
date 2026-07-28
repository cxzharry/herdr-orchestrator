# Herdr Orchestrator Speed and Skill Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic eight-pane workflow with a concise nine-pane,
event-driven skill that prescribes phase-specific Superpowers skills and renders
the approved parallel node order in its canonical graph.

**Architecture:** Keep `SKILL.md` as a thin router and split Herdr-specific
details into four conditionally loaded references. Add one deterministic
contract validator, update the existing semantic graph validator before
changing the graph, then regenerate the Excalidraw/SVG/PNG bundle from one
locked topology.

**Tech Stack:** Markdown skills, Python 3 validators, Excalidraw JSON, SVG,
headless Chrome, Pillow, Git.

## Global Constraints

- Follow the approved design at
  `docs/superpowers/specs/2026-07-28-herdr-orchestrator-speed-routing-design.md`.
- Keep at most nine panes: P1 orchestrator, P2-P5 workers, P5 Integration
  Owner after restart, P6 Integration Reviewer, P7 QC, P8 Designer, P9 Persona.
- P1 uses `gpt-5.6-sol/high`; P2-P4 use `gpt-5.5/medium`; P5-P7 use
  `gpt-5.6-sol/high`; P8 uses `gpt-5.5/high`; P9 uses `gpt-5.5/medium`.
- P1 completes the full brainstorming workflow on every run, then invokes
  `writing-plans`; Herdr is the preselected execution mode.
- Herdr remains the sole scheduler. Runtime panes must not invoke
  `dispatching-parallel-agents`, `subagent-driven-development`,
  `executing-plans`, or `requesting-code-review`.
- P5 smoke and P6 Integration Review run concurrently. P7-P9 prepare early and
  run applicable post-deploy reviews concurrently.
- P5 smoke plus P6 PASS deploys to `dev`; in a single-environment topology, it
  deploys to the only environment immediately under a locked rollback or
  fix-forward policy.
- When no deployment target exists, start an isolated local review runtime and
  deliver evidence without claiming a deployment.
- Preserve deterministic mock data, all applicable system roles, Playwright
  isolation, Git ownership, and revision-bound evidence.
- Outside decisions and evidence, graph colors distinguish only P1 from other
  agents. A violet badge marks P5's second role in the same pane.
- Do not push to GitHub until the user asks; local commits are allowed.

---

### Task 1: Capture the current failure and add the routing contract validator

**Files:**
- Create: `scripts/verify_contract.py`
- Test: `SKILL.md`
- Test: `references/runtime-contract.md`
- Test: `agents/openai.yaml`

**Interfaces:**
- Consumes: the approved pane roster, skill routing, deployment policies, and
  progressive-disclosure file names.
- Produces: a JSON result with `status`, `panes`, `required_references`, and
  `failures`, exiting nonzero for contract drift.

- [ ] **Step 1: Record the pre-edit baseline**

Run:

```bash
python3 scripts/verify_assets.py
python3 scripts/render_assets.py --check assets/delivery-flow.png
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
wc -w SKILL.md references/runtime-contract.md
```

Expected: the current eight-pane asset checks pass and the word count records
the monolithic baseline.

- [ ] **Step 2: Forward-test the current skill before changing it**

Run the four raw scenarios from the approved design with fresh agents against
the current checkout. Do not mention the intended redesign. Capture only
elapsed time, invoked skills, nested dispatches, phase reached, and blocker in a
temporary directory outside the repository.

Expected: at least one scenario reproduces slow or drifting P5/P6 behavior. If
none does, stop and report that the proposed change lacks a behavioral RED
baseline.

- [ ] **Step 3: Write the desired-state validator**

Create `scripts/verify_contract.py` with these exact checks:

```python
EXPECTED_PANES = {
    "P1": ("Orchestrator", "gpt-5.6-sol", "high"),
    "P2": ("Worker 1", "gpt-5.5", "medium"),
    "P3": ("Worker 2", "gpt-5.5", "medium"),
    "P4": ("Worker 3", "gpt-5.5", "medium"),
    "P5": ("Worker 4, then Integration Owner", "gpt-5.6-sol", "high"),
    "P6": ("Integration Reviewer", "gpt-5.6-sol", "high"),
    "P7": ("QC", "gpt-5.6-sol", "high"),
    "P8": ("Designer", "gpt-5.5", "high"),
    "P9": ("Persona", "gpt-5.5", "medium"),
}
REQUIRED_REFERENCES = {
    "references/routing.md",
    "references/git-integration.md",
    "references/review-deploy.md",
    "references/high-assurance.md",
}
FORBIDDEN_RUNTIME_SKILLS = {
    "dispatching-parallel-agents",
    "subagent-driven-development",
    "executing-plans",
    "requesting-code-review",
}
```

The validator must parse the roster table, require the lane-brief fields,
require conditional reference links, require the staged/single/local deployment
policies, require the allowed skill chains, reject a mandatory
`runtime-contract.md` read, and reject any instruction to invoke a forbidden
runtime skill.

- [ ] **Step 4: Verify RED**

Run:

```bash
python3 scripts/verify_contract.py
```

Expected: FAIL naming the missing P9 roster, missing split references, stale
eight-pane metadata, and mandatory monolithic reference.

- [ ] **Step 5: Commit the RED validator**

```bash
git add scripts/verify_contract.py
git commit -m "test: define nine-pane routing contract"
```

### Task 2: Refactor the skill into a thin router

**Files:**
- Modify: `SKILL.md`
- Modify: `agents/openai.yaml`
- Create: `references/routing.md`
- Create: `references/git-integration.md`
- Create: `references/review-deploy.md`
- Create: `references/high-assurance.md`
- Delete: `references/runtime-contract.md`
- Test: `scripts/verify_contract.py`

**Interfaces:**
- Consumes: the design spec and desired-state validator from Task 1.
- Produces: a concise entrypoint plus one always-read routing reference and
  three predicate-selected operational references.

- [ ] **Step 1: Rewrite `SKILL.md` as the router**

Keep only:

1. P1's core invariant and required `herdr` sub-skill.
2. The nine-pane model roster.
3. Full `brainstorming → writing-plans → Herdr` transition.
4. The lane-brief field list.
5. The event order: workers → P5 publish → P5 smoke plus P6 review → deploy →
   parallel P7-P9 → applicable release decision.
6. A conditional reference table.

Target at most 350 words. Do not duplicate Git, Playwright, RBAC, evidence, or
Superpowers procedures.

- [ ] **Step 2: Write `references/routing.md`**

Define:

- readiness waves rather than unconditional worker fan-out;
- the exact lane-brief shape;
- each role's required and conditional skill chain;
- P5's mandatory clean-session transition;
- P6-P9 read-only reviewer boundaries;
- immediate receipts to P1;
- two-repeat blocker escalation;
- explicit prohibition on nested scheduler skills.

- [ ] **Step 3: Split conditional operational references**

Write:

- `git-integration.md`: shared-tree and worktree ownership, accepted SHA
  ancestry, P5-only integration mutation, and P6 read-only attestation.
- `review-deploy.md`: P5 smoke, P6 gate, deployment topology, parallel P7-P9,
  isolated runtime/tenant/seed/profile/lock, mock data, all roles, rollback, and
  impacted reruns.
- `high-assurance.md`: nonce/transcript, reproducible build, strict evidence,
  security-sensitive and destructive-work escalation only.

Delete `references/runtime-contract.md` after every retained invariant has one
new owner. Do not preserve duplicated prose.

- [ ] **Step 4: Refresh UI metadata**

Set:

```yaml
interface:
  display_name: "Herdr Orchestrator"
  short_description: "Run fast nine-pane Herdr delivery loops"
  default_prompt: "Use $herdr-orchestrator to route this task through nine Herdr panes with event-driven integration, deployment, and parallel review."
```

- [ ] **Step 5: Verify GREEN for the text contract**

Run:

```bash
python3 scripts/verify_contract.py
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
wc -w SKILL.md references/routing.md
```

Expected: contract PASS, skill valid, `SKILL.md` no more than 350 words, and no
mandatory monolithic runtime-contract read.

- [ ] **Step 6: Commit the router refactor**

```bash
git add SKILL.md agents/openai.yaml references scripts/verify_contract.py
git commit -m "refactor: route Herdr work by phase"
```

### Task 3: Make the graph validator require the approved nine-pane topology

**Files:**
- Modify: `scripts/verify_assets.py`
- Test: `assets/delivery-flow.excalidraw`
- Test: `assets/delivery-flow.svg`
- Test: `assets/delivery-flow.png`

**Interfaces:**
- Consumes: the event order and role labels from the design spec.
- Produces: a validator that rejects eight-pane, sequential-review, detached
  arrow, wrong-color, and misplaced-node graphs.

- [ ] **Step 1: Replace the expected pane and node allowlists**

Use pane IDs:

```python
PANE_IDS = (
    "orchestrator",
    "worker_1",
    "worker_2",
    "worker_3",
    "worker_4",
    "integration_reviewer",
    "qc",
    "designer",
    "persona",
)
```

Use flow nodes:

```python
FLOW_NODE_IDS = {
    "task", "orchestrator", "ready", "contract", "isolation", "worktree",
    "fork", "worker_1", "worker_2", "worker_3", "worker_4", "integrated",
    "smoke", "integration_reviewer", "artifact_gate", "deploy",
    "review_fork", "qc", "designer", "persona", "review_gate",
    "promotion", "verified", "end",
}
```

- [ ] **Step 2: Require the exact directed graph**

Set `EXPECTED_EDGES` to:

```python
{
    ("task", "orchestrator"),
    ("orchestrator", "ready"),
    ("ready", "contract"),
    ("ready", "orchestrator"),
    ("contract", "isolation"),
    ("isolation", "fork"),
    ("isolation", "worktree"),
    ("worktree", "fork"),
    ("fork", "worker_1"),
    ("fork", "worker_2"),
    ("fork", "worker_3"),
    ("fork", "worker_4"),
    ("worker_1", "integrated"),
    ("worker_2", "integrated"),
    ("worker_3", "integrated"),
    ("worker_4", "integrated"),
    ("integrated", "smoke"),
    ("integrated", "integration_reviewer"),
    ("smoke", "artifact_gate"),
    ("integration_reviewer", "artifact_gate"),
    ("artifact_gate", "deploy"),
    ("artifact_gate", "orchestrator"),
    ("deploy", "review_fork"),
    ("review_fork", "qc"),
    ("review_fork", "designer"),
    ("review_fork", "persona"),
    ("qc", "review_gate"),
    ("designer", "review_gate"),
    ("persona", "review_gate"),
    ("review_gate", "promotion"),
    ("review_gate", "orchestrator"),
    ("promotion", "verified"),
    ("verified", "end"),
}
```

Require every arrow to bind both endpoints, every non-END flow node to have an
outgoing edge, every non-TASK flow node to have an incoming edge, and
`promotion`, `verified`, and `end` to be separate non-overlapping nodes.

- [ ] **Step 3: Require canonical labels and role colors**

Require labels for:

- `P5 INTEGRATION OWNER + SMOKE`;
- `P6 INTEGRATION REVIEWER`;
- `P7 QC`;
- `P8 DESIGNER`;
- `P9 PERSONA`;
- `P5 SMOKE + P6 REVIEW IN PARALLEL`;
- `DEPLOY DEV / SOLE ENV / START LOCAL REVIEW`;
- `P7 QC · P8 DESIGNER · P9 PERSONA IN PARALLEL`.

Keep P1 green and other agents white. Allow evidence blue, decisions amber, and
only P5's second-role badge violet.

- [ ] **Step 4: Verify RED against the old graph**

Run:

```bash
python3 scripts/verify_assets.py
```

Expected: FAIL with nine-pane allowlist, expected edge, text, and source-digest
drift failures.

- [ ] **Step 5: Commit the RED graph validator**

```bash
git add scripts/verify_assets.py
git commit -m "test: require nine-pane delivery graph"
```

### Task 4: Draw and render the event-driven graph

**Files:**
- Modify: `assets/delivery-flow.excalidraw`
- Modify: `assets/delivery-flow.svg`
- Modify: `assets/delivery-flow.png`
- Modify: `assets/manifest.json`
- Modify: `scripts/verify_assets.py`
- Modify: `references/delivery-flow.md`
- Test: `scripts/verify_assets.py`
- Test: `scripts/render_assets.py`

**Interfaces:**
- Consumes: the exact nodes, edges, labels, and style constraints from Task 3.
- Produces: editable Excalidraw, canonical SVG, exact-byte PNG, updated hashes,
  and a human-readable graph reference.

- [ ] **Step 1: Invoke the Excalidraw skill and redraw semantic sources**

Use `$excalidraw`. Preserve the current dark visual language, two agent colors,
decision/evidence exceptions, bound orthogonal arrows, and violet P5
second-role badge.

Lay out nodes left-to-right in this visible order:

```text
Task → P1 Contract → Ready/Isolation → P2-P5 Workers → P5 Integrate
     → [P5 Smoke || P6 Integration Review] → Artifact Verified → Deploy
     → [P7 QC || P8 Designer || P9 Persona] → Release Decision
     → Promote/Keep Sole Environment → Verified Delivery → End
```

Show preparation as a side annotation from the published artifact to P7-P9,
not as a blocking main-path node.

- [ ] **Step 2: Update graph reference text**

Change `references/delivery-flow.md` to state:

- nine panes are the maximum topology;
- worker waves are conditional;
- P5 smoke and P6 review are parallel;
- P7-P9 prepare early and review concurrently;
- deployment policy depends on staged, single, or local topology.

- [ ] **Step 3: Render PNG and refresh asset hashes**

Run:

```bash
python3 scripts/render_assets.py --write assets/delivery-flow.png
sha256sum assets/delivery-flow.excalidraw assets/delivery-flow.svg assets/delivery-flow.png
```

Copy the three exact SHA-256 values into `assets/manifest.json`. Copy the
Excalidraw and SVG values into `CANONICAL_SOURCE_HASHES`. Set each
`derived_from_render_source_sha256` value to the new SVG digest.

- [ ] **Step 4: Verify GREEN for graph semantics and bytes**

Run:

```bash
python3 scripts/render_assets.py --check assets/delivery-flow.png
python3 scripts/verify_assets.py
```

Expected: exact render match, `panes: 9`, `arrows: 33`, and zero
failures.

- [ ] **Step 5: Inspect the actual graph**

Call `view_image` on `assets/delivery-flow.png`. Confirm:

- node order is readable without tracing crossings;
- parallel branches are visually distinct;
- every arrow touches both nodes;
- END is outside Verified Delivery;
- feedback arrows do not cross worker-4 or review labels;
- all nine pane labels are visible.

Fix semantic sources and repeat render/validation if any item fails.

- [ ] **Step 6: Commit the graph**

```bash
git add assets references/delivery-flow.md scripts/verify_assets.py
git commit -m "docs: draw parallel nine-pane delivery flow"
```

### Task 5: Forward-test behavior and install the verified skill

**Files:**
- Modify only if a forward-test exposes a concrete gap: `SKILL.md`,
  `references/*.md`, `scripts/verify_contract.py`, `scripts/verify_assets.py`,
  `assets/*`
- Install from: repository root
- Install to: `/home/haidx14/.codex/skills/herdr-orchestrator`

**Interfaces:**
- Consumes: the revised bundle and the four baseline scenarios from Task 1.
- Produces: verified behavioral comparison, installed skill, and one final
  clean commit.

- [ ] **Step 1: Run the four scenarios with fresh agents**

Pass the revised skill and raw task only. Do not expose the intended answer or
baseline diagnosis. Record the same fields as Task 1.

Expected:

- lane briefs name the right skills and stop conditions;
- no nested scheduler appears;
- P5 changes session before integration;
- P6 returns a bounded read-only verdict;
- P5 smoke and P6 review overlap;
- deployment starts after their receipts;
- P7-P9 overlap when isolation exists;
- the same blocker does not loop more than twice.

- [ ] **Step 2: Compare baseline and revised behavior**

Require equal or better task completion and evidence quality. Require fewer
unnecessary skill loads, no extra panes, no nested dispatch, and a shorter
post-spec critical path. If quality regresses, do not install; tighten only the
specific failed contract and rerun that scenario.

- [ ] **Step 3: Run the complete local gate**

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/verify_contract.py
python3 scripts/render_assets.py --check assets/delivery-flow.png
python3 scripts/verify_assets.py
python3 - <<'PY'
from pathlib import Path
for path in sorted(Path("scripts").glob("*.py")):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print(f"OK {path}")
PY
git diff --check
```

Expected: every command exits zero, graph reports nine panes, and every script
compiles without writing bytecode.

- [ ] **Step 4: Install the exact verified bundle**

Copy only:

```text
SKILL.md
agents/openai.yaml
assets/delivery-flow.excalidraw
assets/delivery-flow.svg
assets/delivery-flow.png
assets/manifest.json
references/delivery-flow.md
references/routing.md
references/git-integration.md
references/review-deploy.md
references/high-assurance.md
scripts/render_assets.py
scripts/verify_assets.py
scripts/verify_contract.py
```

Exclude `.git`, `docs`, `__pycache__`, and `.pyc`. Compare every installed file
with `cmp`.

- [ ] **Step 5: Verify the installed copy**

Run:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  ~/.codex/skills/herdr-orchestrator
python3 ~/.codex/skills/herdr-orchestrator/scripts/verify_contract.py
python3 ~/.codex/skills/herdr-orchestrator/scripts/verify_assets.py
```

Expected: the installed skill, routing contract, exact graph, and all nine panes
pass.

- [ ] **Step 6: Commit any evidence-driven corrections**

```bash
git add SKILL.md agents assets references scripts
git commit -m "fix: close Herdr routing validation gaps"
```

Skip this commit when forward-testing required no corrections.

- [ ] **Step 7: Final repository verification**

```bash
git status --short --branch
git log --oneline --decorate -6
```

Expected: clean worktree and local `main` ahead of `origin/main`. Report the
graph path, validator outputs, commit SHAs, installed path, and that no push was
performed.
