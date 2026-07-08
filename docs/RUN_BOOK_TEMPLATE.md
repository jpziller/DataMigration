# Migration Run Book Template

The checked-in recipe for `run_book.py`'s `generate_run_book()`. Edit this
file to change what every new migration project's first run-book tab starts
with — column headers, section names, and starter Pre-/Post-Migration items.

Each section below is one `##` heading followed by exactly one Markdown
table — `run_book.py` parses both directly. Don't add a second table under
one heading, and don't rename a column without also checking `run_book.py`'s
recipe/result column split for that section.

`Critical = Yes` rows get colored red in the generated workbook — reserve it
for steps that silently break a load if missed (email deliverability, CPQ/
automation toggles), not routine steps.

## Pre-Migration

| Item | Critical | Notes | Person Responsible | Start | End | Total Time |
|---|---|---|---|---|---|---|
| Confirm Email Deliverability setting (Setup > Email Administration > Deliverability) | Yes | | | | | |
| Disable CPQ/Billing automation (or other managed-package automation) on target objects | Yes | | | | | |
| Disable outbound automation that could email real contacts (workflow/Flow email alerts, approval processes) | Yes | | | | | |
| Confirm target org/alias and auth mode for this pass | Yes | | | | | |
| Run analyze-org-risk against in-scope objects | No | | | | | |
| Take a backup/export of any target data being overwritten | No | | | | | |

## Script / Transformations

| Script # / Name | Dependency | Person Responsible | Start | End | Row Count | Rows Loaded | % Loaded | Errors / Issues |
|---|---|---|---|---|---|---|---|---|

## Post-Migration

| Item | Critical | Notes | Person Responsible | Start | End | Total Time |
|---|---|---|---|---|---|---|
| Re-enable Email Deliverability to its normal setting | Yes | | | | | |
| Re-enable CPQ/Billing automation (or other managed-package automation) | Yes | | | | | |
| Re-enable outbound automation disabled during Pre-Migration | Yes | | | | | |
| Spot-check row counts against source | No | | | | | |
| Notify stakeholders the load is complete | No | | | | | |
