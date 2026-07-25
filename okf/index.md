---
okf_version: "0.1"
---
# okf bundle

This project's Open Knowledge Format (OKF) v0.1 reference bundle — a
git-tracked, human- and agent-readable knowledge library for
migration-relevant knowledge that isn't tied to one client engagement's
own SQL mirror database. See `validators/README.md` for the sibling
`validators/` bundle (this project's own tooling gotchas); this bundle is
for external/industry knowledge instead — official Salesforce
documentation, target-platform data models, and migration patterns,
described and linked to their real source rather than duplicated.

# Subject areas

* [NPSP to Nonprofit Cloud (AFNP)](npsp-to-npc/index.md) - official
  Salesforce migration guidance for moving from Nonprofit Success Pack to
  Agentforce Nonprofit / Nonprofit Cloud.
* [Nonprofit Cloud (AFNP)](nonprofit-cloud/index.md) - source-agnostic
  target-platform knowledge for Nonprofit Cloud itself (auto-created
  records, validations, the fundraising reference implementation),
  regardless of which system a client migrates from.
* [Synthetic-data recipes (external sources + coverage)](synthetic-data-recipes/index.md) -
  where vetted, shareable synthetic-data recipes already exist per cloud
  (SFDO community, CumulusCI, Snowfakery), so a migration reuses one
  before authoring its own -- the describe-and-link companion to this
  repo's own `sample_data/` recipes.
