# Migration Post-Mortem Template

A lightweight, repeatable retrospective to run after a migration project
reaches a real completion milestone — a full pass built, loaded, and
verified (not necessarily the final production cutover; a proof-of-concept
or a completed Dev/UAT pass both count). Unlike the Migration Run Book
(the operational record of *what happened*), a post-mortem is about
*what should change* — for this project's next pass, and for every future
project this framework touches.

**This is not a new knowledge-storage mechanism.** This framework already
has the right ones — `validators/<Object>.md` for object-level API
quirks, `okf/<subject-area>/` for target-platform or source→target
pattern knowledge, `ROADMAP.md` for process/tooling gaps. A post-mortem's
only job is to be the *prompt* that reliably produces new entries in
those existing homes, reviewed via the same PR process as everything else
in this repo — not a document that sits alone and gets forgotten. If a
finding below doesn't end up cross-referenced into one of those homes,
the post-mortem hasn't finished its job yet.

Copy this file to `postmortems/<YYYY-MM-DD>-<short-slug>.md` and fill it
in with real content — delete instructional text as you go, don't leave
placeholder brackets in the committed version.

## What went well

What worked without needing a fix — tooling, sequencing decisions,
design choices that held up under real live-org conditions. Worth naming
explicitly, not just the problems: a decision that turns out right is
evidence for keeping doing it that way, and easy to lose track of if only
failures get written down.

## What went poorly (and what was fixed)

Every real bug, gap, or surprise hit during this pass — one entry each,
plain and specific:

- **What happened** (the concrete symptom — an error message, a wrong
  count, a silent gap)
- **Root cause** (confirmed, not guessed — read the actual source/API
  behavior where possible)
- **Fix applied**, if any, and where (a code change, a config decision, a
  workaround)
- **Durable write-up**, if the finding is worth surviving past this one
  project — link to the `validators/`/`okf/`/`ROADMAP.md` entry it became

## Reusable artifacts produced

What this pass built that a *future* pass (same source→target pair, or a
close relative) shouldn't have to rebuild from scratch — transform
scripts, mapping docs, Run Book tabs, deployed metadata patterns. Name
where each one lives, and be explicit about the split CLAUDE.md's own
Standard Workflow assumes: what transfers directly as a *pattern* (routing
logic, field-mapping choices, RecordType/picklist decisions) vs. what
must be redone per client (real Ids, real volumes, that client's own
custom fields) — a reference-implementation doc alongside the source→
target OKF bundle is the right home for this split if the artifacts are
substantial enough to warrant one (see
`okf/npsp-to-npc/reference-implementation.md` for the shape).

## Target-platform-only knowledge extracted

Findings from this pass that are true of the *target* platform
regardless of migration source — these don't belong buried inside a
source-specific OKF bundle. If the target doesn't have its own
source-agnostic OKF subject area yet, this is the moment to create one
(see `okf/nonprofit-cloud/` for the precedent). If it already exists, add
to it rather than duplicating into the source-specific bundle.

## Process and tooling gaps found

Anything about *how this framework itself works* that this pass exposed
— a CLI command that assumed something that wasn't true, a naming
convention that silently collided, a retry budget that wasn't generous
enough for real-world latency. These go into `ROADMAP.md` with the full
account (root cause, fix applied or deferred, verification) — the same
convention every other bug write-up in that file already follows.

## Open questions for next time

Anything genuinely undecided or deferred — a design choice made under
time pressure that deserves real client/stakeholder input before being
treated as settled, a scope boundary drawn for this pass that a bigger
engagement would need to revisit, a tooling gap flagged but not built.
Don't resolve these here; just make sure they're written down where the
next person (or the next pass of this same project) will actually see
them.
