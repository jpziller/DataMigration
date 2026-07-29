/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md). Full Opportunity
   three-way routing rationale (okf/npsp-to-npc/opportunity-routing.md): an
   Opportunity with MORE THAN ONE real Payment routes here (Gift
   Commitment). DonorId via npsp__Primary_Contact__c; Status='Closed';
   RecurrenceType='FixedLength'; ScheduleType='Custom' (190 must match). */

DROP TABLE IF EXISTS [dbo].[GiftCommitmentFromOpp_Load];

SELECT
    o.Id AS LoadId,
    o.Id AS MigrationID__c,
    o.Name,
    pa.Id AS DonorId,
    'Closed' AS [Status],
    'FixedLength' AS RecurrenceType,
    'Custom' AS ScheduleType,
    o.CloseDate AS EffectiveStartDate,
    o.Amount AS ExpectedTotalCmtAmount
INTO [dbo].[GiftCommitmentFromOpp_Load]
FROM [dbo].[Opportunity] o
JOIN [dbo].[Account] pa ON pa.MigrationID__c = o.npsp__Primary_Contact__c
JOIN (
    SELECT npe01__Opportunity__c AS OppId, COUNT(*) AS PaymentCount
    FROM [dbo].[npe01__OppPayment__c]
    GROUP BY npe01__Opportunity__c
) pc ON pc.OppId = o.Id AND pc.PaymentCount > 1;
