# Data-shape profiles

Structured, machine-readable per-object **data-shape profiles** (ROADMAP
#83) — `build-data-shape-profile <Object>` writes `<Object>.json` here.

`describe()` gives you an object's *structure*; a profile adds the
*behavior* the framework has learned about it, in one place a tool can
reason over:

- **structure** — key/required fields and parent lookups, from live `describe()`.
- **automation** — active validation rules / triggers / flows / workflow
  rules / approval processes, from `analyze-org-risk` (`ObjectAutomationRisk`).
- **auto_generated_children** — child objects the platform creates on its
  own (e.g. Nonprofit Cloud's GiftCommitment → GiftCommitmentSchedule /
  GiftTransaction), from `child_record_risk.py`'s empirical detection —
  the Tooling-API-invisible automation a metadata read misses.
- **field_population** — real populated % / distinct counts, from
  `profile-salesforce` (`FieldProfile`).

Consult a profile before building a transform (`show-data-shape <Object>`),
alongside `gather-okf` and `check-validators`. The richer the upstream
signals — run `analyze-org-risk` and `profile-salesforce` first — the
fuller the profile; missing signals are reported as `scanned: false` /
`profiled: false`, never a misleading clean zero.

## Committed or not

The generated `*.json` files are **org-derived** (a specific org's
automation and population), so they're gitignored by default — the same
"commit deliberately" convention as `metadata/` and `mapping/`. Commit a
profile if you want a versioned reference for a cloud/object; otherwise
it's a regenerable, per-project artifact. (Generalizing a profile into
cloud-level reusable knowledge — stripping org-specifics — is a future
refinement noted in ROADMAP #83.)
