/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 9 of
   11.

   CORRECTED live (real finding, contradicts the earlier NPSP-to-NPC
   PoC's own validators/GiftCommitmentSchedule.md): that finding
   confirmed "Recurring-type GiftCommitment always auto-creates its own
   schedule" 6/6 on real NPSP-sourced data. This build's own live testing
   found the OPPOSITE for its 12 Recurring-type synthetic commitments --
   zero auto-created, checked from both directions (GiftCommitment.
   CurrentGiftCmtScheduleId and a direct GiftCommitmentSchedule query),
   confirmed stable over time (not an async-processing delay). The root
   platform cause is genuinely unclear (the Tooling API can't see
   managed-package-internal automation logic -- the same structural blind
   spot child_record_risk.py already exists to work around empirically,
   not by introspection) -- possibly a Bulk-API-vs-UI-insert-context
   difference, possibly a field-population difference this investigation
   didn't isolate. Rather than re-assume either "always auto-creates" or
   "never auto-creates" as a fixed rule, this script now checks what's
   ACTUALLY missing first (replicate dbo.GiftCommitmentSchedule for this
   build's own GiftCommitmentIds, above) and only explicitly inserts a
   schedule for a commitment that genuinely has none yet -- safe under
   either platform behavior, never collides with a real auto-created row.

   TransactionPeriod = 'Custom' for Custom-type commitments (matches
   ScheduleType 1:1, no source period to map). For a Recurring-type
   commitment that turned out to need an explicit schedule anyway,
   'Monthly' is used as the most common real-world recurring-gift
   cadence (this build has no real source period to derive from) --
   TransactionDay defaults to 1, since Monthly requires a real
   TransactionDay value (Appendix B validation, same pattern as the
   earlier PoC's own 170_npc_giftcommitmentschedule_from_rd_load.sql).

   UPDATE (2026-07-19, later, official docs + a real Nonprofit Cloud
   architect's confirmation): the check-first pattern above is still the
   right defensive design (never collides regardless of timing), but the
   "genuinely unclear" root cause note above is now mostly resolved --
   see 360's own header UPDATE and
   okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md. Real
   auto-creation requires either an explicit "Manage Recurring Gift
   Commitment Schedule" action call (this build never made one) or the
   nightly "NextGen commitment processing job" (a real batch, confirmed
   via GiftCommitment.LastNextGenCmtProcError's own field-help text) --
   this build's same-day check ran before that job could ever fire. The
   12 explicit inserts this script produced for "Recurring" commitments
   may collide with real schedules the nightly job creates later against
   the SAME commitments -- a live, unresolved risk on whatever org this
   was run against, not just a documentation gap. On the next rebuild,
   prefer calling the real Action (or waiting a real day) over this
   script's own explicit-insert fallback for genuinely "regular"
   (Monthly-cadence) commitments. */

DROP TABLE IF EXISTS [dbo].[GiftCommitmentSchedule_Load];

SELECT
    gc.LoadId AS LoadId,
    'SNOWFAKE-GCS-' + CAST(gc.LoadId AS VARCHAR(10)) AS MigrationID__c,
    gc.Id AS GiftCommitmentId,
    CASE WHEN gc.ScheduleType = 'Custom' THEN 'Custom' ELSE 'Monthly' END AS TransactionPeriod,
    CASE WHEN gc.ScheduleType = 'Custom' THEN NULL ELSE '1' END AS TransactionDay,
    1 AS TransactionInterval,
    gc.NextTransactionAmount AS TransactionAmount,
    gc.EffectiveStartDate AS StartDate,
    gc.ExpectedEndDate AS EndDate,
    'CreateTransactions' AS [Type]
INTO [dbo].[GiftCommitmentSchedule_Load]
FROM [dbo].[GiftCommitment_Load] gc
LEFT OUTER JOIN [dbo].[GiftCommitmentSchedule] existing ON existing.GiftCommitmentId = gc.Id
WHERE existing.Id IS NULL;
