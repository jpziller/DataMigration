# okf bundle update log

## 2026-07-25
* **New subject area**: [Synthetic-data recipes (external sources +
  coverage)](synthetic-data-recipes/index.md) with its first reference,
  [external-recipe-sources.md](synthetic-data-recipes/external-recipe-sources.md)
  -- a describe-and-link catalog of the shared Snowfakery recipe libraries
  that already exist (SFDO community, CumulusCI, Snowfakery), per-cloud
  coverage + gaps (Consumer Goods/Sales/Service largely uncovered), and
  the limit that upstream recipes give structure, not the auto-creation
  behavior this repo learns empirically. Researched live 2026-07-25. See
  ROADMAP.md #83.
* **Fix**: root [index.md](index.md) now lists the `nonprofit-cloud`
  subject area (it existed but had never been added to the root listing).
* **Tie-in**: this bundle is now actively surfaced, not just present --
  the new `gather-okf` command and CLAUDE.md's Standard Workflow make
  consulting relevant OKF a required step before building, so a clone
  doesn't rediscover this knowledge after a mistake (ROADMAP.md #83).

## 2026-07-16
* **Update**: Added
  [New org, not an in-place upgrade](npsp-to-npc/new-org-vs-in-place.md)
  -- Salesforce's own §2.3.1 recommendation, surfaced by a direct
  question about whether a real migration needs one org or two.
* **Initialization**: Created the bundle root and its first subject area,
  [NPSP to Nonprofit Cloud (AFNP)](npsp-to-npc/index.md), from a full
  review of Salesforce's official migration guide and companion mapping
  workbook. See ROADMAP.md #72.
