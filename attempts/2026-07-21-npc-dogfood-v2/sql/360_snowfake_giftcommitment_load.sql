/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 8 of
   11. Builds GiftCommitment_Load from dbo.GiftCommitment_Mock (15
   standalone rows -- DonorId/CampaignId/CurrentGiftCmtScheduleId all
   skipped by the engine since their targets weren't in the same
   generate-related-mock-data call).

   Name is required with no platform default -- see
   validators/GiftCommitment.md.

   ScheduleType is deliberately NOT taken from the Mock table's own
   random picklist value -- set here in SQL instead, ~70/30
   Recurring/Custom by MockRowId modulo, because it drives the real
   GiftCommitmentSchedule auto-creation rule downstream (370/380): a
   Recurring commitment gets its schedule auto-created by the platform
   the moment this row is inserted; a Custom one needs an explicit
   schedule row built separately. CurrentGiftCmtScheduleId is left unset
   -- the platform manages this field itself once a schedule exists (the
   real circular-reference field between GiftCommitment and
   GiftCommitmentSchedule, confirmed live via describe() on both objects
   -- this is why GiftCommitmentSchedule can never be generated together
   with GiftCommitment through build_recipe(), which would raise on
   unresolved circular dependencies).

   DonorId assigned across the combined 23-Account pool; CampaignId
   assigned against Campaign_Load for roughly half the rows (a real gift
   commitment is often, not always, tied to a campaign). EffectiveStartDate/
   ExpectedEndDate get the same out-of-order swap-safety as Campaign's
   StartDate/EndDate (330) -- Snowfakery generates each date field
   independently, with no cross-field awareness.

   CORRECTED live (real finding, not anticipated in the plan):
   RecurrenceType auto-defaults to 'OpenEnded' on a Recurring-type
   commitment when left unsent (confirmed live, defaultedOnCreate=True)
   -- but the auto-creation of GiftCommitmentSchedule did NOT fire for
   any of this build's first 12 Recurring-type inserts, contradicting
   validators/GiftCommitmentSchedule.md's earlier finding. Root cause,
   found by comparing against the one real, working reference example in
   this org: 'OpenEnded' recurrence semantically means "no end date," but
   this script was still sending a real ExpectedEndDate on every Recurring
   row -- the real working example has ExpectedEndDate genuinely blank.
   Confirmed live that updating an already-inserted commitment's
   ExpectedEndDate to null does NOT retroactively trigger the schedule
   (the automation is insert-time only) -- the 12 affected rows had to be
   deleted and reinserted with ExpectedEndDate correctly null from the
   start. ExpectedEndDate is now only ever sent for Custom-type rows,
   where it's meaningful (a Custom schedule needs a real end). See
   validators/GiftCommitmentSchedule.md for the corrected write-up.

   UPDATE (2026-07-19, later, official docs + a real Nonprofit Cloud
   architect's confirmation): the auto-creation IS real for a "regular"
   recurring type (architect's own words, "eg monthly") -- this build's
   own ScheduleType='Recurring' rows never actually got one because (a)
   the real trigger is either an explicit "Manage Recurring Gift
   Commitment Schedule" Invocable Action call (confirmed NOT fired by a
   plain Bulk API insert) or the nightly "NextGen commitment processing
   job" (a real Salesforce batch, confirmed via
   GiftCommitment.LastNextGenCmtProcError's own field-help text) -- and
   (b) this build checked same-day, before that nightly job could ever
   have run. "Irregular" commitments (pledges) don't get this, or only
   get the first commitment covered -- ScheduleType='Custom' here is
   believed to be that case, matching TransactionPeriod='Custom' on
   GiftCommitmentSchedule, though the exact field-level trigger for
   "regular" isn't independently confirmed by this project yet (only by
   the architect's own domain knowledge). See
   okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md's own
   2026-07-19 update for the full account and what to try differently
   next time (call the Action explicitly, or insert and wait a real day
   before checking -- never explicitly insert a competing schedule
   without checking live first). */

DROP TABLE IF EXISTS [dbo].[GiftCommitment_Load];

WITH AccountPool AS (
    SELECT Id, ROW_NUMBER() OVER (ORDER BY Id) AS AccountSeq, COUNT(*) OVER () AS AccountCount
    FROM (
        SELECT Id FROM [dbo].[HouseholdAccount_Load]
        UNION ALL SELECT Id FROM [dbo].[OrganizationAccount_Load]
        UNION ALL SELECT Id FROM [dbo].[PersonAccount_Load]
    ) a
),
CampaignPool AS (
    SELECT Id, ROW_NUMBER() OVER (ORDER BY Id) AS CampaignSeq, COUNT(*) OVER () AS CampaignCount
    FROM [dbo].[Campaign_Load]
)
SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-GC-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    'Snowfake-' + m.Name AS Name,
    ap.Id AS DonorId,
    CASE WHEN m._MockRowId % 2 = 0 THEN cp.Id ELSE NULL END AS CampaignId,
    m.Description,
    m.Status,
    m.FulfillmentType,
    m.FormalCommitmentType,
    m.GiftVehicleType,
    m.GiftVehicle,
    -- 'Recurring' = the "regular" type (architect-confirmed, e.g. Monthly
    -- cadence) that gets a real GiftCommitmentSchedule auto-created, via
    -- either the Manage Recurring Gift Commitment Schedule action or the
    -- nightly NextGen batch -- see this file's own header UPDATE note.
    -- 'Custom' = the "irregular"/pledge case, which doesn't (or only
    -- covers the first commitment) and needs an explicit schedule (370).
    CASE WHEN m._MockRowId % 10 < 7 THEN 'Recurring' ELSE 'Custom' END AS ScheduleType,
    CASE WHEN m.EffectiveStartDate <= m.ExpectedEndDate THEN m.EffectiveStartDate ELSE m.ExpectedEndDate END AS EffectiveStartDate,
    CASE
        WHEN m._MockRowId % 10 < 7 THEN NULL  -- Recurring/OpenEnded: no end date, see header
        WHEN m.EffectiveStartDate <= m.ExpectedEndDate THEN m.ExpectedEndDate
        ELSE m.EffectiveStartDate
    END AS ExpectedEndDate,
    m.ExpectedTotalCmtAmount,
    m.NextTransactionAmount,
    m.NextTransactionDate,
    m.IsAssetTransferExpected
INTO [dbo].[GiftCommitment_Load]
FROM [dbo].[GiftCommitment_Mock] m
JOIN AccountPool ap ON ap.AccountSeq = ((m._MockRowId - 1) % ap.AccountCount) + 1
JOIN CampaignPool cp ON cp.CampaignSeq = ((m._MockRowId - 1) % cp.CampaignCount) + 1;
