# Context Document Standards

`CLAUDE.md` is loaded into the model's context **on every turn**, so its size
is a recurring tax paid by every session. This document is the git-tracked
**standard** for keeping it lean and load-bearing; the `/optimize-claude-md`
skill (`.claude/commands/optimize-claude-md.md`) is the **executor** that
applies this standard consistently each time. When our thinking evolves, edit
*this* file once and every future run follows it — same "git holds the truth,
a tool applies it" pattern as `reference/field_synonyms.json` +
`auto_mapper.py`.

This is not a one-off cleanup. `CLAUDE.md` accretes as the project grows
(a single session can add several rules); this standard exists so the
periodic trim is principled and repeatable, not done by feel.

## What CLAUDE.md is for — and isn't

**It is for:**
- The **directives** an agent must follow here (hard rules, the standard
  workflow, "use command X", "confirm before Y").
- A **complete but terse inventory** of the CLI commands / tools and how to
  invoke them (name + key flags), so an agent knows what exists.
- Project summary, high-level "where things live", build/test/commit
  conventions.
- **Pointers** to the deeper docs where the *why* lives.

**It is not for** (these have homes — see the routing table):
- Multi-sentence design rationale or architecture justification.
- Live-finding war stories / the full narrative behind a rule.
- Exhaustive flag lists or edge-case behavior for a command.
- Historical evolution ("originally X, then Y") — git already has it.

## The four-class rubric

Classify every block of `CLAUDE.md` as exactly one of these, and act:

| Class | What it is | Action |
|---|---|---|
| **Directive** | An instruction the agent must follow | **Keep, compressed** — the named/numbered rule + a one-*clause* why + a pointer to full detail |
| **Rationale** | The story/justification behind a rule; a live-finding narrative | **Relocate** to its home doc; leave a one-line pointer. Move the paragraph out, lose nothing |
| **Reference** | Exhaustive flag lists, command back-story, file inventories | **Compress** to name + one-line purpose + pointer (full detail already lives in README / `--help` / module docstrings) |
| **Stale** | A rule for a problem that no longer occurs, or a workaround for an old-model weakness | **Flag for human decision** — never auto-delete |

The test for Directive-vs-Rationale: *"Is this an instruction the agent must
act on, or an explanation of one?"* Instructions stay (compressed);
explanations relocate with a pointer.

## Routing table — where relocated content goes

Most of it already exists in these homes; relocation is usually *dedup +
pointer*, not fresh writing.

| Relocated content | Home |
|---|---|
| Design rationale / architecture | `README.md` |
| Live-finding war story / process gap | `ROADMAP.md` (numbered item) or `postmortems/` |
| Object- or cloud-specific behavior finding | `validators/` or `okf/` |
| Command flag detail / behavior | that command's module docstring, or `README.md` |
| Pure historical evolution | git history — drop it, don't relocate |

## Invariants — never violate these

A trim is a **presentation/location refactor, not a rules change.** The
executor must verify all of these before proposing a diff:

1. **Every hard rule keeps its number *and* short name** (stable
   cross-referencing across the repo depends on both).
2. **Safety-critical rules stay fully explicit inline** — never reduced to a
   mere pointer. These are Hard Rules **1–9 and 12** (Mirror-DB-Only,
   Live-Org-Write-Confirmation, Credential-Non-Disclosure, Fingerprint Result
   Mapping, No Invented Field Names, Parent-Batch Sort, Migration Key
   Integrity, Field-Level Security Bundling, Email Deliverability Attestation,
   Live Migration Key Validation). Consistency rules (10, 11, 13, 14, 15) may
   be compressed but keep number + name + a pointer.
3. **Every CLI command / verb still appears** (name + invocation). The
   inventory stays *complete* even as descriptions shrink.
4. **No knowledge is deleted without landing somewhere.** Each Relocate is
   verified to exist in its destination doc before the inline block is
   removed.
5. **Behavior semantics are unchanged.** If a compression would alter what an
   agent does, it's too aggressive — stop.

## The process a run performs

1. **Baseline** — measure `CLAUDE.md` (lines / words / est-tokens, and per
   `##` section). Append a row to the size log below.
2. **Classify** every block per the four-class rubric.
3. **Relocate / Compress / Flag-Stale** — for each Relocate, confirm (or add)
   the content in its home doc, then replace the inline block with a one-line
   pointer.
4. **Invariants check** — run the five-point checklist above.
5. **Report** — before/after metrics (% reduction), a **move manifest**
   (every block → its destination), and the **stale-for-decision** list.
6. **Human review** — a person approves; land on a branch + PR (repo
   convention). The skill *proposes*; it never self-applies.

## Human-owned

Like the Human-Owned Mapping Rule (CLAUDE.md #11), an autonomous rewrite of
the operating manual is exactly the hard-to-reverse, judgment-heavy change
that must be **human-reviewed**. The executor produces a proposal + manifest;
a human reads the diff and approves. Always a branch + PR, never direct to
`main`. Before applying a trim, drop a git tag (e.g. `pre-context-trim`) as a
one-command restore point — git history, not a gitignored copy, is the archive.

## Size log

Append one row per run so drift is visible over time.

| Date | Trigger | Before (words / est-tokens) | After | Δ | Notes |
|---|---|---|---|---|---|
| 2026-08-01 | baseline (pre-skill) | 15,525 / ~20k | — | — | Canonical commands section is ~half the file (~800 lines); first trim target |

*(est-tokens ≈ words × 1.3, a rough guide, not exact.)*

## When to run

Not on a rigid schedule — on a signal:
- **Size trigger** — `CLAUDE.md` climbs past a comfortable budget (as a rough
  line, > ~10k words / ~13k tokens is worth a look).
- **After a burst of additions** — a session that added several rules (this is
  common; capture-then-compress is the healthy rhythm).
- **Periodic** — the "reset and rebuild from load-bearing rules" cadence
  (~6 months) that keeps stale rules from lingering.
