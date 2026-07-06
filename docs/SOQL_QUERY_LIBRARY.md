# SOQL Query Library

Copyright (c) 2026 JP Ziller LLC. Released under the [MIT License](../LICENSE).

A collection of useful Tooling API and standard SOQL queries for inspecting
org metadata and data — run any of these with:

```bash
python cli.py query "<SOQL>"
```

Queries against Tooling API objects (`EntityParticle`, `FieldDefinition`,
`CustomField`, `ValidationRule`, `WorkflowRule`, `ApexTrigger`, `Flow`,
`RelationshipInfo`, etc.) require the Tooling API rather than the standard
REST Query API — `query_tool.py`/`sf.query()` hits the standard REST Query
API only, so run these particular ones by hand via `sf.toolingexecute()`
(see `risk_analyzer.py`) rather than `python cli.py query`. Some of these
object types aren't queryable through the standard Data API at all —
confirmed the hard way while building `risk_analyzer.py` (roadmap #5,
now built): `ValidationRule`/`ApexTrigger`/`WorkflowRule` are Tooling-API-
only (`INVALID_TYPE` otherwise), while `ProcessDefinition` and
`FlowDefinitionView` (not shown below — see `risk_analyzer.py` for the
query, since it's what actually makes "which Flows are record-triggered on
this object" answerable) are standard-REST-API-queryable, *not* Tooling.
Don't assume every metadata object in this file uses the same endpoint —
confirm per object type, the two are genuinely mixed.

Most of what's below now runs automatically via `analyze-org-risk` for the
object-level automation inventory it covers (validation rules, triggers,
record-triggered Flows, workflow rules, approval processes) — these
queries remain useful by hand for anything deeper: field-level formula
text, picklist values, relationship details `risk_analyzer.py` doesn't
surface.

---

## Metadata Queries

### Approval processes on an object
```sql
SELECT Id, Name, DeveloperName, Type, Description, TableEnumOrId, State, CreatedDate
FROM ProcessDefinition
WHERE TableEnumOrId = 'Opportunity'
```

### Custom fields on an object
```sql
SELECT Id, DeveloperName, EntityDefinition.QualifiedApiName, InlineHelpText, NamespacePrefix, Description
FROM CustomField
WHERE EntityDefinition.QualifiedApiName = 'Account'
```

### List of custom objects
```sql
SELECT Id, ExternalName, NamespacePrefix, Description, DeveloperName
FROM CustomObject
```
Add `WHERE NamespacePrefix = ''` to see only objects built in-house, not
ones that came from an installed package.

### Full field metadata for a set of objects
```sql
SELECT EntityDefinition.QualifiedApiName, Name, FieldDefinition.Description, Label,
       QualifiedApiName, InlineHelpText, DataType, Length, Precision, Digits,
       NamespacePrefix, IsAutonumber, IsCalculated, IsCaseSensitive, IsCreatable,
       IsDefaultedOnCreate, IsDependentPicklist, IsNillable, IsUnique, IsUpdatable,
       IsIdLookup, DefaultValueFormula, DeveloperName, DurableId, ExtraTypeInfo,
       FieldDefinitionId, Id, IsApiFilterable, IsApiGroupable, IsApiSortable,
       IsCompactLayoutable, IsComponent, IsCompound, IsDeprecatedAndHidden,
       IsDisplayLocationInDecimal, IsEncrypted, IsFieldHistoryTracked,
       IsHighScaleNumber, IsHtmlFormatted, IsLayoutable, IsListVisible, IsNameField,
       IsNamePointing, IsPermissionable, IsWorkflowFilterable, IsWriteRequiresMasterRead,
       Mask, MaskType, MasterLabel, ReferenceTargetField, ReferenceTo, RelationshipName,
       RelationshipOrder, Scale, ServiceDataTypeId, ValueTypeId
FROM EntityParticle
WHERE EntityDefinitionId IN ('Order', 'OrderItem', 'Contract')
ORDER BY EntityDefinitionId, QualifiedApiName
```
This is close to what `load_order.py`'s dependency graph reads from
describe() directly (relationship fields, `RelationshipOrder` for
master-detail) — useful as a raw reference when the Python-side tool isn't
enough, e.g. checking `IsApiSortable`/`IsApiFilterable` before writing a
`profiling.py`-style aggregate query against an unfamiliar field.

### Find what object types a polymorphic field can point to
```sql
SELECT QualifiedApiName, RelationshipName, ReferenceTo, ReferenceTargetField
FROM FieldDefinition
WHERE EntityDefinition.QualifiedApiName = 'Event' AND QualifiedApiName = 'WhoId'
```

### Data types for every field on an object
```sql
SELECT Id, QualifiedApiName, (SELECT DataType, QualifiedApiName FROM Particles)
FROM FieldDefinition
WHERE EntityDefinition.QualifiedApiName = 'Account'
```

### Global value sets (shared picklists)
```sql
SELECT Id, DeveloperName, MasterLabel, Description, NamespacePrefix
FROM GlobalValueSet
```

### Lightning web components
```sql
SELECT Id, ApiVersion, DeveloperName, FullName, TargetConfigs
FROM LightningComponentBundle
```

### Apex triggers on the org (with usage flags)
```sql
SELECT Id, ApiVersion, Name, EntityDefinition.DeveloperName, EntityDefinition.Description,
       UsageAfterDelete, UsageAfterInsert, UsageAfterUndelete, UsageAfterUpdate,
       UsageBeforeDelete, UsageBeforeInsert, UsageBeforeUpdate, UsageIsBulk
FROM ApexTrigger
```
Directly relevant before any load: this is exactly the kind of query that
should feed CLAUDE.md's Logic Disablement guidance (see the Migration
Playbook §6) — know what's active before deciding what (if anything) needs
disabling.

### Active flows
```sql
SELECT Id, Definition.DeveloperName, MasterLabel, VersionNumber, Definition.Description,
       ProcessType, Status, Description, IsTemplate, ApiVersion, Definition.NamespacePrefix
FROM Flow
WHERE Status = 'Active'
ORDER BY Definition.DeveloperName, MasterLabel, VersionNumber ASC
```

### Lookup/master-detail relationships pointing at an object
```sql
SELECT Id, JunctionIdListNames, ChildSobject.QualifiedApiName, Field.DeveloperName,
       Field.DataType, IsCascadeDelete
FROM RelationshipInfo
WHERE ChildSobject.QualifiedApiName = 'Opportunity'
```
This is the Tooling API's own view of the same relationship graph
`load_order.py` builds from describe() — useful for cross-checking, or for
finding relationships describe() doesn't surface as cleanly.

### Validation rules on an object
```sql
SELECT Id, Active, Description, EntityDefinition.DeveloperName, ErrorDisplayField, ErrorMessage
FROM ValidationRule
WHERE EntityDefinition.DeveloperName = 'Account'
```

### Installed-package custom objects (e.g. Vlocity, or any package)
```sql
SELECT QualifiedApiName, IsQueryable, NamespacePrefix, DurableId
FROM EntityDefinition
WHERE QualifiedApiName LIKE '%__c' AND NamespacePrefix LIKE 'vlocity%'
ORDER BY QualifiedApiName
```
Swap the `NamespacePrefix` filter for whatever package you're checking.

### Workflow rules
```sql
-- All objects
SELECT Id, Name, TableEnumOrId, NamespacePrefix FROM WorkflowRule

-- One object
SELECT Name, TableEnumOrId FROM WorkflowRule WHERE TableEnumOrId = 'Account'
```

### Metadata (including formula definitions) for a single field
Tooling API's `Metadata` field is only queryable one field at a time:
```sql
SELECT Id, DataType, NamespacePrefix, DeveloperName, Metadata
FROM FieldDefinition
WHERE EntityDefinition.QualifiedApiName = 'Account' AND DurableId = 'Account.Industry'
```

### Picklist values for every picklist field on an object
```sql
SELECT EntityParticle.Name, IsDefaultValue, ValidFor, Label, Value
FROM PicklistValueInfo
WHERE EntityParticle.EntityDefinitionId = 'Account'
ORDER BY EntityParticleId, Value
```
Compare against `profiling.py`'s value-distribution output for the same
field — this shows every *valid* value; profiling shows which ones are
actually *used* in real data. The gap between the two is worth reviewing
before migration.

### Apex classes, Visualforce components/pages
```sql
SELECT Id, Name, Status, ApiVersion, NamespacePrefix FROM ApexClass
SELECT Id, ApiVersion, ControllerType, Description, NamespacePrefix, ControllerKey FROM ApexComponent
SELECT Id, ApiVersion, ControllerType, Description, NamespacePrefix, ControllerKey FROM ApexPage
```

---

## Data Queries

### List of users
```sql
SELECT Id, FirstName, LastName, Name, Suffix, Username FROM User
```

### Opportunity with its line items (parent-child subquery)
```sql
SELECT Name, Id, (SELECT Quantity, PricebookEntry.Name, ListPrice, PricebookEntry.UnitPrice FROM OpportunityLineItems)
FROM Opportunity
LIMIT 2
```

### Polymorphic relationship filtering
Sometimes you want records only where a polymorphic lookup points at a
specific object type:
```sql
-- EmailMessages related to an Account specifically
SELECT * FROM EmailMessage WHERE Relation.Type = 'Account'

-- Tasks tied to an Account or an Opportunity
SELECT * FROM Task WHERE What.Type IN ('Account', 'Opportunity')
```
See Salesforce's [polymorphic relationships in SOQL](https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/langCon_apex_SOQL_polymorphic_relationships.htm)
docs for the full pattern.

### CPQ/Billing error log rollup
```sql
SELECT blng__ErrorCode__c, blng__ErrorName__c, blng__ErrorOrigin__c, COUNT(Id)
FROM blng__ErrorLog__c
GROUP BY blng__ErrorCode__c, blng__ErrorName__c, blng__ErrorOrigin__c
```
Useful when troubleshooting a stuck Order/OrderItem activation batch — see
the Migration Playbook's Contract/Order/OrderItem notes.
