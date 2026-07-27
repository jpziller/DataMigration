---
type: MigrationPattern
title: Date-range fields (start/end) must be ordered -- and mock generation won't do it for you
description: A cross-cloud pattern. Many objects have a start/end date pair
  (a schedule's StartDate/EndDate, EffectiveStartDate/ExpectedEndDate, a
  campaign's or contract's or promotion's dates). The platform expects
  end >= start, and often that a related date falls within the window --
  but synthetic-data generators (Snowfakery/Mockaroo) produce each date
  INDEPENDENTLY, so a mock start/end pair can come out backwards and break
  the load. Two rules -- same-object pairs get ordered in generation
  (end generated after start via a field reference); a cross-object
  constraint (a date that must fall inside a DIFFERENT object's window) is
  a transform-layer clamp, because the generator can't see the other
  object. This repo enforces both generically.
tags: [salesforce-platform, cross-cloud, date-range, start-end, mock-data, snowfakery, data-quality, migration-pattern, campaign, contract, schedule]
timestamp: "2026-07-27"
---
# Date-range fields (start/end) must be ordered

## The pattern

An object has a **start/end date pair** and the platform requires the end
to be on or after the start (and sometimes that some third date fall
*within* the window). Examples across clouds -- a Nonprofit Cloud
`GiftCommitmentSchedule`'s `StartDate`/`EndDate` (derived from
`EffectiveStartDate`/`ExpectedEndDate`), a `Campaign`'s
`StartDate`/`EndDate`, a contract's or a Consumer-Goods promotion's dates.

**Why mock data breaks it**: a synthetic-data generator maps each date
field to an *independent* range (this repo's Snowfakery generator used
`DateBetween(-3y, +1y)` for every date; Mockaroo behaves the same way).
Independent draws mean a generated `end` can land *before* the generated
`start` -- a backwards window. On load that surfaces as an
`INVALID_INPUT`/validation failure, or a downstream date that can't be
reconciled to the (now-backwards) window.

This is **generic** -- it's not about one object. Any object with a
start/end date pair is exposed, on any cloud.

## Two rules

**1. Same-object start/end pairs -- order them in generation.** The `end`
should be generated *after* the `start`, so `end >= start` on every row by
construction. Snowfakery expresses this with a field reference:

```yaml
StartDate:
  date_between: { start_date: -3y, end_date: -1M }
EndDate:
  date_between: { start_date: ${{StartDate}}, end_date: +2y }
```

Ordering has to happen at generation time because the value is per-row --
you can't fix it with a static range. (The referenced field must be emitted
*first*; Snowfakery references resolve backward only.)

**2. A cross-object date constraint is a transform-layer clamp.** When a
date must fall inside a *different* object's window -- e.g. a
`GiftTransaction.TransactionDueDate` must be within its assigned
`GiftCommitmentSchedule`'s `StartDate`..`EndDate`, and the assignment
happens in SQL, not in the recipe -- the generator can't know the window.
Clamp it in the transform (two-sided: to Start if below, to End if above),
and make sure the window itself is valid first (rule 1). See
`sql/transformations/390`/`370` for the Nonprofit Cloud instance.

## How this repo enforces it (so you don't per-object)

- **Generation (generic)**: `snowfakery_data.py` detects same-object
  start/end date pairs by name and generates the end after the start via a
  `date_between` field reference -- for *every* object, automatically
  (ROADMAP #88). Best-effort heuristic (start/begin/effective/... vs
  end/finish/expiration/maturity/...); `date`-typed pairs only (Faker
  rejects a substituted datetime, so datetime ranges rely on the transform
  layer). Ambiguous pairings (several starts, no shared root) are left
  independent and surfaced, not silently guessed.
- **Visibility**: `build-data-shape-profile <Object>` lists the object's
  `date_range_pairs`, so the risk is visible before you build a transform
  (`show-data-shape`), even for the cases the generator's heuristic can't
  pair.
- **Safety net (per-object, where it matters)**: a SQL guard in the
  transform can force a forward window regardless of what the data
  contains (Nonprofit Cloud: `370`'s
  `CASE WHEN ExpectedEndDate >= EffectiveStartDate THEN ... ELSE DATEADD(...)`).

## How to look for it on a new cloud

Run `build-data-shape-profile` for the object and read its
`date_range_pairs`; if a pair is listed, confirm the generator ordered it
(or order it in the recipe), and check whether any *other* field must fall
inside that window (a cross-object clamp). If the profile lists date fields
that look like a start/end pair but the heuristic didn't pair them
(different roots, e.g. `ActiveFrom`/`DeactivateBy`), order them by hand in
the recipe -- the heuristic is deliberately conservative.

# Citations

1. Found + generalized live 2026-07-27, from a Nonprofit Cloud instance
   (a backwards `GiftCommitmentSchedule` window causing the reload's
   `TransactionDueDate` failure, ROADMAP #85/#87) into the generic
   generation-time fix (ROADMAP #88).
