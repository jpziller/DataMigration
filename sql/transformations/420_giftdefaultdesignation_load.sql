/* No ticket -- no ticket system in use for this project (hard rule 10).

   PROMOTED (2026-07-25) from attempts/2026-07-21-npc-sample-v2/sql/ --
   the Replace-model promotion described in CLAUDE.md's "Library vs.
   attempts workspace" section. This replaces the library's own earlier
   version, which built a Load table and explicitly INSERTed one
   GiftDefaultDesignation per GiftCommitment -- confirmed wrong live (the
   platform auto-creates this row; the explicit insert collided, 15 of 15
   failed). See validators/GiftDefaultDesignation.md and
   okf/nonprofit-cloud/never-update-auto-created-records.md.

   NPC fundraising/donor-management Snowfakery sample data recipe, group 11
   of 11 (final group).

   CORRECTED live (2026-07-21, second rebuild pass): the platform
   auto-creates a GiftDefaultDesignation the instant a GiftCommitment is
   inserted -- 100% AllocatedPercentage, GiftDesignationId pointing at
   this org's own real, pre-existing default GiftDesignation. Confirmed
   live: querying the org directly for 3 of this build's own real
   GiftCommitment Ids each showed exactly one already-existing
   GiftDefaultDesignation row, all at 100%. This build's original
   explicit insert (one row per commitment, round-robin across our own 6
   GiftDesignation_Load rows, also at 100%) collided with the real
   auto-created row -- FIELD_INTEGRITY_EXCEPTION "Designations can't
   exceed 100% on a gift transaction," 15 of 15 failed cleanly (0
   succeeded, nothing to clean up).

   Same auto-creation family already known for AccountContactRelation
   (see 250's own corrected header) and GiftCommitmentSchedule (see
   validators/GiftCommitmentSchedule.md) -- but per the user's own
   correction this pass, the fix is NOT to replicate-then-update the
   auto-created row either. The org's real default designation link is
   what a human-created commitment gets automatically too; there's no
   evidence a human ever goes back and repoints it to a different
   designation. Never insert, never update -- leave the platform's own
   auto-created default entirely alone.

   NOTE (confirmed 2026-07-24, building the corrected 430): auto-creation
   is NOT universal -- 12 of this build's 15 real GiftCommitment records
   (all Recurring-type) have an auto-created GiftDefaultDesignation; the 3
   Custom-type ones don't, and Campaign never gets one at all. A CONSUMER
   of this data (430_gifttransactiondesignation_load.sql) must replicate
   GiftDefaultDesignation and LEFT JOIN it, never assume every commitment
   has one. See validators/GiftDefaultDesignation.md.

   What this migration does now: nothing. No Load table, no insert, no
   update. See validators/GiftDefaultDesignation.md. */
