/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 10 of ~14. Opportunity's
   three-way routing (migration guide sec 7.6.3-7.6.5,
   okf/npsp-to-npc/opportunity-routing.md): an Opportunity with MORE THAN
   ONE real Payment routes here (Gift Commitment), not to Gift
   Transaction. Confirmed live against the real replicated npe01__OppPayment__c
   data (not the original seed Load table, which undercounted -- 3 of the
   6 Opportunities also carry an NPSP-auto-generated Payment never in
   that table): exactly 2 of our 6 seeded Opportunities qualify (2 and 3
   real Payments respectively). The other 4 (0-1 real Payment each) route
   to Gift Transaction directly instead (200).

   DonorId resolves through npsp__Primary_Contact__c (the real individual
   donor Contact NPSP tracks per-Opportunity), not the household AccountId
   -- consistent with 160's own RD->GiftCommitment DonorId choice (the
   actual person, not the household grouping).

   Status = 'Closed' (not 'Active') -- these Opportunities are already
   Closed Won with all installments paid, a completed multi-payment gift,
   not an ongoing forward-looking commitment like a Recurring Donation.
   RecurrenceType = 'FixedLength' (a known, finite number of installments,
   not open-ended). ScheduleType = 'Custom' -- these ad hoc multi-payment
   gifts have no clean recurring period the way an RD does; 190's own
   GiftCommitmentSchedule must match this (same cross-validation found
   live in 160/170). */

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
