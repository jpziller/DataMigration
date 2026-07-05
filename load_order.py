"""Load-order dependency analysis.

Reads describe() for a set of objects, builds a dependency graph from their
lookup/master-detail reference fields, and computes a recommended load order
(parents before children) via topological sort. Results are written to
dbo.ObjectDependency (the raw edges) and dbo.ObjectLoadOrder (the computed
order) so other scripts/transforms can query them instead of re-deriving the
graph from describe() every time.

Self-referencing fields (e.g. Account.ParentId -> Account) don't block
ordering -- they just mean that field needs a two-pass load (insert without
it, then update it in). Genuine multi-object cycles (A -> B -> A through two
different objects) can't be safely auto-resolved, so they're flagged rather
than guessed at.
"""
from datetime import datetime, timezone

from sqlalchemy import text


def build_dependency_edges(sf, object_names):
    """Return a list of dependency edges among the given objects.

    Each edge: {child, parent, field, is_master_detail, is_nillable}.
    Only reference fields whose target is also in object_names are recorded
    -- dependencies outside the requested scope aren't tracked.
    """
    in_scope = set(object_names)
    edges = []

    for object_name in object_names:
        desc = getattr(sf, object_name).describe()
        for field in desc["fields"]:
            if field["type"] != "reference":
                continue
            for target in field.get("referenceTo") or []:
                if target not in in_scope:
                    continue
                edges.append({
                    "child": object_name,
                    "parent": target,
                    "field": field["name"],
                    "is_master_detail": field.get("relationshipOrder") is not None,
                    "is_nillable": bool(field.get("nillable", True)),
                })

    return edges


def compute_load_order(object_names, edges):
    """Topologically sort object_names using edges (child depends on parent).

    Returns a dict: {
        "order": [{"object", "level", "sequence"}, ...],   # parents-first
        "self_references": {object: [field, ...]},
        "unresolved_cycles": [[object, ...], ...],          # objects that
                                                              # couldn't be
                                                              # ordered
    }
    """
    self_references = {}
    parents_of = {name: set() for name in object_names}

    for edge in edges:
        if edge["child"] == edge["parent"]:
            self_references.setdefault(edge["child"], []).append(edge["field"])
            continue
        parents_of[edge["child"]].add(edge["parent"])

    remaining = set(object_names)
    ordered = []
    level = 0

    while remaining:
        # Objects whose remaining (unordered) parents are all already placed.
        ready = sorted(
            name for name in remaining
            if not (parents_of[name] & remaining)
        )
        if not ready:
            break  # everything left is part of an unresolved cycle
        for name in ready:
            ordered.append({"object": name, "level": level})
        remaining -= set(ready)
        level += 1

    for i, row in enumerate(ordered, start=1):
        row["sequence"] = i

    unresolved_cycles = _group_cycle_members(remaining, parents_of)

    return {
        "order": ordered,
        "self_references": self_references,
        "unresolved_cycles": unresolved_cycles,
    }


def _group_cycle_members(remaining, parents_of):
    """Group leftover (un-orderable) objects into their connected cycles."""
    groups = []
    unseen = set(remaining)
    while unseen:
        start = unseen.pop()
        group = {start}
        frontier = {start}
        while frontier:
            next_frontier = set()
            for node in frontier:
                related = (parents_of[node] & remaining) | {
                    other for other in remaining if node in parents_of[other]
                }
                next_frontier |= related - group
            group |= next_frontier
            frontier = next_frontier
        unseen -= group
        groups.append(sorted(group))
    return groups


def write_to_sql(engine, object_names, edges, result, schema="dbo"):
    analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.ObjectDependency', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[ObjectDependency];"
        ))
        cx.execute(text(
            f"CREATE TABLE [{schema}].[ObjectDependency] ("
            "ChildObject NVARCHAR(255) NOT NULL, "
            "ParentObject NVARCHAR(255) NOT NULL, "
            "LookupField NVARCHAR(255) NOT NULL, "
            "IsMasterDetail BIT NOT NULL, "
            "IsNillable BIT NOT NULL, "
            "AnalyzedDate DATETIME2 NOT NULL);"
        ))
        if edges:
            cx.execute(
                text(
                    f"INSERT INTO [{schema}].[ObjectDependency] "
                    "(ChildObject, ParentObject, LookupField, IsMasterDetail, IsNillable, AnalyzedDate) "
                    "VALUES (:child, :parent, :field, :is_master_detail, :is_nillable, :analyzed_at)"
                ),
                [{**edge, "analyzed_at": analyzed_at} for edge in edges],
            )

        cx.execute(text(
            f"IF OBJECT_ID('{schema}.ObjectLoadOrder', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[ObjectLoadOrder];"
        ))
        cx.execute(text(
            f"CREATE TABLE [{schema}].[ObjectLoadOrder] ("
            "ObjectName NVARCHAR(255) NOT NULL PRIMARY KEY, "
            "LoadLevel INT NULL, "
            "LoadSequence INT NULL, "
            "HasSelfReference BIT NOT NULL, "
            "SelfReferenceFields NVARCHAR(500) NULL, "
            "InUnresolvedCycle BIT NOT NULL, "
            "CycleMembers NVARCHAR(500) NULL, "
            "AnalyzedDate DATETIME2 NOT NULL);"
        ))

        cycle_by_object = {}
        for group in result["unresolved_cycles"]:
            for name in group:
                cycle_by_object[name] = [m for m in group if m != name]

        ordered_by_object = {row["object"]: row for row in result["order"]}
        rows = []
        for name in object_names:
            ordered_row = ordered_by_object.get(name)
            self_ref_fields = result["self_references"].get(name)
            cycle_members = cycle_by_object.get(name)
            rows.append({
                "object_name": name,
                "level": ordered_row["level"] if ordered_row else None,
                "sequence": ordered_row["sequence"] if ordered_row else None,
                "has_self_ref": self_ref_fields is not None,
                "self_ref_fields": ",".join(self_ref_fields) if self_ref_fields else None,
                "in_cycle": cycle_members is not None,
                "cycle_members": ",".join(cycle_members) if cycle_members else None,
                "analyzed_at": analyzed_at,
            })

        cx.execute(
            text(
                f"INSERT INTO [{schema}].[ObjectLoadOrder] "
                "(ObjectName, LoadLevel, LoadSequence, HasSelfReference, SelfReferenceFields, "
                "InUnresolvedCycle, CycleMembers, AnalyzedDate) "
                "VALUES (:object_name, :level, :sequence, :has_self_ref, :self_ref_fields, "
                ":in_cycle, :cycle_members, :analyzed_at)"
            ),
            rows,
        )


def analyze_load_order(sf, engine, object_names, schema="dbo"):
    edges = build_dependency_edges(sf, object_names)
    result = compute_load_order(object_names, edges)
    write_to_sql(engine, object_names, edges, result, schema=schema)
    return result
