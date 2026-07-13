# Task validator

## Custom fields deploy on Activity, not Task
**Found:** 2026-07-11, D360_PLAYGROUND, adding `MigrationID__c` as Task's
migration key.
**What happens:** `sf project deploy start` against
`force-app/main/default/objects/Task/fields/MigrationID__c.field-meta.xml`
fails with `Entity Enumeration Or ID: bad value for restricted picklist
field: Task`.
**Why:** confirmed via Salesforce's own help docs — Task and Event are
both "Activity" underneath, and new custom fields are created at the
Activity level, then made available on Task and/or Event (chosen via page
layout at creation time in the UI; the Metadata API equivalent is simply
deploying under the `Activity` object folder). Setup's own field-creation
UI doesn't even offer a "New" button directly on Task/Event for this
reason.
**What to do:** put the field's `.field-meta.xml` under
`force-app/main/default/objects/Activity/fields/`, not
`.../objects/Task/fields/`. The deployed field then shows up correctly on
`describe('Task')` (and Event) as `Activity.MigrationID__c` in the
deployed-source listing, `Task.MigrationID__c` when queried/used
normally. Permission set `fieldPermissions` entries still reference it as
`Task.MigrationID__c` (or `Event.MigrationID__c`) — the `Activity` object
name only matters for the field's own deployment location.

## WhatId is genuinely polymorphic
**Found:** 2026-07-11, confirmed live via `describe('Task')`.
**What happens:** `WhatId` accepts ~90 different target object types
(Account, Opportunity, Case, Contract, Order, and many more) — a single
Task's `WhatId` is one specific type per row, never resolvable generically.
**Why:** this is a real Salesforce polymorphic lookup, not a data
mapping ambiguity — the platform itself defines it this way.
**What to do:** for mock/related-data generation, `generate-related-mock-data`
now detects a field with more than one in-scope target and splits the
child object into one cohort per target parent, tagging each row with a
literal `_ParentType` discriminator column (see `snowfakery_data.py`'s
`build_recipe()` polymorphic handling). The transform then resolves the
real field with a `CASE m._ParentType WHEN 'Account' THEN ... WHEN
'Opportunity' THEN ... END` per row — see `sql/transformations/040_task_load.sql`
for the concrete pattern. `WhoId` (Contact/Lead) is polymorphic in the
same sense but wasn't exercised beyond a single in-scope target (Contact)
in this project.
**Executable check:** none yet (build-time transform pattern, not a
runtime QA check) — worth revisiting if a future project needs to verify
every polymorphic-field row actually resolved (e.g.
`SELECT COUNT(*) FROM <LoadTable> WHERE WhatId IS NULL`).

**Also relevant to discovery, not just mock/transform generation:** `Task`
is the object that first exposed a real bug in
`discovery_checklist.py`'s (roadmap #60) own out-of-scope-dependency
check — its original design generated one "confirm X is in scope"
question per `referenceTo` target, which produced ~90 near-identical
lines for `WhatId` alone (drowning out every other, genuinely actionable
question for the object). Fixed to collapse any field with more than one
target into a single question naming the field and a truncated target
list, since a polymorphic field's real dependency question is "which of
these does the client's data actually use," not "confirm every possible
type is in scope." Also surfaced `OwnerId` as polymorphic
(`Group`/`User`) on `Task` — a generic, not Task-specific, Salesforce
pattern, so not written up as its own finding above.

## IsRecurrence / Recurrence* fields are one interdependent cluster
**Found:** 2026-07-11, D360_PLAYGROUND — first live Task insert failed
530/530 (100%).
**What happens:** independently-random mock values for `IsRecurrence` and
the `Recurrence*` fields (`RecurrenceStartDateOnly`, `RecurrenceEndDateOnly`,
`RecurrenceTimeZoneSidKey`, `RecurrenceType`, `RecurrenceInterval`,
`RecurrenceDayOfWeekMask`, `RecurrenceDayOfMonth`, `RecurrenceInstance`,
`RecurrenceMonthOfYear`, `RecurrenceRegeneratedType`) produce combinations
Salesforce actively rejects: `INVALID_FIELD_FOR_INSERT_UPDATE: You cannot
insert or update ActivityDate for a recurring task`, `Day of week must be
blank for type Recurs Monthly`, `FIELD_INTEGRITY_EXCEPTION: Choose a type
of date for repeating this task.`
**Why:** Salesforce cross-validates this whole cluster as one
interdependent unit (recurrence type determines which of the other
recurrence fields are legal/required/forbidden) — not a per-field
constraint any single field's own describe() metadata would reveal.
Safely mocking a *valid* recurrence pattern would need real recurrence-
rule-aware logic, genuinely out of scope for generic mock-data generation.
**What to do:** don't attempt to mock or load these fields independently.
`mock_data.py`/`snowfakery_data.py` now skip the whole cluster
automatically (`_is_interdependent_field()` in `mock_data.py`) — nothing
to do manually for a new project unless real recurring-task data
specifically needs to migrate, in which case build that logic
project-specifically rather than relying on generic mock generation.
**Executable check:** none — this is a build-time exclusion (don't select
these columns), not a checkable Load-table state.

## Subject is type `combobox`, not `picklist`
**Found:** 2026-07-11 — `Subject` was silently skipped by both
`mock_data.py` and `snowfakery_data.py` (neither had a case for the
`combobox` field type), leaving every mocked Task with no Subject at all.
**Why:** `combobox` is a real, distinct describe() type — a picklist that
also accepts free text — and both mock generators' type-mapping only had
cases for `picklist`, not `combobox`, even though `combobox` fields carry
the same real `picklistValues` a `picklist` does.
**What to do:** already fixed generically, not just for Task —
`_snowfakery_field()`/`_mockaroo_field()` now treat `combobox` the same as
`picklist` (pick from real `picklistValues`). Any other object with a
`combobox` field benefits automatically.

## TaskSubtype
**Found:** 2026-07-11 — present in `describe()`, createable, but not
included in this project's `040_task_load.sql` SELECT list.
**What to do:** not a gotcha, just an intentional scope decision for this
pass (wasn't needed to demonstrate the `WhatId` polymorphism this test was
built for) — add it if a future project's mapping actually calls for it.
