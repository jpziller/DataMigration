/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 2 of
   11.

   CORRECTED live (new finding, not anticipated in the plan): Salesforce
   auto-creates an AccountContactRelation (IsDirect = true) the instant a
   Contact is inserted with a real AccountId -- confirmed live, all 16 of
   this build's own Contacts already had one the moment 240 finished
   loading, before this script ever ran. This is the same auto-creation
   pattern already found once for GiftCommitmentSchedule (see
   validators/GiftCommitmentSchedule.md) -- an explicit INSERT here
   collided with the real, already-existing row (submitted 16, succeeded
   0, failed 0 -- no error, since bulk_op()'s own fingerprint-based result
   mapping simply never matched anything real). Never insert
   AccountContactRelation explicitly; replicate the real, already-created
   rows instead (`replicate AccountContactRelation --where "IsDirect =
   true"`) and UPDATE them with the fields the auto-creation doesn't set:
   IsIncludedInGroup/IsPrimaryMember are the real household-membership
   signal, not just AccountId/ContactId -- see
   validators/AccountContactRelation.md (found during the earlier NPSP-
   to-NPC PoC). Every generated member gets IsIncludedInGroup = true;
   exactly one member per household gets IsPrimaryMember = true, chosen
   deterministically by lowest Contact_Load.LoadId (this data has no
   NPSP npo02__Household_Naming_Order__c equivalent to rank by).

   CORRECTED again (user feedback, live): an earlier version of this
   script also backfilled MigrationID__c onto the real auto-created row.
   Wrong -- this row wasn't created by this migration, so stamping a
   migration key on it falsely claims it was, and there's no reason to
   touch a platform-managed row's fields beyond what's functionally
   necessary (unnecessary writes to a system-managed record are their
   own real risk). Only IsIncludedInGroup/IsPrimaryMember are sent.
   Hard Rules 7/12 (migration-key dedup/live-validation) don't apply to
   this table either, for the same reason -- there's no migration key
   here, matching is by the real Id alone (already known via the
   replicate + join below), not a fingerprint/external-id lookup.

   Two more real findings from correcting this live: (1) bulk_op()'s
   default result-matching fingerprints every SENT column, including the
   boolean IsIncludedInGroup/IsPrimaryMember fields here -- Salesforce
   echoes a sent boolean back in a different string representation than
   pandas' CSV export used, silently breaking the fingerprint match for
   every row (reported succeeded=0/failed=0, even though the real DML
   fully succeeded, confirmed by direct query). Always pass
   `--fingerprint-columns Id` for an update where Id is already known
   ahead of time, not the default (every sent column). (2) That same
   false-negative match, on an EARLIER bad run of this same command
   (before this fix), destructively nulled out the Id column this
   script's own SELECT had already populated -- bulk_op()'s in-place
   writeback sets id_column = NULL for any row it fails to fingerprint-
   match, even when the caller supplied a real, correct Id going in. This
   script's SELECT re-derives Id fresh from the replicated
   dbo.AccountContactRelation table every run specifically so a corrupted
   Load table is always recoverable by re-running it -- never hand-edit
   AccountContactRelation_Load's own Id column to "fix" it. */

DROP TABLE IF EXISTS [dbo].[AccountContactRelation_Load];

SELECT
    c.LoadId AS LoadId,
    acr.Id AS Id,
    c.AccountId AS REF_AccountId,  -- bookkeeping only (hard rule 13), for the Sort column below; AccountId itself isn't updateable
    1 AS IsIncludedInGroup,
    CASE WHEN c.LoadId = (
        SELECT MIN(c2.LoadId) FROM [dbo].[Contact_Load] c2 WHERE c2.AccountId = c.AccountId
    ) THEN 1 ELSE 0 END AS IsPrimaryMember
INTO [dbo].[AccountContactRelation_Load]
FROM [dbo].[Contact_Load] c
JOIN [dbo].[AccountContactRelation] acr
    ON acr.AccountId = c.AccountId AND acr.ContactId = c.Id;
