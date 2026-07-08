# Migration Run Book Template

The checked-in recipe for `migration_run_book.py`'s
`generate_migration_run_book()`. Structure is a direct mirror (structure
only -- column names/layout -- never content) of a real client's
in-production migration-status tracking tab. Edit this file to change
what every new migration project's first Migration Run Book tab starts
with — phase names and starter rows.

Each phase below is one `##` heading followed by exactly one Markdown
table, all sharing the **same column schema** — `migration_run_book.py`
validates every table's header against that shared schema and errors if
one drifts. Don't add a second table under one heading, and don't rename
or reorder a column here without also updating `_COLUMNS` in
`migration_run_book.py`.

A phase's name becomes a single banner row in the generated workbook (dark
navy fill, white text) — rename or add your own phases freely (a project
might add `Salesforce Config Changes`, `Source Download and Load`,
`MANUAL ALERT`, etc.), they're plain text, not a fixed enum. A heading
starting with "Load" gets its rows replaced by `analyze-load-order`'s
auto-fill when `--objects` is given; every other phase's rows are used as
written here.

`Status` is a real dropdown in the generated workbook (`Not Started`,
`N/A`, `In Process`, `Completed`, `Issue`) with live conditional-formatting
colors — set it here to whatever a starter row's actual state should be.
`Critical = Yes` rows get colored red — reserve it for steps that silently
break a load if missed (email deliverability, CPQ/automation toggles), not
routine steps. Leave `JIRA Ticket Link` blank in this template — never
invent a ticket reference (see `CLAUDE.md` hard rule 10).

## Pre-Migration Steps

| Stage | Object | Dependency | Status | Critical | Person Responsible | Begin Time | End Time | Execution Time | JIRA Ticket Link | Notes | Total Records | Success Records | Failed Records | Success Percent | Error Details |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Salesforce Config Changes | Confirm Email Deliverability setting (Setup > Email Administration > Deliverability) | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Salesforce Config Changes | Disable CPQ/Billing automation (or other managed-package automation) on target objects | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Salesforce Config Changes | Disable outbound automation that could email real contacts (workflow/Flow email alerts, approval processes) | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Pre Migration | Confirm target org/alias and auth mode for this pass | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Pre Migration | Run analyze-org-risk against in-scope objects | None | Not Started | No |  |  |  |  |  |  |  |  |  |  |  |
| Pre Migration | Take a backup/export of any target data being overwritten | None | Not Started | No |  |  |  |  |  |  |  |  |  |  |  |

## Source Download and Load Steps

| Stage | Object | Dependency | Status | Critical | Person Responsible | Begin Time | End Time | Execution Time | JIRA Ticket Link | Notes | Total Records | Success Records | Failed Records | Success Percent | Error Details |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Load Steps

| Stage | Object | Dependency | Status | Critical | Person Responsible | Begin Time | End Time | Execution Time | JIRA Ticket Link | Notes | Total Records | Success Records | Failed Records | Success Percent | Error Details |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Post-Migration Steps

| Stage | Object | Dependency | Status | Critical | Person Responsible | Begin Time | End Time | Execution Time | JIRA Ticket Link | Notes | Total Records | Success Records | Failed Records | Success Percent | Error Details |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Salesforce Config Changes | Re-enable Email Deliverability to its normal setting | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Salesforce Config Changes | Re-enable CPQ/Billing automation (or other managed-package automation) | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Salesforce Config Changes | Re-enable outbound automation disabled during Pre-Migration | None | Not Started | Yes |  |  |  |  |  |  |  |  |  |  |  |
| Post Migration | Spot-check row counts against source | None | Not Started | No |  |  |  |  |  |  |  |  |  |  |  |
| Post Migration | Notify stakeholders the load is complete | None | Not Started | No |  |  |  |  |  |  |  |  |  |  |  |
