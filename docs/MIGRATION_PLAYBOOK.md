# Salesforce Data Migration Playbook

Copyright (c) 2026 JP Ziller LLC. Released under the [MIT License](../LICENSE) —
free to use, modify, and redistribute (including commercially), provided the
copyright notice is retained.

This playbook captures the methodology behind `sf-migration`: the
non-tool-specific knowledge — what to do, in what order, and why — that
applies regardless of which framework moves the data. Where earlier notes on
this methodology existed, they were written around a now-retired commercial
tool; this version is realigned around this repo's own stack (SQL Server,
Python, the Salesforce Bulk API 2.0, and Claude Code as the operating layer)
and rebuilt from scratch rather than copied. Illustrative examples below use
a fictional client, "Data Goat," and its fictional system "Data Goat CRM."

---

## 1. Migration Concept

The goal of a Salesforce data migration is a process that is logical,
organized, and repeatable — not a one-off script written under deadline
pressure. That means:

- A standardized mapping document for every object (see §3 and
  `mapping_doc.py`).
- SQL Server as the integration hub — query, stage, transform, and load
  through it rather than moving data directly between systems.
- A small, reusable library of functions for common transformations
  (`sql/functions/`) instead of reinventing string-cleanup logic per object.
- A consistent script pattern for every object, so any developer can pick up
  someone else's transform and understand it immediately (see §4 and
  `CLAUDE.md`'s "Standard workflow").

A migration is not just a technical data movement — it's also a business
process review. The target org's configuration (validation rules, required
fields, automation) needs to be reviewed against the incoming data, and
someone with business context needs to sign off on how edge cases are
handled. Don't treat this as a purely technical exercise.

## 2. Toolchain Mapping

If you've worked with an older SQL-Server-to-Salesforce migration toolkit,
here's how those concepts map onto this framework:

| Older concept | This framework |
|---|---|
| Replicate a full object from Salesforce | `python cli.py replicate <Object>` |
| Incremental replicate (changed records only) | **Not built** — a known gap, see README's "Known limitations." Would filter on `SystemModstamp` and `MERGE` into the mirror. |
| Load a staging table into Salesforce, write Id/Error back | `python cli.py bulkops <Object> <op> <LoadTable>` |
| Ad hoc SOQL query, results to a table or the screen | `python cli.py query "<SOQL>"` |
| A dedicated "add a sort column" step before loading | `EXEC dbo.AddBulkLoadSortColumn` (CLAUDE.md hard rule 6) |
| A licensed COM object / linked server connecting SQL Server to Salesforce | The Salesforce Bulk API 2.0 REST endpoints, called directly via Python (`simple-salesforce`) — no licensed component, no linked server |

## 3. Data Mapping & Templates

There are two ways to plan what data moves where, and the biggest mistake in
any migration is attempting one without either:

**Data Mapping** — a full review of source and target fields, documenting
every field's disposition and any transformation logic. Best for large
migrations where accuracy matters more than speed. Requires access to a full
copy of source data and significant upfront effort. This is what
`generate-mapping-doc`/`check-mapping-balance` are built for (§9 below has
the exact structure).

**Data Template** — a predefined list of fields provided to whoever is
supplying data, used for smaller migrations (roughly 20 fields or fewer per
object). Faster, but fragile — the person filling in the template rarely
follows instructions exactly, and the file usually needs rework.

Tips that apply to either approach:

- Always capture the field's **API name**, not just its label — many
  fields share a label.
- Every source record needs a stable, unique identifier (an external ID) —
  and any reference to a *related* record should use that identifier too,
  never a mutable value like an Account's Name or a person's First/Last
  Name.
- When a field is a picklist, list the actual valid values and require the
  data provider to use them exactly — free text against a picklist is a
  guaranteed cleanup task later.
- Include an example row showing exactly the expected format, and remember
  to strip it out before loading.
- Mark clearly which fields are required vs. optional, and validate that
  every required column is actually complete before building a transform
  against the data.

## 4. Migration Script Pattern

Every script should follow the same shape, so any of these steps can be
adjusted without re-learning the whole script:

1. **Header** — what this script does, which object, what source it reads.
2. **Data replication** — pull whatever reference data the transform needs.
3. **Drop the load table** — start clean (`IF OBJECT_ID(...) DROP TABLE`).
4. **Build the load table** — the actual transformation logic. This is
   where nearly all real migration effort goes.
5. **Sort column** — `AddBulkLoadSortColumn`, standard on every object with
   a parent relationship. Not optional busywork — see §6.
6. **Dupe-check** — `CheckLoadTableDuplicateKeys` on the migration key,
   before ever touching `bulkops`.
7. **Load** — `bulkops`, with explicit org confirmation.

This is codified as the "Standard workflow" in `CLAUDE.md` — steps 5 and 6
are this framework's own additions on top of the base pattern, not
optional.

## 5. Data Extraction from Source Systems

Before any of the above can happen, source data has to land in SQL Server.

**Flat files** (Excel, CSV/TXT) are the most common transport, and the
riskiest. Excel silently mis-detects data types — dates and large numbers
can be coerced into scientific notation, and text that looks numeric can
lose leading zeros. Fix by explicitly setting column formats before
export/import, never trusting Excel's auto-detection for anything
migration-critical. CSVs are fragile at scale — commas embedded in text
fields shift columns rightward unless the file uses proper text
qualification (quoting), and even then, literal quote characters inside a
quoted field can still break naive parsers. Test with a sample before
committing to a delimiter/qualifier choice on a large file.

**Direct database access or a database backup** is the most reliable
method when available (rare for SaaS source systems) — it preserves data
types and structure exactly. SQL Server's Linked Server feature can reach
Oracle, MySQL, and other platforms directly via four-part naming
(`server.database.schema.table`), not just other SQL Server instances.

**JSON exports** are increasingly common from SaaS systems and need the
most hand-holding — validate structure with a JSON viewer before writing
any import logic, and use a large-file-capable editor rather than a
standard text editor for big exports. Import via `OPENROWSET`/`OPENJSON`:

```sql
DECLARE @JSON NVARCHAR(MAX);
SELECT @JSON = BulkColumn
FROM OPENROWSET(BULK 'C:\imports\accounts.json', SINGLE_NCLOB) AS j;

SELECT *
INTO DataGoat_Accounts_Raw
FROM OPENJSON(@JSON, '$.accounts')
WITH (
    id            NVARCHAR(25),
    company_name  NVARCHAR(255),
    created_at    VARCHAR(50),
    salesforce_id VARCHAR(18) '$.crm_fields.salesforce_id',
    region        NVARCHAR(50) '$.crm_fields.region'
);
```

## 6. Migration Process Considerations

### SQL database structure
Keep a clear separation between a **source** database (raw imported data,
never modified after load — it's your unadulterated reference) and a
**stage** database (everything transformed, including `*_Load` tables).
Never share databases across target orgs (dev/sandbox vs. production) — it
is very easy to cross-contaminate data between environments if you do. A
reasonable naming convention: `<System>_Source_<Env>` and
`<Project>_Stage_<Env>` (e.g. `DataGoat_Source_Dev`, `DataGoat_Stage_Prod`).

### Email deliverability
Disable Email Deliverability ("No access," not "System Email Only" — some
installed packages categorize their notifications as system email) before
any load that touches tens of thousands of records or more, and put
re-enabling it back on the checklist just as visibly. This is not
optional-if-annoying: an accidental mass email to real customers is the
kind of mistake that ends up in the news. If a stakeholder insists it's
unnecessary, document that decision explicitly rather than silently
skipping the step.

### Batch considerations
Salesforce allows 15,000 Bulk API batches per rolling 24-hour period across
the whole org — exceeding it halts *all* Bulk API batches until the window
resets. Each batch must finish within 10 minutes or it's paused and
retried. Batches can hold 1–10,000 records; unspecified batch size defaults
to 2,000 (internally chunked into 200-row sections by the platform).
Objects with heavy automation (CPQ, Billing, or anything with significant
Flow/trigger logic) often need much smaller batches — down to 50 records —
to let that logic keep up. The standard API has a separate 5,000
batches-per-user-per-day limit; a dedicated integration user can be a
legitimate way to get a second allotment if genuinely needed.

### Logic disablement
Default to leaving Flows, triggers, validation rules, and other automation
**on** during a load — that logic exists for a reason, and disabling it
means the migration has to reproduce whatever it was doing. Only disable
when there's a concrete reason: it's actively interfering with the load, or
it would fire an undesirable side effect (e.g. an external notification)
against migrated data.

Installed-package logic (Salesforce CPQ, Billing) usually has to be
disabled via that package's own "Configure" settings in Setup, not by
editing Apex directly. For your own custom triggers, build in a bypass
mechanism from day one rather than improvising one under deadline pressure
— see §8 for a clean pattern. And if disabling logic requires a metadata
deployment, remember it needs to pass Apex code-coverage validation on the
way back in — don't paint yourself into a corner where your org's
code-coverage requirements block you from re-enabling something you
disabled mid-migration.

### Row-lock considerations
`UNABLE_TO_LOCK_ROW` is the most common frustrating error in a bulk load.
It happens when two batches, processing concurrently, both need exclusive
access to the same parent record (via a lookup or master-detail field) at
the same time.

- **The fix this framework already builds in**: `AddBulkLoadSortColumn`
  groups every child of the same parent into a contiguous range so they
  land in the same submitted batch instead of being scattered across
  batches that run concurrently. A plain `ORDER BY` on the load-building
  query is *not* sufficient on its own — nothing guarantees a `SELECT INTO`
  preserves that order once the rows are actually submitted in batches.
  `ROW_NUMBER() OVER (ORDER BY <parent key>)`, materialized into a real
  `[Sort]` column, is what makes the grouping durable — and
  `AddBulkLoadSortColumn`'s companion verification (`MAX(Sort) - MIN(Sort)
  = COUNT(*) - 1` per parent) is what proves it actually took, rather than
  assuming it did.
- **Lookup fields** can be configured locking or non-locking, depending on
  the "what to do if the lookup record is deleted" setting — "clear the
  value" is non-locking, "don't allow deletion" is locking. Consider
  toggling this during a migration if it's safe to (and always restore it
  afterward).
- **Master-detail fields are always locking.** Converting one to a lookup
  and back is possible for custom relationships only, has real
  restrictions (no rollup-summary fields, every record must have a value to
  convert back), and is a last resort, not a first move.
- **Data skew** — a disproportionate number of children under one parent —
  causes row locks even with sorting, since a single parent's records still
  can't be split across concurrent batches safely. Split high-skew parents
  into their own load, run in serial mode, and load everything else
  normally.
- **Serial vs. parallel batches** — Bulk API loads up to 5 batches in
  parallel by default. Serial mode processes one at a time, which is much
  slower but sidesteps locking entirely for the worst cases.
- **Sharing rule recalculation** can be deferred org-wide (a
  Salesforce-support-enabled setting, not exposed by default) to avoid
  paying that cost on every single record during a load.
- **Reducing batch size** doesn't fix the underlying contention, but it
  reduces how many records a single lock failure takes down with it — and
  for objects where the interfering logic genuinely can't be disabled
  (CPQ/Billing automation is the classic case), a smaller batch size gives
  that logic time to keep up and can resolve the problem outright, not just
  shrink its blast radius.
- **Retry pattern for failures**: copy failed rows (`WHERE Error IS NOT
  NULL`) into a new table and resubmit, rather than re-running the whole
  load — `python cli.py bulkops-retry <LoadTable>` does exactly this.

### Object migration order
General principles, not just a fixed list:

- Anything else references Users, so migrate Users first if they're in
  scope at all (often they aren't — created manually instead).
- Accounts and Contacts next — nearly everything else references them,
  directly or indirectly.
- Leads are usually **not** migrated at all once converted — a converted
  Lead has no further function beyond historical reporting, and the
  Account/Contact/Opportunity it produced already carries the value
  forward.
- Products (with pricebook entries for every pricebook an Opportunity will
  reference) need to exist before Opportunities that reference them.
- Opportunity child objects (OpportunityLineItem, OpportunityContactRole,
  etc.) load after their parent Opportunity.
- Anything with a "primary" lookup that depends on a *sibling* object
  (e.g. an Opportunity's primary Quote) needs a post-load update pass once
  both sides exist — you can't populate it in the initial insert.
  Activities (Tasks/Events) come after most other objects, since they can
  reference almost anything. Chatter and Content come last, since they can
  reference *everything*, including each other.

This is exactly the problem `analyze-load-order` (roadmap #2, built) solves
programmatically from live describe() metadata, rather than requiring this
list to be maintained by hand.

## 7. SQL Best Practices

- **Alias the primary table `a`**, other joined tables with short but
  *meaningful* names (not `b`, `c`, `d` — a reader shouldn't have to trace
  the FROM clause to know what a table alias means).
- **Alias every selected field explicitly** with `AS`, even when the name
  wouldn't change — it prevents confusion and makes the target field
  obvious at a glance.
- **Bracket-escape field/table names** with special characters, spaces, or
  reserved words: `[Annual Revenue]`. When in doubt, bracket everything —
  it costs nothing and prevents an entire class of errors.
- **Prefer `LEFT OUTER JOIN`** unless you specifically intend to drop
  unmatched rows — an `INNER JOIN` silently discards data that doesn't
  match, and a `LEFT OUTER JOIN` at least surfaces the gap as a NULL you
  can investigate.
- **Capitalize SQL keywords** (`SELECT`, `FROM`, `CASE`, `WHEN`, `LEFT OUTER
  JOIN`) for readability.
- **`CASE` statements always need an `ELSE`.** Without one, rows that don't
  match any `WHEN` silently get excluded rather than passed through — often
  not what you want.
- **NULL is not blank.** A NULL means "no known value," not zero or empty
  string, and can't be compared directly. `ISNULL(field, '') = ''` is the
  standard pattern for treating NULL and blank identically in a comparison.

## 8. Trigger Bypass Pattern (Apex)

A generic, well-known pattern for letting a migration temporarily disable
specific trigger logic without touching the trigger's actual business
logic — implemented here from scratch, not copied from any particular
source, since it's a standard technique many Salesforce developers arrive
at independently:

1. Create a hierarchical Custom Setting (e.g. `Migration_Bypass__c`) with
   one checkbox field per thing you want to be able to bypass — one per
   trigger is a reasonable default granularity. Default every checkbox to
   `false` (i.e. "don't bypass, run normally").
2. In each trigger, check the setting as the very first line and return
   immediately if it says to bypass:

```apex
trigger OpportunityTrigger on Opportunity (before insert, before update, after insert, after update) {
    if (MigrationBypassService.isBypassed('OpportunityTrigger')) { return; }

    // normal trigger logic below
}
```

```apex
public with sharing class MigrationBypassService {
    public static Boolean isBypassed(String triggerName) {
        Migration_Bypass__c settings = Migration_Bypass__c.getInstance();
        switch on triggerName {
            when 'OpportunityTrigger' { return settings.Opportunity_Trigger__c; }
            when 'AccountTrigger'     { return settings.Account_Trigger__c; }
            when else                { return false; }
        }
    }
}
```

3. During a migration, set the relevant checkbox to `true` at the org-wide
   default (or scoped to just the migration user, for less blast radius),
   run the load, then set it back to `false` — and treat "turn it back off"
   as a checklist item with the same weight as "turn off email
   deliverability."

Requires normal Apex test coverage like any other class — a bypass switch
with no tests is exactly the kind of thing that blocks a future deployment
when someone discovers the coverage gap under time pressure.

## 9. Object-by-Object Notes

Reference structure for `generate-mapping-doc`'s Target block, and gotchas
worth knowing before you build a transform for each object. (Sample SQL
below is illustrative — a "Data Goat" stand-in shape, not any real client's
actual transform.)

### User
Required: `LastName`, `Alias` (8 chars max, must be unique org-wide —
`JSmith`, `JSmit1` for collisions), `Email`, `Username` (must be a
globally-unique email-shaped string across *all* Salesforce orgs, not just
yours — append an environment suffix in non-prod: `j.smith@datagoat.com.dev`),
`ProfileId`, `EmailEncodingKey`, `LanguageLocaleKey`, `LocaleSidKey`,
`TimeZoneSidKey`. In sandboxes, suffix emails with `.invalid` to guarantee
no real notification ever sends. If Users are migrated at all (often
they're created manually instead), they're the first object loaded, since
everything else can reference a User as an owner.

### Account / Contact
Required: `Name` (Account) or `LastName` (Contact), 255/80 characters
respectively. `BillingAddress`/`ShippingAddress` are compound fields in the
UI but must be populated field-by-field (`BillingStreet`, `BillingCity`,
etc.) — there's no single field to write to. If `OwnerId` is populated for
any record, populate it for all of them, or have a documented default
fallback for unassigned records. Every migrated record should carry a
migration external ID (marked External ID + Unique Case-Insensitive on the
target field) — this is the fingerprint uniqueness this framework's
`bulkops.py` already depends on for insert result-mapping. `RecordType`
often needs a lookup-style `CASE`/join against source category data — this
is a common enough pattern that it's worth building once and reusing.

### Lead
Required: `Company`, `LastName` — deliberately light, since Leads are often
low-quality by nature. Once a Lead converts, it typically has no further
purpose except historical reporting — most migrations only bring over
Leads where `IsConverted = false`, and many skip Leads entirely. Confirm
this with the business before assuming either way.

### Opportunity
No field is strictly required by the platform except `Name`, `CloseDate`,
`StageName` — but `Pricebook2Id` is functionally required in almost every
real org. Opportunities tend to accumulate more validation rules and
automation than almost any other object — budget real time for reviewing
what's active before loading. Editing a child (OpportunityLineItem) will
also re-trigger logic on the parent Opportunity.

### OpportunityLineItem / OpportunityContactRole
Required: `OpportunityId`, `PricebookEntryId`, `UnitPrice` (line item) or
`OpportunityId`/`ContactId`/`Role` (contact role). If source data lists
multiple related contacts in one delimited field (`jsmith, lsmall,
ghumphries`), `STRING_SPLIT` plus `ROW_NUMBER() OVER (PARTITION BY ...)` is
the standard way to explode it into rows and identify which one should be
marked "Primary."

### Contract / Order / OrderItem (and CPQ/Billing generally)
These load in a **draft-then-activate** pattern: insert as `Draft`, wire up
the relationships (Order↔Contract, OrderItem↔Subscription), then run a
follow-up update to flip status to `Activated`. Activation frequently
triggers external integrations (tax calculation, revenue recognition) that
can time out or error independently of the load itself — check the Apex
Jobs monitor in Setup, not just the load's own result table, and expect to
re-run the activation step more than once. A common reprocessing pattern
for stuck async jobs: reset the stuck status field to an error state, then
back to its original pending state, forcing the platform to re-attempt it
— this itself is just another `bulkops` update pass, sorted and batched
like any other load.

### Case / CaseComment
`CaseComment` has no External ID field available on the object at all —
if you need one for result tracking, prefix it onto the `CommentBody`
temporarily and strip it back off with a follow-up update once the load is
confirmed successful.

### Task / Event
Either `WhatId` (non-human relation) or `WhoId` (Contact/Lead) must be
populated. `StripHtml` (already in `sql/functions/utilities/`) is
frequently needed to clean a `Description` field pulled from a source
system's rich-text notes.

### EmailMessage
Only available on orgs using Email-to-Case or Enhanced Email. Creating an
`EmailMessage` record also auto-creates a corresponding Task, so plan for
that side effect rather than being surprised by extra Task rows.

### Note (legacy) / ContentNote (Enhanced Notes)
Legacy `Note` has no External ID field either — same prefix-then-strip
trick as CaseComment, applied to the Title field. Enhanced Notes
(`ContentNote`) are a completely different, richer object — Lightning-only,
loaded as a binary field (`VersionData`, `VARBINARY(MAX)`), requiring
invalid characters to be escaped first (`EscapeContentNote`, already in
`sql/functions/`). Loading is a two-step process: load the content itself,
then create a `ContentDocumentLink` to attach it to a parent record and
grant visibility.

### Content (Attachments / Files)
Also two steps: load `ContentVersion`, then `ContentDocumentLink`. Content
can come from a database `VARBINARY` column (typical for Salesforce-to-
Salesforce migrations) or from files on disk (typical migrating from a
non-Salesforce system) — for the latter, `VersionData` needs to reference
the file's path, not its bytes directly. Keep the `ContentVersion` load's
result table — the `ContentVersion` Id it contains is hard to retrieve
after the fact except by the record's owner, so don't assign an owner other
than the migration user until the whole process is confirmed complete. If
you don't need to preserve an existing ContentDocument association,
`FirstPublishLocationId` on the initial `ContentVersion` insert can skip
the second step entirely for brand-new files.

## 10. Reusable Functions

Every function this playbook's source material referenced is already
ported, cleaned, and MIT-licensed in `sql/functions/` — see that folder's
own README for the full list and provenance notes (including which two
functions were deliberately rebuilt from scratch rather than ported
verbatim, due to third-party copyright notices in the original source
files):

- `StripHtml`, `RemoveInvalidXmlChars`, `RemoveNonAscii`, `CleanNumber`,
  `EscapeContentNote` — `sql/functions/utilities/`
- `IsValidEmail` — `sql/functions/cleansing/`
- `ConvertTo18DigitId` — `sql/functions/salesforce/`
