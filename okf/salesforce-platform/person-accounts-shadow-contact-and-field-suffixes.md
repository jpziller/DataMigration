---
type: MigrationPattern
title: Person Accounts -- the shadow Contact, and the __pc / __pr field suffixes
description: A cross-cloud platform feature (irreversible once enabled) that
  merges an Account and a Contact into one "person" record for B2C-style
  data. Each person is ONE Account row plus a platform-managed paired
  "shadow" Contact. Contact fields are mirrored onto the Account with special
  API-name suffixes -- Person* for standard fields, __pc for custom fields,
  __pr for custom relationships (the person-account analogs of plain fields
  and __c / __r). The migration consequence is that you load the ACCOUNT (with a
  Person Account RecordTypeId) and never insert the Contact -- the platform
  auto-creates it, and PersonContactId hands you its Id afterward. You may
  need to RECOGNIZE __pc/__pr (so tooling doesn't mis-handle them) even when
  you never migrate "into" them as separate targets.
tags: [salesforce-platform, cross-cloud, person-accounts, pc-suffix, pr-suffix, shadow-contact, account, contact, record-type, migration-pattern, nonprofit-cloud]
timestamp: "2026-08-01"
---
# Person Accounts -- the shadow Contact, and the __pc / __pr field suffixes

## What a Person Account is

**Person Accounts** is a platform feature for B2C data, where the customer
*is* an individual, not a company. When it's enabled (an **irreversible**
org-level change), a "person" is stored as **one Account row** with a
platform-managed **paired "shadow" Contact**. The two are linked:
`Account.PersonContactId` holds the Id of the auto-created Contact, and
`Account.IsPersonAccount = true` distinguishes a person account from a normal
business account.

You never see this feature in a plain B2B org (Account + separately-inserted
Contact). It shows up in **Nonprofit Cloud / Agentforce for Nonprofits**
(which *mandates* person accounts -- see the NPSP->NPC reference
implementation), and in some B2C Sales/Service orgs.

## The field-suffix taxonomy (the part that trips people up)

Because a person's individual attributes conceptually belong to the Contact
but the record you work with is the Account, Salesforce **mirrors** the
Contact's fields onto the Account under distinct API names. These are **field
and relationship name suffixes, not objects**:

| On a person account (Account) | What it is | Business-account analog |
|---|---|---|
| `Person`-prefixed standard field | a standard Contact field surfaced on Account | e.g. `PersonEmail`, `PersonMobilePhone`, `PersonBirthdate`, `PersonContactId` |
| `Foo__pc` | a **custom** Contact field surfaced on the person Account | `Foo__c` (on Contact) |
| `Foo__pr` | the **relationship** name for a **custom lookup** on the person Account | `Foo__r` |
| standard relationship, `Person`-prepended | standard relationship traversal on a person account | plain standard relationship name |

So the mnemonic: `__pc` is to `__c` as `__pr` is to `__r` -- the same custom
field / custom relationship, in its person-account-mirrored form on the
Account. A field ending `_pc` is "a Contact field supported for person
accounts but not business accounts" (Salesforce Help, Account Fields).

Namespacing still applies on top of the suffix: `ns__Foo__pc` is a *managed
package* person-account field (portable to any org licensed for that
package), while a bare `Foo__pc` is an *org-specific* custom field -- the same
packaged-vs-org-custom distinction as `ns__Foo__c` vs `Foo__c`.

## The migration consequence

**You migrate a person by loading the ACCOUNT, not the Contact.**

- Insert the **Account** with a Person Account `RecordTypeId`. The paired
  **Contact is auto-created by the platform** -- "when a person account is
  created ... a corresponding contact record is also created" (SOAP API
  Person Accounts guide). **Never insert the shadow Contact yourself.**
- Person data lives on the Account for a person account: set `PersonEmail`,
  and any custom `Foo__pc` fields, **on the Account load**. So a source
  Contact-side custom field's real target is often a `__pc` field on the
  Account insert -- one Account load, not a Contact load.
- After the load, `Account.PersonContactId` gives you the auto-created
  Contact's Id (needed by anything that must lookup to the person's Contact,
  e.g. a household-membership `AccountContactRelation` -- see the NPSP->NPC
  reference implementation, which reads `PersonContactId` back from a
  post-load replicate).
- Converting a business account to a person account (or vice-versa) via
  `update()`/`upsert()` has caveats: you can't change other fields in the
  same call, and fields common to both (Owner, Currency) must already match.

## "Need to recognize, not migrate into"

A key subtlety: even in a person-account org you rarely migrate *into*
`__pc`/`__pr` as if they were separate objects -- you load the Account. But
**tooling still has to RECOGNIZE them.** This repo's `generalize-data-shape`
classifies API names for cloud-level portability
(`data_shape._api_name_kind`), and originally only knew `__c`/`__r`/`__x`.
On a person-account org (found live on a Salesforce demo org, 2026-07-31)
that let an org's own `SDO_Foo__pc` custom fields leak into what's meant to
be cloud-true shared IP, because `__pc` fell through to "standard". The fix
was to classify `__pc`/`__pr` the same as `__c`/`__r` (org-custom stripped,
namespaced-packaged kept) -- recognizing them precisely so they're handled
correctly, without ever migrating into them.

## How to recognize it on a new org

- `Account.IsPersonAccount` exists and some Accounts have it `true`.
- The Account describe() carries `Person*` standard fields and any `*__pc`
  custom fields; custom lookups traverse via `*__pr`.
- If the org is a plain B2B org, none of these exist -- don't invent them
  (Hard Rule 5, No Invented Field Names -- confirm with `describe`).

# Citations

1. [Person Account Record Types | SOAP API Developer Guide](https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_guidelines_personaccounts.htm)
   -- the paired Contact is auto-created on person-account creation;
   `PersonContactId`; `IsPersonAccount`; business<->person conversion caveats.
2. [Account Fields | Salesforce Help](https://help.salesforce.com/s/articleView?id=sales.account_fields.htm&type=5)
   -- "Fields with a suffix `_pc` are contact fields that are supported for
   person accounts but not business accounts."
3. Salesforce community confirmation of the `__pr` relationship suffix
   (custom relationships end `__pr`; standard relationships get `Person`
   prepended): [Forcetalks -- which fields/relationships end with __pc and __pr](https://www.forcetalks.com/salesforce-topic/which-custom-fields-or-relationships-in-salesforce-ends-with-pc-and-pr/).
   Treated as community-sourced (not first-party); the `__pc` half and the
   auto-created-Contact behavior are corroborated by the two Salesforce docs
   above.
4. In-repo: `okf/npsp-to-npc/reference-implementation.md` (person accounts
   are mandatory in AFNP; load the Account, shadow Contact auto-created,
   `PersonContactId` read back post-load) and `data_shape._api_name_kind`
   (the `__pc`/`__pr` classification fix).
