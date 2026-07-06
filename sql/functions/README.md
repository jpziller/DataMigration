# Reusable SQL function library

General-purpose T-SQL helper functions for data cleansing, matching, and ID
handling during a migration — not tied to any specific object or client.
Load whichever ones a given migration needs; these aren't auto-deployed by
the framework.

## utilities/
Zero-dependency string/number/date helpers: `CleanNumber`, `RemoveNonAscii`,
`StripHtml`, `SplitString`, `InitCap`, `IsInt`, `IsLeapYear`,
`GetMonthsBetweenDates`, `EscapeContentNote`, `ToBase64`/`FromBase64`,
`UrlDecode`, `RemoveInvalidXmlChars`.

Also here (load-table pre-flight checks, not string/date helpers, but same
folder): `AddBulkLoadSortColumn` (numbers a load table by parent key so
same-parent rows land in the same Bulk API batch — CLAUDE.md hard rule 6)
and `CheckLoadTableDuplicateKeys` (flags duplicate/NULL migration-key values
before `bulkops` — hard rule 7).

## cleansing/
`GetFirstName` / `GetLastName` (splits a "Full Name" column, handles
Mr/Mrs/Ms/Dr titles and Jr/Sr/II/III suffixes), `IsValidEmail`,
`IsRoleBasedEmail` (flags generic addresses like `info@`), `CleanPostalAddress`
(abbreviation expansion), `IsValidPhone` (needs a `CountryPhoneNumberPattern`
reference table — see the function header for its shape).

## salesforce/
`ConvertTo18DigitId` — case-sensitive 15-char Id -> case-safe 18-char Id,
per Salesforce's published checksum algorithm.

## matching/
Fuzzy string comparison for dedup/match-merge: `JaroWinklerDistance` (best
general-purpose choice), `CompareNames` (crude, fast), `SoundexComparison`,
`CompareStringsNgramMatching`.

## lookups/
Static reference data: `GetStateCode` / `GetStateName` (country + state name
<-> code), `GetCountryCode` / `GetCountryCode3` (ISO 2/3-letter codes).

---

## Provenance note

These were cleaned up from a personal archive of past migration-consulting
scripts, genericized (client database names, one-off table references, and
other tools' product names removed), and standardized on a consistent style.
Two functions from that archive were deliberately **excluded** rather than
ported, because their original file headers carried explicit third-party
copyright notices ("all rights reserved" / a named company's copyright) —
not appropriate to redistribute under this repo's MIT license:

- An invalid-XML-character stripper — reimplemented from scratch here as
  `utilities/RemoveInvalidXmlChars.sql` (the underlying algorithm — strip
  Unicode control characters below 32 except tab/LF/CR — is generic and
  not owned by anyone).
- A country-name lookup table — not ported in this pass; if needed, replace
  with a lookup built from a public ISO 3166 country list instead.
