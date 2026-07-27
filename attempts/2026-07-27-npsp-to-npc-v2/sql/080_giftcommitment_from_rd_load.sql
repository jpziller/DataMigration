/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC v2 build attempt (2026-07-27), group 8. CARRIED FORWARD
   UNCHANGED from the PoC (sql/transformations/160) -- see that header for
   the full RD->GiftCommitment rationale (Status/RecurrenceType picklist
   mapping, the ScheduleType cross-validation that must match 090's
   TransactionPeriod, Name required-on-insert).

   Sample-data learning confirmed compatible: a Recurring-type
   GiftCommitment auto-creates its GiftCommitmentSchedule (and a
   GiftDefaultDesignation) -- 090 already only inserts a schedule for the
   Custom case, so no collision. */

DROP TABLE IF EXISTS [dbo].[GiftCommitmentFromRD_Load];

SELECT
    rd.Id AS LoadId,
    rd.Id AS MigrationID__c,
    rd.Name,
    pa.Id AS DonorId,
    CASE rd.npsp__Status__c
        WHEN 'Active' THEN 'Active'
        WHEN 'Lapsed' THEN 'Lapsed'
        WHEN 'Closed' THEN 'Closed'
        WHEN 'Paused' THEN 'Paused'
        ELSE 'Active'
    END AS [Status],
    CASE rd.npsp__RecurringType__c
        WHEN 'Open' THEN 'OpenEnded'
        WHEN 'Fixed' THEN 'FixedLength'
        ELSE 'OpenEnded'
    END AS RecurrenceType,
    rd.npsp__StartDate__c AS EffectiveStartDate,
    CASE rd.npe03__Installment_Period__c
        WHEN 'Monthly' THEN 'Recurring'
        WHEN 'Weekly' THEN 'Recurring'
        WHEN 'Yearly' THEN 'Recurring'
        ELSE 'Custom'
    END AS ScheduleType
INTO [dbo].[GiftCommitmentFromRD_Load]
FROM [dbo].[npe03__Recurring_Donation__c] rd
JOIN [dbo].[Account] pa ON pa.MigrationID__c = rd.npe03__Contact__c;
