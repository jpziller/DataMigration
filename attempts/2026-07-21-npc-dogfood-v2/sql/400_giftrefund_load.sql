/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 10
   of 11 -- companion to 390. Builds GiftRefund_Load from
   dbo.GiftRefund_Mock (25 rows, nested under GiftTransaction in the same
   generate-related-mock-data call -- _ParentMockRef resolves to
   GiftTransaction_Load.LoadId). GiftTransactionId is the only real
   reference this object carries.

   CORRECTED live: three real Appendix-B-style validation rules,
   confirmed via a real failed load (not anticipated in the plan):
   (1) a refund's parent GiftTransaction must already be Status = 'Paid'
   -- filtered out entirely for any parent that isn't (this build's
   Status values are Snowfakery's own random picklist choice, so only
   some transactions qualify); (2) refund Amount must not exceed the
   transaction's own OriginalAmount -- clamped down when the Mock table's
   independently-random Amount is larger; (3) refund Date must be on or
   after the transaction's own TransactionDate (its completion date) --
   clamped up when earlier. Same "Snowfakery generates fields
   independently, with no cross-field or cross-object awareness" pattern
   already hit on Campaign's StartDate/EndDate (330) and
   GiftTransaction's TransactionDueDate (390), just spanning two
   different objects here instead of two fields on one object. */

DROP TABLE IF EXISTS [dbo].[GiftRefund_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-GR-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    gt.Id AS GiftTransactionId,
    CASE WHEN m.Date < gt.TransactionDate THEN gt.TransactionDate ELSE m.Date END AS Date,
    CASE WHEN m.Amount > gt.OriginalAmount THEN gt.OriginalAmount ELSE m.Amount END AS Amount,
    m.Reason,
    m.Status
INTO [dbo].[GiftRefund_Load]
FROM [dbo].[GiftRefund_Mock] m
JOIN [dbo].[GiftTransaction_Load] gt ON gt.LoadId = m._ParentMockRef
WHERE gt.Status = 'Paid';
