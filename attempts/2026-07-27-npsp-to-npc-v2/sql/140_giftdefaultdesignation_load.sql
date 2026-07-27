/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC v2 build attempt (2026-07-27), group 14. NEW in v2 --
   doc-only, no counterpart in the PoC (090-220), which predated this
   finding.

   The platform AUTO-CREATES a GiftDefaultDesignation the instant a
   GiftCommitment (and a GiftDesignation) is inserted -- 100%
   AllocatedPercentage, pointing at the org's own default GiftDesignation.
   Confirmed live on the sample-data build (sql/transformations/420,
   validators/GiftDefaultDesignation.md,
   okf/nonprofit-cloud/never-update-auto-created-records.md): an explicit
   insert collides (FIELD_INTEGRITY_EXCEPTION, "Designations can't exceed
   100%"). Same auto-creation family as AccountContactRelation (030) and
   GiftCommitmentSchedule (090).

   Auto-creation is NOT universal: confirmed ~Recurring-type commitments
   get one; Custom-type and Campaign-only paths may not. So a CONSUMER
   (150) must replicate GiftDefaultDesignation and LEFT JOIN it -- never
   assume every commitment has one.

   What this migration does: NOTHING. No Load table, no insert, no update.
   The platform's own default designation is what a human-created commitment
   gets too; there is no NPSP source field that should overwrite it. This
   file exists so a future engineer doesn't try to migrate NPSP's own
   "default GAU" concept into an auto-created record. See
   validators/GiftDefaultDesignation.md. */
