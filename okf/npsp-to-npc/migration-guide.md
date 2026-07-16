---
type: Reference
title: NPSP to Agentforce Nonprofit Migration Guide
description: Salesforce's official migration guide (v2.0) for moving from
  Nonprofit Success Pack to Agentforce Nonprofit / Nonprofit Cloud --
  strategy guidance plus a concrete, ordered ~35-step data migration
  sequence.
resource: https://resources.docs.salesforce.com/rel1/doc/en-us/static/pdf/Agentforce_Nonprofit_Migration_Guide_v2.pdf
tags: [npsp, npc, afnp, agentforce-nonprofit, migration-guide, nonprofit]
timestamp: "2026-07-16"
---
# NPSP to Agentforce Nonprofit Migration Guide

78 pages, written by Galvin Technologies in partnership with Salesforce
(v2.0). Linked from the [migration guides help
article](https://help.salesforce.com/s/articleView?id=sfdo.npc_implementation_migration_guides.htm&type=5)
— that landing page is a JavaScript-rendered SPA this bundle's own
tooling can't fetch directly, so this concept file (not the article
itself) is the map. Verified by direct extraction of the PDF's real
table of contents and full text, not summarized secondhand.

Core terminology: Salesforce's own docs use "Agentforce Nonprofit"
(AFNP) for the migration target most places in this guide; "Nonprofit
Cloud" is the product family name used elsewhere. Both names refer to
the same target platform throughout this bundle.

# Table of contents

1. Introduction (purpose, audience, document history)
2. Migration Overview -- AFNP's design philosophy (built on the core
   Salesforce platform, like other Industry Clouds, rather than a
   separate managed package), migration approach, assumptions (**new org
   vs. in-place** -- see
   [new-org-vs-in-place.md](new-org-vs-in-place.md), disregarded/omitted
   fields are deliberate, software-agnostic, assumes current-version
   NPSP feature usage)
3. Business Process Audit -- user permissions/record access,
   integrations/customizations/third-party packages, objects/fields/
   record types
4. Technical Audit -- integrations/customizations, third-party packages
5. Strategy Checklist -- the conceptual-comparison + recommendation
   pattern used throughout: change management, stakeholders, user
   management, **account model** (Person Accounts, Business Accounts,
   Households as Party Relationship Groups, relating people/businesses to
   each other), addresses/emails/phones, campaigns & campaign members,
   **gifts & related records** (Gift Designations, Gifts, Gift Soft
   Credits, Gift Refunds), tasks & events, object/sharing strategy, data
   archival, data migration strategy, customization strategy
6. Preparing the Environment -- export/backup, data hygiene/de-dup,
   initial AFNP org setup, third-party apps, custom fields required for
   migration (a legacy-Id field per target object, populated with the
   NPSP record's CASESAFEID -- the same migration-key pattern this
   framework's own Hard Rule 4/7 already use)
7. **Data Migration Sequence** -- the real step-by-step order, see below
8. Objects Not Recommended for Migration -- e.g. Recurring Donation
   Change Log, Batch entries, Engagement Plans (noted as candidates for
   external data-warehouse storage or a custom AFNP Action Plan instead)
9. Additional Resources -- Salesforce Field Reference Guide, Agentforce
   Nonprofit product documentation, Agentforce Nonprofit developer guide
10. Appendix -- see [mapping-spreadsheets.md](mapping-spreadsheets.md)
    (Appendix A) and the three validations files (Appendix B)

# Data Migration Sequence (§7) -- the ordered outline

Each step is a real numbered subsection in the guide with its own
Preparation/Migration detail -- not reproduced here yet (deliberately
deferred, see this bundle's own index.md). This is the map:

1. Migrate Users & assign roles/profiles/permissions
2. Migrate Accounts
   1. Overview
   2. Create Party Role Relationships
   3. Create Accounts for Households (if applicable)
   4. Create Accounts for Organizations
   5. Create Individuals (Person Accounts)
   6. Create a Party Relationship Group record for every Household
      Account created in step 3 -- see
      [households-to-party-relationship-groups.md](households-to-party-relationship-groups.md)
   7. Create Account Contact Relationships (AccountContactRelation)
   8. Create Contact Contact Relationships (ContactContactRelation)
   9. Create Account Account Relationships (optional)
3. Migrate Addresses -- Contact Point Address, then Phone, then Email
4. Migrate Campaigns -- Campaigns, then Outreach Source Codes (optional)
5. Migrate Gift Designations (GAUs)
6. Migrate Gifts (Opportunities and Payments) -- the largest, most
   conditional section:
   1. Migrate Recurring Donations (export the Recurring Donation
      Schedule first)
   2. Create Gift Commitments & Gift Commitment Schedules for Recurring
      Donations
   3. Create Opportunities
   4. Create Gift Commitments from Opportunities
   5. Create Gift Transactions from Opportunities -- see
      [opportunity-routing.md](opportunity-routing.md) for the routing
      rule across steps 3-5
   6. Create Gift Transactions from Payments
   7. Create Gift Refunds from Payments
   8. Create Gift Soft Credits from Account Soft Credits
   9. Create Gift Soft Credits from Partial Soft Credits
   10. Create Gift Soft Credits from Opportunity Contact Roles
   11. Create Gift Default Designations
   12. Create Gift Transaction Designations
   13. Migrate Tasks and Events
   14. Migrate other data
   15. Migrate emails, attachments & files

# Citations

1. [NPSP to Agentforce Nonprofit Migration Guide v2.0 (PDF)](https://resources.docs.salesforce.com/rel1/doc/en-us/static/pdf/Agentforce_Nonprofit_Migration_Guide_v2.pdf)
2. [Migration guides help article](https://help.salesforce.com/s/articleView?id=sfdo.npc_implementation_migration_guides.htm&type=5)
