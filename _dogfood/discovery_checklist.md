# Discovery Checklist

## Account

*0 active validation rule(s), 0 Apex trigger(s), 0 active record-triggered flow(s), 0 legacy workflow rule(s), 0 approval process(es).*

- Account depends on User (via OwnerId), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Account depends on User (via CreatedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Account depends on User (via LastModifiedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Account depends on DandBCompany (via DandbCompanyId), which isn't in this candidate list yet -- confirm DandBCompany is in scope too, or that target DandBCompany records already exist in the org for this migration to reference.
- Account depends on OperatingHours (via OperatingHoursId), which isn't in this candidate list yet -- confirm OperatingHours is in scope too, or that target OperatingHours records already exist in the org for this migration to reference.

## Contact

*0 active validation rule(s), 0 Apex trigger(s), 0 active record-triggered flow(s), 0 legacy workflow rule(s), 0 approval process(es).*

- Contact depends on User (via OwnerId), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Contact depends on User (via CreatedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Contact depends on User (via LastModifiedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Contact depends on Individual (via IndividualId), which isn't in this candidate list yet -- confirm Individual is in scope too, or that target Individual records already exist in the org for this migration to reference.

## Opportunity

*0 active validation rule(s), 0 Apex trigger(s), 0 active record-triggered flow(s), 0 legacy workflow rule(s), 0 approval process(es).*

- Opportunity depends on Pricebook2 (via Pricebook2Id), which isn't in this candidate list yet -- confirm Pricebook2 is in scope too, or that target Pricebook2 records already exist in the org for this migration to reference.
- Opportunity depends on User (via OwnerId), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Opportunity depends on User (via CreatedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Opportunity depends on User (via LastModifiedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Opportunity depends on OpportunityHistory (via LastAmountChangedHistoryId), which isn't in this candidate list yet -- confirm OpportunityHistory is in scope too, or that target OpportunityHistory records already exist in the org for this migration to reference.
- Opportunity depends on OpportunityHistory (via LastCloseDateChangedHistoryId), which isn't in this candidate list yet -- confirm OpportunityHistory is in scope too, or that target OpportunityHistory records already exist in the org for this migration to reference.

## Task

*0 active validation rule(s), 0 Apex trigger(s), 0 active record-triggered flow(s), 0 legacy workflow rule(s), 0 approval process(es).*

- Task.WhoId is polymorphic and can reference: Lead -- confirm with the client which of these the real data actually uses before assuming any are in scope (one row points at exactly one target, never all).
- Task.WhatId is polymorphic and can reference: ApprovalSubmission, ApprovalSubmissionDetail, ApprovalWorkItem, ApptBundleAggrDurDnscale, ApptBundleAggrPolicy, and 91 more -- confirm with the client which of these the real data actually uses before assuming any are in scope (one row points at exactly one target, never all).
- Task.OwnerId is polymorphic and can reference: Group, User -- confirm with the client which of these the real data actually uses before assuming any are in scope (one row points at exactly one target, never all).
- Task depends on User (via CreatedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
- Task depends on User (via LastModifiedById), which isn't in this candidate list yet -- confirm User is in scope too, or that target User records already exist in the org for this migration to reference.
