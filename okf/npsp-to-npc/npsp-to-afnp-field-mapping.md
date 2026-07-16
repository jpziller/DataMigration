---
type: MappingReference
title: NPSP to AFNP field mapping workbook
description: Structure, taxonomy, and a worked routing example from
  Salesforce's official NPSP-to-Agentforce-Nonprofit field-mapping
  workbook (33 sheets, one per NPSP object). Describes the workbook, does
  not reproduce its ~1,400 mapping rows.
resource: https://help.salesforce.com/s/articleView?id=sfdo.npc_implementation_migration_guides.htm&type=5
tags: [npsp, npc, afnp, mapping, field-mapping, appendix-a]
timestamp: "2026-07-16"
---
# NPSP to AFNP field mapping workbook

"Nonprofit Managed Package to AFNP Core Data Dictionary" -- the core
companion workbook [Appendix A](migration-guide.md) links to. 33 sheets:
a `Start Here` cover/legend sheet, a `General Migration Logic` sheet
(cross-cutting rules), and one sheet per NPSP object (Contact, Account,
Address, Relationship, Relationship Lookup, Affiliation, Opportunity,
Opportunity Contact Role, Recurring Donation, Recurring Donation
Schedule, Payment, Account Soft Credit, Partial Soft Credit, Campaign,
Campaign Member, Activity, General Accounting Unit, Allocation, Data
Import Batch, Event, Task, Lead, User, Recurring Donation Change Log,
Engagement Plan/Template/Task, Level, Household (legacy account model),
and two deprecated sheets -- Batch, Fund). Verified directly by opening
the workbook and inspecting every sheet, not summarized secondhand.

# Column structure and taxonomy

Every object sheet (except Opportunity, see below) shares one row-per-
field shape:

`Metadata Source | Source Object Label | Source Object API Name | Source
Field Label | Source Field API Name | Source Field Type | Type | Target
Object(s) | Target Object(s) API Name | Target Field(s) | Target
Field(s) API Name | Target Field Type | Notes`

`Type` is the workbook's own taxonomy for what kind of transformation
(if any) a field needs:

| Type | Meaning |
|---|---|
| `1:1` | Maps directly to one target field. |
| `1:many` | Source field needs to map to multiple destinations. |
| `many:1` | Multiple source fields collapse into one destination. |
| `New Data` | A new AFNP record is required with data not present in the source (e.g. a new relationship record vs. a simple lookup). |
| `Disregard` | Should not or cannot be migrated (generally irrelevant -- system fields, formula fields, NPSP customizable rollups). |
| `Omitted` | Has potential value in AFNP but requires customer-specific choice -- no clean analogue, or touches a still-evolving part of the data model. |

General rules stated on the `General Migration Logic` sheet: no
automations are assumed to fire on insert/upsert; formula fields,
customizable rollups, and system fields are never mapped (system dates
are preserved as text on historical records only); Created/Last
Modified Date are carried across from the source on every object; a
Household account's Party Relationship Group looks up to that account's
original NPSP Id.

# Worked example: Opportunity's three-way routing

`Opportunity` is structurally different from every other sheet -- an
extra header row splits **three parallel target blocks** side by side
(Gift Transaction / Gift Commitment / Opportunity) instead of one. The
routing rule, from the sheet's own Notes column:

- Zero or one Payment associated → **Gift Transaction**
- More than one Payment associated → **Gift Commitment**
- Open stage (`IsClosed = false`) → stays an **Opportunity**

See [opportunity-routing.md](opportunity-routing.md) for the fuller
conceptual picture. `Recurring Donation` similarly splits across **Gift
Commitment** and **Gift Commitment Schedule**, and `Payment` splits
across **Payment Instrument**, **Gift Transaction**, and **Gift
Refund** (sequencing note on that sheet: load Gift Transactions before
Gift Refunds, since Gift Refund is a child of Gift Transaction).

# Aggregate shape (this pass, all object sheets, excluding Opportunity's
non-standard layout which isn't machine-tallied the same way)

492 `1:1`, 388 `Disregard`, 163 `Omitted`/`Omit`, 10 `New Data`, 9
`1:many`, 5 `many:1` -- 1,067 rows total. `User` (168 rows, all `1:1`)
and `Task`/`Event` (23 and 48 rows, nearly all `1:1`) are the most
directly portable sheets; `Contact` (143 rows, 88 `Disregard`) and
`Account` (57 rows, 42 `Disregard`) carry the most legacy/system-field
noise to filter out.

# Citations

1. Migration guide, Appendix A - Mapping Spreadsheets (see
   [migration-guide.md](migration-guide.md))
2. [Mapping spreadsheets index](mapping-spreadsheets.md)
