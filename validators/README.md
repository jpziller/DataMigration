# Validators library

A git-tracked knowledge base of things to check **before** building a
transform for a given Salesforce object — retrieved by object name rather
than re-derived from memory or rediscovered the hard way on a live org.
See CLAUDE.md's "Validators library" section for the full rationale;
this file is the practical how-to.

## Two kinds

- **`system/*.md`** — apply to every object, no exceptions. Each
  formalizes one of CLAUDE.md's own numbered Hard Rules that's also an
  executable check (today: rules 6, 7, 12, 15). The markdown explains
  *why*; the actual check is a real CLI command this framework already
  has — these files are a named, retrievable pointer to it, not a
  reimplementation.
- **`<Object>.md`** (e.g. `Task.md`) — findings specific to one object,
  discovered the hard way on a real project: a metadata deployment quirk,
  a polymorphic field, a business-rule field cluster that can't be
  independently mocked, anything Salesforce enforces that isn't obvious
  from `describe()` alone. Created the first time something object-
  specific is actually discovered — nothing exists preemptively for an
  object with no known gotchas yet.

## When to check one

Standard Workflow step 1 (CLAUDE.md, "Standard workflow: building a new
load-table script"): before building a transform for any object, check
`validators/<Object>.md` if it exists, and skim `validators/system/` if
this is your first pass through this project.

## When to write one

The moment you discover something object-specific the hard way — a
deploy that fails with a confusing error, a load that fails on a field
combination no describe() field alone would have predicted, a real
platform quirk. Write it down even if the immediate fix was "just don't
send that field" and the script already avoids it: a correctly-written
script hides the knowledge of *why* just as effectively as a wrong one
would have hidden the bug. This repo gets handed off, forked, and reused
for other projects before most objects' scripts are ever built for the
first time — the validator entry is what lets that first build skip the
rediscovery.

## Format

Each object validator is free-form markdown, but a consistent shape helps
skimming:

```markdown
# <Object> validator

## <Short name for the gotcha>
**Found:** <date, project/context if useful>
**What happens:** <the actual symptom -- error text, wrong result>
**Why:** <the real platform reason, confirmed not guessed>
**What to do:** <the concrete action -- exclude a field, use a different
  metadata path, resolve via a JOIN, whatever the actual fix is>
**Executable check (if any):** <a SQL snippet, or a CLI command
  reference, if this is automatable -- otherwise say so explicitly>
```

A markdown-only entry (no automated check yet) is a completely valid,
permanent state for something that's a judgment call rather than a
mechanical check — it doesn't have to "graduate" to executable to be
worth keeping. When it does make sense to automate, the same
tool-proposes-human-commits principle as `reference/batch_size_heuristics.json`
applies: propose the check, a human reviews and commits it deliberately.
