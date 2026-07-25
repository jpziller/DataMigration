---
type: Reference
title: External Snowfakery recipe sources -- catalog and per-cloud coverage
description: A catalog of the vetted, shareable synthetic-data recipe
  libraries that already exist in the Salesforce ecosystem (Salesforce.org
  community recipes, CumulusCI-bundled datasets, Snowfakery's own
  examples), what each covers, and the real coverage gaps -- so a
  migration checks for an upstream recipe before authoring one from
  scratch. Coverage is strong for Nonprofit/Education and generic core
  objects, thin-to-absent for Consumer Goods, Sales, Service, Health, and
  FSC. Crucial limit -- upstream recipes encode object structure and
  relationships, NOT the managed-package auto-creation/behavior layer this
  repo has to learn empirically (validators/, child_record_risk.py).
tags: [snowfakery, sample-data, synthetic-data, recipes, cumulusci, external-source, reference, nonprofit-cloud, consumer-goods-cloud, sales-cloud, service-cloud, education]
resource: https://github.com/SFDO-Community-Sprints/Snowfakery-Recipe-Templates
timestamp: "2026-07-25"
---
# External Snowfakery recipe sources -- catalog and per-cloud coverage

Before authoring a new cloud's synthetic-data recipe (`sample_data/`), or
building transforms against an unfamiliar target, **check here first**.
The Salesforce ecosystem already publishes vetted recipes for several
clouds; reusing one heads off issues an upstream author already solved,
and its object graph is a fast way to learn a target's real relationships
and cardinalities.

Researched live 2026-07-25 (see `# Citations`). Verify against the live
sources before relying on any specific detail -- these libraries evolve.

## The sources

| Source | `resource:` | What it covers | Notes |
|---|---|---|---|
| **SFDO-Community-Sprints / Snowfakery-Recipe-Templates** (the "Data Gen Toolkit") | https://github.com/SFDO-Community-Sprints/Snowfakery-Recipe-Templates | `snowfakery_samples/` folders: `npsp`, `EDA`, `OBF`, `PMM`, `OSC`, `salesforce` (core standard objects) | The best single shared library. Nonprofit/education/managed-package weighted. |
| **CumulusCI bundled datasets** | https://cumulusci.readthedocs.io/en/latest/data.html | NPSP and EDA ship `datasets/*.recipe.yml`; `cci org scratch npc` supports Nonprofit Cloud scratch orgs | Authoritative Salesforce.org recipes; CumulusCI is the standard loader (`snowfakery` + `cci`). |
| **SFDO-Tooling / Snowfakery** (the engine) | https://github.com/SFDO-Tooling/Snowfakery | Canonical recipe patterns + examples; `docs/` and `examples/` | The reference for recipe syntax and Salesforce integration. |
| **Community blogs / one-offs** | e.g. https://aaronwinters.com/data-generation-recipe-for-student-success-hub/ | Occasional industry recipes (e.g. Student Success Hub / EDU) | Useful gems; not a maintained library. |

## Per-cloud coverage (as of 2026-07-25)

| Cloud / product | Upstream recipe available? | Where |
|---|---|---|
| Nonprofit Success Pack (NPSP) | **Yes** | Community-Sprints `npsp/`, CumulusCI NPSP datasets |
| Education Data Architecture (EDA) / Education Cloud | **Yes** | Community-Sprints `EDA/`, CumulusCI EDA datasets |
| Nonprofit Cloud (AFNP) | **Partial** | `cci org scratch npc`; some community coverage. Fundraising surface is thin -- see below. |
| Managed packages (Outbound Funds, Program Management Module, Advisor Link) | **Yes** | Community-Sprints `OBF/`, `PMM/` |
| Generic core standard objects (Account/Contact/Opportunity/Case…) | **Yes** | Community-Sprints `salesforce/` |
| **Consumer Goods Cloud** (retail execution, TPM/TPO) | **No** (none found) | — build and own it here |
| **Sales Cloud** (beyond generic core) | **Thin** | generic core only |
| **Service Cloud** | **Thin** | generic core only |
| Health Cloud, Financial Services Cloud | **Referenced, not real recipe folders** | — treat as build-your-own |

## The crucial limit -- why this does NOT replace `validators/` + empirical learning

Upstream recipes encode a cloud's **structure**: objects, fields, and the
*intended* relationships/cardinalities. That's a genuine head start on
learning a target's data shape. But they generally **do not** encode the
**behavioral layer** this repo has had to learn the hard way:

* **Managed-package auto-created records** the Tooling API can't even see
  (Nonprofit Cloud's `GiftDefaultDesignation`, `GiftCommitmentSchedule`,
  `AccountContactRelation`). A community recipe won't tell you the
  platform will silently create these -- see
  [never-update-auto-created-records.md](../nonprofit-cloud/never-update-auto-created-records.md),
  [gift-commitment-schedule-auto-creation.md](../nonprofit-cloud/gift-commitment-schedule-auto-creation.md).
* **Real required-vs-defaulted-in-practice** fields, valid cross-object
  state combinations, and the actual population of fields in working data.

So the two are **complementary**: an upstream recipe accelerates the
*known-structure* half; this repo's `sample-reference-records`,
`child_record_risk.py`, `analyze-org-risk`, and `validators/<Object>.md`
capture the *auto-creation and real-behavior* half. Use both.

## How to use this (heading off issues)

1. **Before authoring a cloud's recipe or its transforms**, check the
   tables above (and run `gather-okf` for the objects in play, which
   surfaces this doc alongside any platform-behavior findings).
2. **If an upstream recipe exists** (nonprofit/education/core): start from
   it -- read its object graph to learn the relationships -- then layer
   this repo's own empirical findings (auto-created records, validations)
   on top. Cite it here; don't copy it wholesale.
3. **If it doesn't** (Consumer Goods Cloud, most industry work): that gap
   is the signal to build and own the recipe in `sample_data/` and record
   the target's real behavior in `validators/` + `okf/<cloud>/` as it's
   learned -- exactly what this repo already did for the NPC fundraising
   surface (see
   [fundraising-sample-reference-implementation.md](../nonprofit-cloud/fundraising-sample-reference-implementation.md)
   and `sample_data/README.md`).

## Licensing note

These are open-source Salesforce.org / community projects. Naming and
citing them is fine (and encouraged) under this repo's licensing rule --
they're tools/libraries this framework *builds on and integrates with*
(like Snowfakery, Mockaroo, SFDMU), not tools it replaces. Respect each
source's own license if adapting a recipe; prefer describe-and-link over
copying.

# Citations

1. Researched live 2026-07-25 via web search + fetching each source's
   repository/README:
   - SFDO-Community-Sprints/Snowfakery-Recipe-Templates (folder inventory:
     `npsp`, `EDA`, `OBF`, `PMM`, `OSC`, `salesforce`).
   - CumulusCI "Automate Data Operations" docs (datasets, `cci org scratch
     npc`).
   - SFDO-Tooling/Snowfakery (engine + examples).
   - Consumer Goods Cloud: confirmed **no** shared Snowfakery recipes found.
2. Coverage is a point-in-time snapshot; these libraries add clouds over
   time -- re-check the live sources rather than trusting this table
   indefinitely.
