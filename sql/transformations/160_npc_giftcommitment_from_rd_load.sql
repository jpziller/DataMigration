/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 8 of ~14. Recurring
   Donation -> Gift Commitment (migration guide sec 7.6.2 "Create Gift
   Commitments & Gift Commitment Schedules for Recurring Donations"). This
   step builds the GiftCommitment half only -- GiftCommitmentSchedule
   (170) is a separate later step since it needs THIS load's real,
   written-back GiftCommitmentId.

   DonorId is the RD's Contact's own migrated Person Account Id -- joins
   through dbo.Account (still holding the target-side Person Account
   replicate from the 090/100 requery, MigrationID__c = source Contact Id).

   Status and RecurrenceType are mapped by real picklist value, both
   sides confirmed live (not guessed):
     npsp__Status__c (Active/Lapsed/Closed/Paused) -> GiftCommitment.Status
       -- all 4 values exist verbatim on the target, direct 1:1.
     npsp__RecurringType__c (Open/Fixed) -> RecurrenceType
       (OpenEnded/FixedLength) -- explicit CASE mapping, no value overlap.

   ScheduleType must match 170's own TransactionPeriod mapping exactly --
   confirmed live via a real FIELD_INTEGRITY_EXCEPTION ("Prevent mismatched
   schedule types" validation, Appendix B): a GiftCommitmentSchedule row
   whose TransactionPeriod maps to 'Custom' (Quarterly/'1st and 15th', no
   direct target period) requires its parent GiftCommitment.ScheduleType
   to also be 'Custom', not 'Recurring'. The CASE below mirrors 170's own
   TransactionPeriod mapping so the two never drift apart.

   Name is a genuinely required field with no platform default (confirmed
   live via REQUIRED_FIELD_MISSING when omitted -- describe() shows
   createable: True, nillable: False, defaultedOnCreate: False, same as
   PartyRelationshipGroup.Name (120); not a describe()/API mismatch as an
   earlier version of this comment claimed, see
   validators/GiftCommitment.md's own correction). Reuses the RD's own
   Name. */

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
