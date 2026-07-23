/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 6 of
   11. Builds Campaign_Load from dbo.Campaign_Mock (4 rows, generated
   together with CampaignMember below -- generate-related-mock-data
   Campaign CampaignMember --count Campaign=4 --count CampaignMember=3-8).
   Campaign.Name is a real, standard createable field -- straightforward
   "Snowfake-" prefix, no special-case handling needed.

   StartDate/EndDate: Snowfakery generates each date field independently
   (fake.DateBetween per column, no cross-field awareness), which can and
   did produce EndDate < StartDate on a real row -- confirmed live,
   FIELD_INTEGRITY_EXCEPTION "campaign end date should not be before the
   start date." Swap the two when out of order rather than trusting the
   Mock table's raw values. */

DROP TABLE IF EXISTS [dbo].[Campaign_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-CAMP-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    'Snowfake-' + m.Name AS Name,
    m.[Type],
    m.Status,
    CASE WHEN m.StartDate <= m.EndDate THEN m.StartDate ELSE m.EndDate END AS StartDate,
    CASE WHEN m.StartDate <= m.EndDate THEN m.EndDate ELSE m.StartDate END AS EndDate,
    m.ExpectedRevenue,
    m.BudgetedCost,
    m.ActualCost,
    m.ExpectedResponse,
    m.NumberSent,
    m.IsActive,
    m.Description
INTO [dbo].[Campaign_Load]
FROM [dbo].[Campaign_Mock] m;
