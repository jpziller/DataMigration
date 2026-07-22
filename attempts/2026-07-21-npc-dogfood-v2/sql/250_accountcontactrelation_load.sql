/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 2 of
   11.

   CORRECTED live (2026-07-21, second rebuild pass): Salesforce
   auto-creates an AccountContactRelation (IsDirect = true) the instant a
   Contact is inserted with a real AccountId -- confirmed again this
   pass, same as the first build. The first build's own fix (still
   documented in validators/AccountContactRelation.md's earlier entries)
   was to REPLICATE the real auto-created row and UPDATE it with
   IsIncludedInGroup/IsPrimaryMember. That update itself turned out to be
   wrong, caught by the user directly: "you shouldn't be updating auto
   created records... not even to add a migration id to it... the rule
   to not update the created records is all created records and not
   just one object." Investigated live rather than assumed either way
   (per the user's own standing instruction not to brute-force past a
   real platform question) -- queried every real, non-migrated,
   IsDirect=true AccountContactRelation row in this org:

       IsIncludedInGroup=False, IsPrimaryMember=False -- 5 of 5, zero
       exceptions.

   This directly contradicts the first build's premise that real data
   shows these fields set True on a household member -- that earlier
   finding ("IsIncludedInGroup populated 10/10, mixed True/False") came
   from an UNFILTERED sample that, on closer look, was actually picking
   up organization-style business relationships (Roles = Influencer/
   Decision Maker/Evaluator/Other -- clearly not household membership at
   all), not IsDirect=true household rows. The real, IsDirect=true shape
   this migration should actually match is uniformly False/False --
   i.e. NOT setting these fields is what mirrors real human-created data
   here, not setting them True. See validators/AccountContactRelation.md
   for the corrected write-up.

   What this migration does now: nothing. No Load table, no insert, no
   update -- the platform's own auto-created row (already exactly
   matching real evidenced shape) is left completely untouched. */
