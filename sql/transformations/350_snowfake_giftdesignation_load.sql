/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 7 of
   11. Builds GiftDesignation_Load from dbo.GiftDesignation_Mock (6 rows,
   generate-related-mock-data GiftDesignation --count GiftDesignation=6).
   A standalone root object -- no in-scope parent, no self-reference.

   Field selection deliberately excludes the transaction-summary rollup
   fields also present on the Mock table (AverageTransactionAmount,
   TotalTransactionCount, LastYearTrxnAmount, etc.) -- those are
   platform-computed from real Gift Transaction Designation activity, not
   something a human fills in when creating a fund/designation through
   the UI; a real one starts with zero transaction history.

   IsDefault deliberately never sent (not even false) -- confirmed live,
   this org already has a real, pre-existing default designation, and a
   second IsDefault = true collides with it (INVALID_INPUT: "Looks like
   another gift designation is already marked as default"). A real-world
   platform constraint (at most one default org-wide), not something to
   route around. */

DROP TABLE IF EXISTS [dbo].[GiftDesignation_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-GD-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    'Snowfake-' + m.Name AS Name,
    m.Description,
    m.IsActive
INTO [dbo].[GiftDesignation_Load]
FROM [dbo].[GiftDesignation_Mock] m;
