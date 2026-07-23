/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 10
   of 11. Builds GiftTransaction_Load from dbo.GiftTransaction_Mock (40
   rows, generated together with GiftRefund/GiftSoftCredit below --
   DonorId/CampaignId/GiftCommitmentId/GiftCommitmentScheduleId all
   skipped by the engine since none of their targets were in the same
   generate-related-mock-data call).

   Name is required with no platform default -- see
   validators/GiftTransaction.md.

   ~60% of transactions are linked to a GiftCommitment (a real installment
   payment against a pledge), the rest are standalone one-off gifts --
   GiftCommitmentScheduleId is only ever set alongside GiftCommitmentId,
   joined from a fresh `replicate GiftCommitmentSchedule` covering all 15
   real schedules (never guessed; see validators/GiftCommitmentSchedule.md's
   corrected pattern -- every commitment in this build has exactly one
   real schedule now, so this join is unconditional once GiftCommitmentId
   is chosen, no Custom/Recurring branching needed the way the earlier
   PoC required). NOTE: joins against dbo.GiftCommitmentSchedule (the
   replicated snapshot), NOT dbo.GiftCommitmentSchedule_Load -- that Load
   table only ever reflects whichever subset 370's own check-first logic
   found missing on its last run (12 of 15 here), not the complete set;
   a mistake caught before this script's first live run. DonorId
   assigned across the combined 23-Account pool; CampaignId assigned for
   roughly half the standalone (non-commitment-linked) rows only -- a
   commitment-linked transaction's campaign association naturally flows
   through the commitment itself in real usage, not a second independent
   link.

   CORRECTED live: TransactionDueDate is required specifically for the
   commitment-linked rows -- INVALID_INPUT: "Complete this field" on all
   24 of them, none of the 16 standalone rows. Already present on the
   Mock table (Snowfakery generates it for every row) but not originally
   included in this SELECT -- carrying it through for every row fixes it,
   since a standalone gift having a due date too is harmless.

   CORRECTED again, live: a commitment-linked TransactionDueDate must
   fall on or after its GiftCommitmentSchedule's own StartDate --
   INVALID_INPUT on 9 of the 24 linked rows, since Snowfakery generates
   TransactionDueDate independently with no awareness of which schedule
   a row will end up linked to (that link itself is assigned later, in
   this same SQL). Clamped to the later of the two dates for linked rows
   only -- standalone rows are unaffected.

   CORRECTED again, live: a Custom-type GiftCommitmentSchedule only ever
   allows ONE linked GiftTransaction (AFNP's own "Single Transaction for
   Custom Schedule" validation -- already documented in
   validators/GiftTransaction.md from the earlier PoC, re-hit here since
   this build's round-robin commitment assignment didn't originally
   account for it, and a real Bulk API batch-level race let 3 rows
   momentarily succeed against the same Custom schedule before this fix).
   For a Custom-type schedule with more than one candidate transaction,
   only the first (by LoadId) keeps GiftCommitmentScheduleId -- the rest
   keep GiftCommitmentId (the parent commitment relationship still holds)
   but the schedule link is explicitly cleared, the same pattern the
   validator already documents for this exact rule.

   CORRECTED again, live: clearing GiftCommitmentScheduleId needs the
   literal '#N/A' sentinel, not SQL NULL -- a blank CSV cell on an
   upsert of an already-existing record is a no-op in Bulk API 2.0 (the
   same lesson already learned correcting AccountContactRelation.
   MigrationID__c), so the 2 real records that had already, incorrectly,
   grabbed the same Custom schedule during the race above kept failing
   revalidation on every subsequent upsert attempt even though this
   script's own SQL correctly computed NULL for them -- Salesforce never
   actually saw the field change. */

DROP TABLE IF EXISTS [dbo].[GiftTransaction_Load];

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
),
CommitmentPool AS (
    SELECT LoadId, Id, ROW_NUMBER() OVER (ORDER BY LoadId) AS CommitmentSeq, COUNT(*) OVER () AS CommitmentCount
    FROM [dbo].[GiftCommitment_Load]
),
Assigned AS (
    SELECT
        m._MockRowId,
        m.Name, m.Description, m.TransactionDate, m.TransactionDueDate, m.Status,
        m.PaymentMethod, m.OriginalAmount, m.GiftType, m.TaxReceiptStatus,
        ap.Id AS DonorId,
        CASE WHEN m._MockRowId % 5 >= 3 AND m._MockRowId % 2 = 0 THEN cp.Id ELSE NULL END AS CampaignId,
        CASE WHEN m._MockRowId % 5 < 3 THEN gc.Id ELSE NULL END AS GiftCommitmentId,
        CASE WHEN m._MockRowId % 5 < 3 THEN gcs.Id ELSE NULL END AS ScheduleCandidateId,
        gcs.TransactionPeriod,
        gcs.StartDate AS ScheduleStartDate,
        ROW_NUMBER() OVER (PARTITION BY gcs.Id ORDER BY m._MockRowId) AS SeqWithinSchedule
    FROM [dbo].[GiftTransaction_Mock] m
    JOIN AccountPool ap ON ap.AccountSeq = ((m._MockRowId - 1) % ap.AccountCount) + 1
    JOIN CampaignPool cp ON cp.CampaignSeq = ((m._MockRowId - 1) % cp.CampaignCount) + 1
    JOIN CommitmentPool gc ON gc.CommitmentSeq = ((m._MockRowId - 1) % gc.CommitmentCount) + 1
    LEFT OUTER JOIN [dbo].[GiftCommitmentSchedule] gcs ON gcs.GiftCommitmentId = gc.Id
)
SELECT
    _MockRowId AS LoadId,
    'SNOWFAKE-GT-' + CAST(_MockRowId AS VARCHAR(10)) AS MigrationID__c,
    'Snowfake-' + Name AS Name,
    DonorId,
    GiftCommitmentId,
    CASE
        WHEN TransactionPeriod = 'Custom' AND SeqWithinSchedule > 1 THEN '#N/A'
        ELSE ScheduleCandidateId
    END AS GiftCommitmentScheduleId,
    CampaignId,
    Description,
    TransactionDate,
    CASE
        WHEN ScheduleCandidateId IS NOT NULL AND ScheduleStartDate > TransactionDueDate THEN ScheduleStartDate
        ELSE TransactionDueDate
    END AS TransactionDueDate,
    Status,
    PaymentMethod,
    OriginalAmount,
    GiftType,
    TaxReceiptStatus
INTO [dbo].[GiftTransaction_Load]
FROM Assigned;
