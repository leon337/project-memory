# Project Memory Continuity Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `project-memory` resumable by a fresh AI/client through explicit project-local continuity rules while keeping technical truth in the existing canonical project documents.

**Architecture:** The project consumes the universal MCF continuity protocol and provides a small overlay that maps project-specific authority domains, freshness requirements and live-state sources. `STATUS.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `NEXT.md` and `.mcf/project-capsule.yaml` remain the canonical project entrypoints; runtime/live truth is re-observed rather than copied into chat memory.

**Tech Stack:** Markdown, YAML, existing project-memory canonical documents and GitHub metadata.

**Spec:** Gate 3 architecture explicitly approved by LEANDRO on 2026-09-07 and the universal MCF continuity protocol created by the paired Gate 3 MCF branch.

## Global Constraints

- `project-memory` remains owner of Robô Operador technical truth.
- MCF provides discovery/governance rules but must not absorb project runtime state.
- Chat/model memory is never authoritative.
- Remote GitHub state and local/live notebook state must remain distinct.
- Approval and evidence are separate; authorization never upgrades a failing or unverified technical result to PASS.
- Before the Gate 3 changes are merged and re-read from `main`, the project must represent them as `CANONICALIZATION_PENDING`.
- No Robô runtime behavior, executor, provider, SQLite schema or physical input path is changed by this documentation gate.
- No tag, release, production deployment or destructive operation is authorized by this plan.

---

### Task 1: Create the project continuity overlay

**Files:**
- Create: `docs/CONTINUITY.md`

**Interfaces:**
- Consumes: universal MCF continuity protocol and existing canonical project docs.
- Produces: project-specific domain authority/freshness map used by fresh clients.

- [ ] **Step 1:** Define authority by domain: identity/discovery -> MCF registry; architecture -> `ARCHITECTURE.md`; verified current state -> `STATUS.md` plus evidence; decisions -> `DECISIONS.md`; next work -> `NEXT.md`; quick snapshot -> capsule; live desktop/runtime -> live observation; task execution history -> durable runtime records where applicable.
- [ ] **Step 2:** Define freshness rules and when a live notebook observation is mandatory.
- [ ] **Step 3:** Define remote vs local snapshot fields and explicit stale/conflict semantics.
- [ ] **Step 4:** Define the exact bootstrap order for a fresh client resuming the Robô Operador.
- [ ] **Step 5:** Define conflict checks before publication using base SHA/current remote head and overlapping open work.
- [ ] **Step 6:** State that chat history may provide hints but cannot override canonical or live sources.
- [ ] **Step 7:** Commit the overlay.

### Task 2: Persist Gate 3 decision and pending-canonicalization state

**Files:**
- Modify: `docs/DECISIONS.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/NEXT.md`
- Modify: `.mcf/project-capsule.yaml`

**Interfaces:**
- Consumes: Task 1 overlay and human approval.
- Produces: project memory that accurately distinguishes approved design from merged/canonical implementation.

- [ ] **Step 1:** Add a decision recording the hybrid responsibility split (`MCF` universal / `project-memory` technical / runtime live), domain authority, remote/local separation, governance/evidence axes and pending canonicalization.
- [ ] **Step 2:** Update `STATUS.md` with Gate 3 state as approved/in implementation and explicitly not yet canonical until merge and verification.
- [ ] **Step 3:** Replace the old NEXT item asking for protocol approval with implementation/validation/merge/bootstrap-test steps.
- [ ] **Step 4:** Update capsule workstream, next action, blockers/resolved findings and add `continuity_overlay: docs/CONTINUITY.md` while keeping Gate 3 `CANONICALIZATION_PENDING`.
- [ ] **Step 5:** Commit the canonical-memory updates.

### Task 3: Project-local consistency validation

**Files:**
- Validate: `docs/CONTINUITY.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/NEXT.md`, `.mcf/project-capsule.yaml`.

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces: static PASS/FAIL evidence before PR.

- [ ] **Step 1:** Re-read all modified files from the branch and verify terminology/state values are consistent.
- [ ] **Step 2:** Verify `NEXT.md` no longer says the protocol awaits architectural approval.
- [ ] **Step 3:** Verify capsule does not claim Gate 3 canonical before merge.
- [ ] **Step 4:** Verify every authority domain resolves to a real existing source or an explicitly live source.
- [ ] **Step 5:** Compare branch against `main` and inspect the complete diff for unrelated changes.
- [ ] **Step 6:** Open a draft PR and declare the paired MCF PR as dependency.

### Task 4: Fresh-context acceptance test definition

**Files:**
- Create: `artifacts/gates/GATE-03-MULTI-AI-CONTINUITY-VALIDATION-20260907.md`

**Interfaces:**
- Consumes: project overlay plus paired MCF protocol.
- Produces: auditable criteria for the fresh-context test and final Gate 3 verdict.

- [ ] **Step 1:** Define the cold-start prompt: `Continue o projeto do Robô Operador.`
- [ ] **Step 2:** Require the fresh client to identify `leon337/project-memory`, load capsule and canonical entrypoints, report Gate 2R as the last completed physical gate, identify Gate 3 as current work, and avoid claiming chat memory as authority.
- [ ] **Step 3:** Require explicit remote/local distinction and conflict/freshness check before proposing a write.
- [ ] **Step 4:** Record each acceptance criterion as PASS/FAIL/BLOCKED with evidence refs.
- [ ] **Step 5:** If no tool can instantiate an actually fresh client automatically, mark only that execution step `BLOCKED_BY_EXTERNAL_SURFACE` rather than fabricating a PASS; keep static checks independently scored.

### Task 5: Final canonicalization after paired merge

**Files:**
- Modify after merge: `.mcf/project-capsule.yaml`
- Modify after merge if needed: `docs/STATUS.md`, `docs/NEXT.md`, Gate 3 validation artifact.

**Interfaces:**
- Consumes: merged MCF protocol, merged project overlay and acceptance evidence.
- Produces: canonical Gate 3 closure or an explicit remaining blocker.

- [ ] **Step 1:** Re-read both repositories from `main` after merge and capture final commit SHAs.
- [ ] **Step 2:** Change governance state from `CANONICALIZATION_PENDING` to `CANONICAL` only if both required documents are on `main` and cross-references resolve.
- [ ] **Step 3:** Record evidence verdict separately from governance state; a blocked fresh-client execution cannot be rewritten as PASS.
- [ ] **Step 4:** Update next action to the drawer/responsiveness work only if Gate 3 acceptance criteria are actually satisfied.
- [ ] **Step 5:** Commit/PR the closure update if a post-merge canonicalization commit is necessary.