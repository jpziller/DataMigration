---
type: Guide
title: Validators library -- how-to
description: The practical convention guide for this bundle -- the two
  kinds of validator (system vs object), when to check one, when to write
  one, and the format a new entry should follow.
tags: [guide, validators]
timestamp: "2026-07-11"
---
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

### Frontmatter (OKF)

This library is an Open Knowledge Format (OKF) v0.1 bundle (see
ROADMAP.md #72) — every non-reserved `.md` file here starts with a YAML
frontmatter block. `type` is the one required field
(`SystemValidator`, `ObjectValidator`, or `Guide` for this file);
`title`, `description`, `tags` (lowercase-kebab list), and `timestamp`
(quoted `"YYYY-MM-DD"`, the date the knowledge last changed) are
recommended. `resource:` is deliberately omitted across this bundle —
a validator is abstract knowledge, and its executable check already
lives in the body. `index.md` and `log.md` are OKF reserved filenames
(directory listing / change history) and live at the `validators/` root
only — never inside `system/`, where they'd be mistaken for validators.
When adding a new validator, add a matching entry to `index.md` and a
dated line to `log.md`.

### Body

Each object validator is free-form markdown, but a consistent shape helps
skimming:

```markdown
---
type: ObjectValidator
title: <Object> validator
description: <one-sentence summary of the findings>
tags: [object-validator, <object-name>]
timestamp: "<YYYY-MM-DD>"
---
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
