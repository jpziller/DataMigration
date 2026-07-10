---
description: Query the target org's real RecordType rows for an object and write them into a reference table to JOIN against by DeveloperName.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py resolve-record-types *)
---
Resolve RecordTypes for `$ARGUMENTS` (object name).

1. Run: `.venv/Scripts/python.exe cli.py resolve-record-types $ARGUMENTS`
2. Report the row count written, or say plainly if the object has no
   RecordTypes configured in this org.
3. Remind: the transform should `JOIN dbo.RecordTypeMap` by
   `DeveloperName` to populate `RecordTypeId` (hard rule 15) — never hand-
   copy a raw Id from the source, since RecordType Ids are org-specific
   and never portable. Use a `LEFT JOIN` so an unmatched `DeveloperName`
   surfaces as a visible `NULL RecordTypeId` rather than silently
   dropping the row or matching nothing — this design has no automatic
   unresolved-value guard, so making the gap visible in the transform
   itself is what catches it.

Read-only against Salesforce (a plain SOQL query), writes only to the
mirror DB — safe to run without confirmation.
