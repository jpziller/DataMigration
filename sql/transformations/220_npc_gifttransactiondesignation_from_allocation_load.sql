/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 14 of ~14, the last one.
   Allocation -> Gift Transaction Designation (migration guide sec 7.6.12
   "Create Gift Transaction Designations"), joining each Allocation's real
   GiftTransactionId and its GAU's real GiftDesignationId (150).

   Real design wrinkle found live, not assumed up front: NPSP's Allocation
   is Opportunity-level (splits one gift's total across GAUs), but 2 of
   our 4 seeded Allocations reference Opportunity #6 -- a multi-Payment
   Opportunity that itself fanned out into 3 separate Gift Transactions
   (210, one per real Payment), not one. GiftTransactionDesignation.
   GiftTransactionId is a single lookup, so an Opportunity-level Allocation
   has no single correct Gift Transaction to attach to when its
   Opportunity produced more than one. Resolved here by splitting each
   such Allocation proportionally across every Payment-level Gift
   Transaction under that Opportunity, weighted by that Payment's own
   share of the Opportunity's total Amount -- accurate and never silently
   drops or guesses at data, at the cost of turning 2 Allocations into 6
   GiftTransactionDesignation rows (Opportunity #6's 3 equal $500 payments
   split each Allocation into 3 equal thirds). The other 2 Allocations
   (Opportunities #2/#3, single-Payment, routed to Gift Transaction
   directly in 200) need no splitting -- a plain 1:1 join.

   Percent required alongside Amount -- confirmed live via a real
   INVALID_INPUT failure ("Complete both the Percent and Amount fields"),
   not assumed up front. Computed against each row's own joined Gift
   Transaction's OriginalAmount (200/210 both populate it), so a plain
   1:1 Allocation always lands at 100% and each split row lands at its
   real proportional share. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionDesignation_Load];

SELECT
    a.Id AS LoadId,
    a.Id AS MigrationID__c,
    gt.Id AS GiftTransactionId,
    gd.Id AS GiftDesignationId,
    a.npsp__Amount__c AS Amount,
    100.0 * a.npsp__Amount__c / gt.OriginalAmount AS [Percent]
INTO [dbo].[GiftTransactionDesignation_Load]
FROM [dbo].[npsp__Allocation__c] a
JOIN [dbo].[GiftTransactionFromOpp_Load] gt ON gt.LoadId = a.npsp__Opportunity__c
JOIN [dbo].[GiftDesignation_Load] gd ON gd.LoadId = a.npsp__General_Accounting_Unit__c

UNION ALL

SELECT
    a.Id + '-' + p.Id AS LoadId,
    a.Id + '-' + p.Id AS MigrationID__c,
    gt.Id AS GiftTransactionId,
    gd.Id AS GiftDesignationId,
    a.npsp__Amount__c * (p.npe01__Payment_Amount__c / o.Amount) AS Amount,
    100.0 * (a.npsp__Amount__c * (p.npe01__Payment_Amount__c / o.Amount)) / gt.OriginalAmount AS [Percent]
FROM [dbo].[npsp__Allocation__c] a
JOIN [dbo].[Opportunity] o ON o.Id = a.npsp__Opportunity__c
JOIN [dbo].[npe01__OppPayment__c] p ON p.npe01__Opportunity__c = o.Id
JOIN [dbo].[GiftTransactionFromPayment_Load] gt ON gt.LoadId = p.Id
JOIN [dbo].[GiftDesignation_Load] gd ON gd.LoadId = a.npsp__General_Accounting_Unit__c;
