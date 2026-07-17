# Validators bundle update log

## 2026-07-17
* **New**: [GiftCommitment validator](GiftCommitment.md),
  [GiftTransaction validator](GiftTransaction.md),
  [PartyRelationshipGroup validator](PartyRelationshipGroup.md) --
  Nonprofit Cloud/AFNP's fundraising object family, discovered during a
  live NPSP-to-NPC migration proof-of-concept. Same root finding hit
  three separate objects independently: `Name` reports
  `createable: False` in `describe()` but is genuinely required and
  acceptable to send on insert -- confirmed a real describe()/API
  mismatch, not a fluke, once it recurred a third time.

## 2026-07-15
* **Update**: Adopted the Open Knowledge Format (OKF v0.1) — frontmatter
  added to every concept file (no body content changed), this log and
  [index.md](index.md) created. See ROADMAP.md #72.

## 2026-07-13
* **Update**: [Task validator](Task.md) — added the
  discovery-checklist polymorphic-collapse note (a Task WhatId finding
  that surfaced a real bug in `discovery_checklist.py`'s
  out-of-scope-dependency check).

## 2026-07-11
* **Initialization**: Created the bundle — [README.md](README.md),
  [Task validator](Task.md), and the four system validators formalizing
  Hard Rules 6, 7, 12, and 15.
