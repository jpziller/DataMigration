/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md). Last of the core
   chain. Full Allocation->GiftTransactionDesignation rationale,
   including the proportional split of an Opportunity-level Allocation
   across the multiple Payment-level Gift Transactions its Opportunity fans
   out into (the UNION ALL branch), and Percent being required alongside
   Amount.

   === v2 corrections from the sample-data loop (rebuild-plan findings 2 & 3) ===

   LOAD ORDER -- designations BEFORE refunds. A transaction's total
   designation Amount is capped at CurrentAmount (OriginalAmount minus
   RefundedAmount), and a GiftRefund reduces CurrentAmount ASYNCHRONOUSLY.
   Loading a refund before its transaction's designation makes the
   designation exceed the now-reduced cap and fail (confirmed live, sample
   data -- validators/GiftTransactionDesignation.md). Percent/Amount here
   are computed against OriginalAmount, which equals CurrentAmount only
   while RefundedAmount is still 0 -- so this table MUST load before any
   GiftRefund. If a real client migrates refunds, place them AFTER this
   step (a GiftRefund transform is a deferred scope-expansion item -- see
   okf/npsp-to-npc/reference-implementation.md).

   OPEN QUESTION (flagged for architect/live confirmation -- see
   okf/npsp-to-npc/reference-implementation.md):
   Allocation fan-out vs. the auto-created GiftDefaultDesignation. This
   maps GiftTransactionDesignations from real NPSP Allocations. A
   GiftTransaction whose Opportunity had NO Allocation still needs a
   designation -- the platform's auto-created GiftDefaultDesignation (215)
   supplies the commitment/campaign default, so we deliberately do NOT
   synthesize a GTD for those here (that is what sample-data 430 leaned on:
   inherit the default rather than invent one). Confirm with the architect
   whether Allocation-less transactions should (a) rely on the default as
   here, or (b) get an explicit inherited GTD like 430. This build takes
   (a) -- confirmed to load without error on real data 2026-07-27, but the
   intended behavior still needs architect confirmation. */

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
