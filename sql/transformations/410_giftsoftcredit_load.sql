/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 10
   of 11 -- companion to 390/400. Builds GiftSoftCredit_Load from
   dbo.GiftSoftCredit_Mock (23 rows, nested under GiftTransaction in the
   same generate-related-mock-data call -- _ParentMockRef resolves to
   GiftTransaction_Load.LoadId). RecipientId is a real Account reference
   (confirmed live via sample-reference-records, Phase 0 -- a soft credit
   recipient is an Account row, not a Contact directly, matching the
   Person Account model), SQL-assigned across the combined 23-Account
   pool -- ideally a DIFFERENT Account than the transaction's own DonorId
   (a soft credit typically recognizes someone OTHER than the actual
   donor, e.g. a matching employer or household member), enforced with a
   simple offset rather than an exclusion join.

   CORRECTED live: PartialAmount and PartialPercent are mutually
   exclusive -- FIELD_INTEGRITY_EXCEPTION on all 23/23 rows, since
   Snowfakery generated both independently with no awareness they're a
   real either/or pair (the same shape as the already-known Percent+
   Amount pairing requirement on GiftTransactionDesignation). Alternates
   deterministically by LoadId parity instead -- even rows keep
   PartialPercent, odd rows keep PartialAmount, the other nulled. */

DROP TABLE IF EXISTS [dbo].[GiftSoftCredit_Load];

WITH AccountPool AS (
    SELECT Id, ROW_NUMBER() OVER (ORDER BY Id) AS AccountSeq, COUNT(*) OVER () AS AccountCount
    FROM (
        SELECT Id FROM [dbo].[HouseholdAccount_Load]
        UNION ALL SELECT Id FROM [dbo].[OrganizationAccount_Load]
        UNION ALL SELECT Id FROM [dbo].[PersonAccount_Load]
    ) a
)
SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-GSC-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    gt.Id AS GiftTransactionId,
    ap.Id AS RecipientId,
    m.Role,
    CASE WHEN m._MockRowId % 2 = 1 THEN m.PartialAmount ELSE NULL END AS PartialAmount,
    CASE WHEN m._MockRowId % 2 = 0 THEN m.PartialPercent ELSE NULL END AS PartialPercent
INTO [dbo].[GiftSoftCredit_Load]
FROM [dbo].[GiftSoftCredit_Mock] m
JOIN [dbo].[GiftTransaction_Load] gt ON gt.LoadId = m._ParentMockRef
JOIN AccountPool ap ON ap.AccountSeq = ((m._MockRowId + 3 - 1) % ap.AccountCount) + 1;
