"""RecordType DeveloperName resolution for cross-org migration (roadmap #36).

RecordType Ids are org-specific and never portable across orgs -- a
RecordTypeId carried over from a source system (or a different org
entirely) almost never matches the *target* org's real Ids. Migrating
one today means either hand-building a per-migration Id-mapping table in
T-SQL, or -- more commonly -- it silently gets dropped or wrong without a
data architect specifically catching it.

Design, chosen directly over an alternative (automatic resolution inside
bulk_op(), matching how CumulusCI does it): a plain T-SQL reference table
the architect JOINs against themselves, matching this framework's
established "the transform script owns the logic" convention
(load_table_prep.py's sort/dupe-key checks), not new automatic bulkops
behavior. Deliberately simpler, at the cost of no built-in
unresolved-value guard -- writing the transform so an unmatched
DeveloperName surfaces as a visible NULL RecordTypeId (a LEFT JOIN, not an
INNER JOIN) is the architect's own responsibility, per hard rule 15.
"""
from datetime import datetime, timezone

from sqlalchemy import text


def _ensure_table(engine, schema):
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.RecordTypeMap', 'U') IS NULL "
            f"CREATE TABLE [{schema}].[RecordTypeMap] ("
            "Id NVARCHAR(18) NOT NULL, "
            "DeveloperName NVARCHAR(255) NOT NULL, "
            "Name NVARCHAR(255) NULL, "
            "SobjectType NVARCHAR(255) NOT NULL, "
            "IsActive BIT NULL, "
            "AnalyzedDate DATETIME2 NOT NULL, "
            "CONSTRAINT PK_RecordTypeMap PRIMARY KEY (SobjectType, DeveloperName));"
        ))


def resolve_record_types(sf, engine, object_name, schema="dbo"):
    """Query the target org's real RecordType rows for object_name and
    write them into [schema].[RecordTypeMap] -- a plain reference table a
    transform JOINs against by DeveloperName to populate RecordTypeId,
    instead of ever hand-copying a raw, org-specific Id from the source.
    Shared across every object in the project (like dbo.FieldProfile);
    replaces only object_name's own prior rows. Returns the row count."""
    _ensure_table(engine, schema)
    analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    records = sf.query(
        f"SELECT Id, DeveloperName, Name, IsActive FROM RecordType WHERE SobjectType = '{object_name}'"
    )["records"]

    with engine.begin() as cx:
        cx.execute(
            text(f"DELETE FROM [{schema}].[RecordTypeMap] WHERE SobjectType = :t"),
            {"t": object_name},
        )
        if records:
            cx.execute(
                text(
                    f"INSERT INTO [{schema}].[RecordTypeMap] "
                    "(Id, DeveloperName, Name, SobjectType, IsActive, AnalyzedDate) "
                    "VALUES (:id, :dev_name, :name, :sobject, :is_active, :analyzed_at)"
                ),
                [{
                    "id": r["Id"], "dev_name": r["DeveloperName"], "name": r.get("Name"),
                    "sobject": object_name, "is_active": r.get("IsActive"), "analyzed_at": analyzed_at,
                } for r in records],
            )

    return len(records)
