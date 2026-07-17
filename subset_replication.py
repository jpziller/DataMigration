"""Relationship-consistent subset replication (roadmap #34).

replicate() pulls one object at a time, independently filtered -- there
is no way to say "pull 50 pilot Accounts and only the Contacts/
Opportunities/Cases that actually belong to those 50" without hand-
writing matching --where clauses across every object, with real risk of
an orphaned child row if the filters don't line up exactly.

replicate_subset() reuses this project's own load_order.py dependency
graph (the same one analyze-load-order and snowfakery_data.py already
reuse) in-memory only, the same way snowfakery_data.py does -- no
dbo.ObjectDependency/ObjectLoadOrder persistence needed here either.
The root object gets the caller's own --where/--limit; every other named
object is constrained to rows whose in-scope parent lookup(s) point at
Ids this same run actually just replicated, read back from the mirror
table itself (the authoritative record of what was really written, not
a second live-org round-trip that could drift from it).
"""
import pandas as pd
from sqlalchemy import text

import load_order
import replicate as replicate_module
import sql_dialect

_IN_CHUNK_SIZE = 200  # same practical SOQL IN(...) limit bulkops.py's
                      # _resolve_external_ids_to_sf_id() already uses


def _quote_soql_value(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _in_clause(field, ids):
    """A SOQL `field IN (...)` fragment, chunked at _IN_CHUNK_SIZE and
    OR'd together if there are more ids than fit in one clause."""
    sorted_ids = sorted(ids)
    parts = []
    for i in range(0, len(sorted_ids), _IN_CHUNK_SIZE):
        chunk = sorted_ids[i:i + _IN_CHUNK_SIZE]
        quoted = ", ".join(_quote_soql_value(v) for v in chunk)
        parts.append(f"{field} IN ({quoted})")
    return "(" + " OR ".join(parts) + ")"


def _build_child_where(child_object, edges, replicated_ids):
    """A SOQL WHERE fragment constraining child_object to rows whose
    in-scope parent references all point within their respective
    already-replicated subsets, or None if no in-scope parent has been
    replicated yet for this object (it should replicate unconstrained).

    replicated_ids: {object_name: set-of-real-Ids-already-written}.

    Grouped by field first: a polymorphic field (multiple edges sharing
    one field, different parents) naturally unions every already-
    replicated parent's Ids under that one field key -- correct OR
    semantics for polymorphic lookups with no separate detection step.
    Different fields on the same child combine with AND -- a deliberate
    scope choice (a row must satisfy every named in-scope relationship,
    not just one), not the only possible interpretation.

    A parent whose own replicated subset is empty makes the WHOLE clause
    guaranteed-empty for that field (an empty IN() would be invalid
    SOQL) -- signaled by returning the sentinel string "" so the caller
    can skip the API call entirely rather than construct a fake
    always-false condition.
    """
    ids_by_field = {}
    for edge in edges:
        if edge["child"] != child_object or edge["parent"] == child_object:
            continue  # not this child, or a self-reference (same pass, not a gate)
        if edge["parent"] not in replicated_ids:
            continue  # parent out of scope, or not replicated yet
        ids_by_field.setdefault(edge["field"], set()).update(replicated_ids[edge["parent"]])

    if not ids_by_field:
        return None
    if any(not ids for ids in ids_by_field.values()):
        return ""  # a required parent subset was empty -- child must be too

    return " AND ".join(_in_clause(field, ids) for field, ids in sorted(ids_by_field.items()))


def _read_replicated_ids(engine, schema, object_name):
    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, object_name)
    with engine.connect() as cx:
        rows = cx.execute(text(f"SELECT Id FROM {qualified}")).fetchall()
    return {str(row[0]) for row in rows}


def replicate_subset(sf, engine, root_object, related_objects, stage_dir,
                      schema="dbo", where=None, limit=None, raw=False,
                      chunksize=50000):
    """Replicate root_object (filtered by where/limit, same as a plain
    replicate() call) plus every object in related_objects, each
    automatically constrained to rows related to what was actually
    replicated so far. Returns {object_name: row_count}, in the order
    objects were processed (root's own dependency-graph position, not
    necessarily first).
    """
    object_names = [root_object] + [o for o in related_objects if o != root_object]

    edges = load_order.build_dependency_edges(sf, object_names)
    result = load_order.compute_load_order(object_names, edges)
    if result["unresolved_cycles"]:
        raise ValueError(
            f"Cannot subset-replicate: unresolved dependency cycle(s) among "
            f"{object_names}: {result['unresolved_cycles']}. Remove one of the "
            "objects in a cycle from the request, or replicate it separately."
        )

    counts = {}
    replicated_ids = {}
    notes = {}

    for row in result["order"]:
        object_name = row["object"]
        if object_name == root_object:
            n = replicate_module.replicate(
                sf, engine, object_name, stage_dir, schema=schema,
                where=where, limit=limit, raw=raw, chunksize=chunksize,
            )
        else:
            child_where = _build_child_where(object_name, edges, replicated_ids)
            if child_where is None:
                notes[object_name] = "no relationship constraint applied (no in-scope parent replicated)"
                n = replicate_module.replicate(
                    sf, engine, object_name, stage_dir, schema=schema,
                    raw=raw, chunksize=chunksize,
                )
            elif child_where == "":
                notes[object_name] = "0 rows (parent subset empty)"
                replicate_module.create_table(
                    engine, object_name, getattr(sf, object_name).describe(),
                    schema=schema, raw=raw,
                )
                n = 0
            else:
                n = replicate_module.replicate(
                    sf, engine, object_name, stage_dir, schema=schema,
                    where=child_where, raw=raw, chunksize=chunksize,
                )
        counts[object_name] = n
        replicated_ids[object_name] = _read_replicated_ids(engine, schema, object_name)

    return counts, notes
