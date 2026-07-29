---
type: Guide
title: NPSP source-shape fingerprint (first instance, ROADMAP #89)
description: A machine-readable fingerprint of what an NPSP org's data actually
  looks like -- the packaged objects/fields that make an org recognizable as
  NPSP, plus each migration-relevant object's shape and how it maps to the
  Nonprofit Cloud target. First real instance of the source-shape fingerprint
  idea, captured from a live NPSP-to-NPC run.
tags: [npsp, npc, afnp, source-fingerprint, data-shape, migration-pattern, npsp-to-npc]
timestamp: "2026-07-27"
---
# NPSP source-shape fingerprint

The machine-readable fingerprint is
[`source-fingerprint-npsp.json`](source-fingerprint-npsp.json) (describe-and-link
per OKF -- the JSON is the data, this note is the explanation). It is the
**first concrete instance of ROADMAP #89** (Known Source-Shape Fingerprints),
captured from the real NPSP→NPC v2 migration run's own source data. No registry
tooling exists yet -- this is the real example to generalize the tooling from
later, the same "prove on one real case first" discipline as the target-side
data-shape work (#83).

## What it captures

- **A recognition signature** -- the packaged objects (`npe03__Recurring_Donation__c`,
  `npe01__OppPayment__c`, `npsp__Allocation__c`, `npsp__General_Accounting_Unit__c`)
  and namespaces (`npsp__`/`npe01__`/`npe03__`/`npo02__`) that let you recognize
  an org as NPSP from its shape alone, plus the household signal
  (`npe01__SYSTEM_AccountType__c = 'Household Account'`) and the
  mixed-org caveat (NPSP dev orgs commonly also hold standard demo Accounts --
  scope to households).
- **Per migration-relevant object** -- namespace, the fields that actually
  matter for migration, and the *shape* observed on real data (e.g. NPSP
  Payments are a MIXED paid/unpaid population, where unpaid installments carry
  only a scheduled date -- the reality behind `validators/GiftTransaction.md`'s
  paid/unpaid finding).
- **How it maps to the target** -- the key `NPSP object → AFNP object`
  mappings and the kit that implements them.

## How to use it

Before an NPSP→NPC engagement, read the signature to confirm you're looking at
an NPSP org and to spot which records are actually in scope; read the per-object
shape to know what the transforms must handle (paid/unpaid, routing, auto-created
schedules) *before* hitting it live. Discoverable via
`gather-okf --objects <Object>`. Population counts are from one run's scoped
subset (shape, not universal magnitudes); the recognition signature is portable.
