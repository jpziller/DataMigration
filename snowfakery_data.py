"""Relationship-aware mock data generation via Snowfakery (roadmap #6).

`mock_data.py` generates independently random rows for one object at a
time -- there's no way to get, say, 10 Accounts each with 3 Contacts that
actually reference those specific Accounts. This module is that second,
relationship-aware backend: it builds a Snowfakery YAML recipe from the
same describe()-driven field mapping approach as `mock_data.py`, nesting
child objects inside their parent using this framework's own load-order
dependency graph (`load_order.py`) rather than re-deriving relationships
from describe() a second time, then runs the recipe and loads each
object's rows into `<Object>_Mock` -- same table-naming convention as the
single-object path, so a `*_Load` transform built against it doesn't care
which backend produced the mock data.

Requires the `snowfakery` package (new dependency, see requirements.txt).
Not wired into `bulkops` -- same boundary `mock_data.py` already documents:
this only gets mock data into `*_Mock` tables, building the `*_Load`
transform (including assigning a real unique migration key) is a manual
next step.

RECIPE SHAPE, confirmed live against Snowfakery 4.2 (not assumed from
docs alone):
  - A no-param fake value: `fake: Company`.
  - A parameterized fake value: `fake.RandomInt: {min: 0, max: 1000}`
    (dotted key, PascalCase is case-insensitive but used here for
    readability) -- NOT `fake: {RandomInt: {...}}`, which raises
    DataGenNameError.
  - Picklist-style fixed choices: `random_choice: [A, B, C]`.
  - A child object nested under a parent's `fields:` key becomes that
    parent's child in the flat JSON output; the *parent's* own record
    gets a spurious field named after the nesting key holding just the
    child count (not a list) -- so nesting keys here are always prefixed
    `_children_<ChildObject>` to make them trivially droppable afterward.
  - A child's explicit `reference: <Object>` field resolves to that
    parent's internal integer id within the current nesting context.
  - A secondary (non-primary, non-nested) parent link uses
    `random_reference: <Object>` instead -- picks a random already-
    generated row of that type, since only one relationship per object
    can be expressed via containment.
"""
import os
from datetime import datetime

import pandas as pd
import yaml
from snowfakery import generate_data
from sqlalchemy import text

import load_order as lo
import sql_dialect
from mock_data import _UNSUPPORTED_TYPES, _DATA_DOT_COM_FIELDS, _is_interdependent_field, truncate_to_field_lengths
from type_map import is_compound

_NAME_HINTS = [
    (("firstname",), "FirstName"),
    (("lastname",), "LastName"),
    (("email",), "Email"),
    (("phone", "fax"), "PhoneNumber"),
    (("website", "url"), "Url"),
    (("city",), "City"),
    (("state", "province"), "StateAbbr"),
    (("postalcode", "zip"), "Postcode"),
    (("country",), "CountryCode"),
    (("street", "address"), "StreetAddress"),
    (("description", "note", "comment"), "Paragraph"),
    (("name",), "Company"),
]


def _snowfakery_field(field):
    """Map one SF describe field to a Snowfakery field-value dict, or None
    if there's no reasonable mapping (mirrors mock_data._mockaroo_field's
    role, targeting Snowfakery's fake:/random_choice: syntax instead of
    Mockaroo's JSON schema)."""
    name = field["name"]
    sf_type = field["type"]

    if sf_type == "double" and name.lower().endswith(("latitude", "longitude")):
        # Same policy as mock_data.py: rarely populated by clients, not
        # worth mocking just to prove a field can be filled.
        return None

    if sf_type == "boolean":
        return {"fake": "Boolean"}
    if sf_type == "int":
        return {"fake.RandomInt": {"min": 0, "max": 1000}}
    if sf_type in ("double", "currency", "percent"):
        # Respect real precision/scale, same reasoning as mock_data.py's
        # equivalent branch -- a flat range would overflow a tightly
        # scaled decimal column.
        precision = field.get("precision") or 0
        scale = field.get("scale") or 2
        integer_digits = max(precision - scale, 1) if precision else 5
        return {"fake.Pyfloat": {
            "left_digits": min(integer_digits, 5),
            "right_digits": min(scale, 2) if scale else 2,
            "positive": True,
        }}
    if sf_type == "date":
        return {"fake.DateBetween": {"start_date": "-3y", "end_date": "+1y"}}
    if sf_type == "datetime":
        return {"fake.DateTimeBetween": {"start_date": "-3y", "end_date": "+1y"}}
    if sf_type == "time":
        return {"fake": "Time"}
    if sf_type == "phone":
        return {"fake": "PhoneNumber"}
    if sf_type == "email":
        return {"fake": "Email"}
    if sf_type == "url":
        return {"fake": "Url"}
    if sf_type in ("picklist", "combobox"):
        # combobox (e.g. Task.Subject) carries real picklistValues too --
        # it just also accepts free text, unlike a restricted picklist.
        # Picking a real value is still a reasonable mock, confirmed live.
        values = [v["value"] for v in field.get("picklistValues", []) if v.get("active", True)]
        if values:
            return {"random_choice": values}
        return {"fake": "Word"}
    if sf_type in ("string", "textarea", "id"):
        lowered = name.lower()
        for keywords, faker_type in _NAME_HINTS:
            if any(k in lowered for k in keywords):
                return {"fake": faker_type}
        return {"fake": "Word"}

    return None


def _fix_snowfakery_datetime_strings(df, mapped_fields):
    """Snowfakery's own JSON output serializes a fake.DateTimeBetween value
    via Python's default str(datetime) representation -- space-separated,
    tz-aware (e.g. "2024-07-29 22:38:35+00:00") -- confirmed live: this is
    a genuine XSD dateTime parse failure against Salesforce's Bulk API
    ("is not a valid value for the type xsd:dateTime"), not merely
    non-canonical, and it's baked into the raw JSON before pandas/
    sql_dialect.py's own dtype-based normalize_datetime_columns() ever
    gets a chance to see a real datetime64 column -- pandas reads it as a
    plain string. Reformat every field the real describe() says is
    "datetime" specifically (not a heuristic), via
    datetime.fromisoformat() (accepts the space-separated form) round-
    tripped through .isoformat() (defaults to 'T')."""
    df = df.copy()
    for field in mapped_fields:
        if field["type"] != "datetime":
            continue
        name = field["name"]
        if name not in df.columns:
            continue
        df[name] = df[name].map(
            lambda v: datetime.fromisoformat(v).isoformat() if isinstance(v, str) and v else v
        )
    return df


def _parse_datetime_fields_to_real_datetime64(df, mapped_fields):
    """Parse every real describe()-"datetime" field still holding a plain
    string (as left by _fix_snowfakery_datetime_strings(), which only fixes
    the separator, not the dtype) into a real, tz-naive pandas datetime64
    column.

    sql_dialect.py's own normalize_datetime_columns() only acts on a
    genuine datetime64 column -- MssqlDialect's is a documented no-op,
    relying on "pyodbc's own native datetime handling already round-trips a
    real Python/pandas datetime object into DATETIME2 correctly." A plain
    string parameter bound against a DATETIME2 column instead breaks
    pyodbc's fast_executemany outright (mssql "Invalid character value for
    cast specification") -- confirmed via a minimal repro, not assumed;
    found via a real dogfood run, not a synthetic test. Tz-naive
    specifically: DATETIME2 has no offset component, and a tz-aware
    Timestamp bound via fast_executemany separately breaks with a
    different error ("String data, right truncation"), also confirmed via
    repro. Parsing here gives normalize_datetime_columns() what its own
    no-op already assumes: mssql passes the real datetime straight through
    to pyodbc; sqlite's own branch still re-stringifies it with the
    correct 'T' separator either way."""
    df = df.copy()
    for field in mapped_fields:
        if field["type"] != "datetime":
            continue
        name = field["name"]
        if name not in df.columns:
            continue
        df[name] = pd.to_datetime(df[name], errors="coerce", utc=True).dt.tz_localize(None)
    return df


def object_field_schema(sf, object_name):
    """Return (fields, skipped) for one object -- fields is a list of
    (describe_field, snowfakery_value_spec) tuples; skipped mirrors
    mock_data.mock_schema_for_object's (name, reason) shape."""
    desc = getattr(sf, object_name).describe()
    fields, skipped = [], []

    for field in desc["fields"]:
        if is_compound(field) or not field.get("createable"):
            continue
        if field["type"] in _UNSUPPORTED_TYPES:
            skipped.append((field["name"], field["type"]))
            continue
        if field["name"] in _DATA_DOT_COM_FIELDS:
            skipped.append((field["name"], "data.com"))
            continue
        if _is_interdependent_field(field["name"]):
            skipped.append((field["name"], "interdependent recurrence field, not mocked"))
            continue
        spec = _snowfakery_field(field)
        if spec is None:
            skipped.append((field["name"], field["type"]))
            continue
        fields.append((field, spec))

    return fields, skipped


def build_recipe(sf, object_names, counts, stage_dir="_stage"):
    """Build a Snowfakery recipe for object_names, nested by this
    framework's own load-order dependency graph, and write it to
    _stage/<objects>_recipe.yml.

    counts: {object_name: int | str} -- required for every name in object_names.
    A str value is passed through verbatim as a Snowfakery count expression
    (e.g. "${{random_number(min=1,max=2)}}", built by cli.py from a
    --count NAME=N-M range) for a random per-parent count instead of a
    fixed one.

    Returns (recipe_path, skipped_by_object, primary_parent,
    secondary_exact_parents, secondary_random_parents, fields_by_object,
    polymorphic_children).
    secondary_exact_parents[name] are additional in-scope parents that are
    already an ancestor of name's chosen primary parent -- these get an
    exact nested `reference:` (confirmed live: it resolves up the *entire*
    ancestor chain, not just the immediate parent), not a random one.
    secondary_random_parents[name] are additional parents NOT reachable
    that way -- a real, disclosed limitation, since Snowfakery's
    `random_reference` samples the whole object pool with no way to scope
    it to "only rows under the same primary parent." fields_by_object[name]
    is the list of real describe() field dicts actually included for that
    object, needed by run_recipe() to know which columns of the combined
    JSON output really belong to it. polymorphic_children[name] (only
    present for a child whose in-scope parents come from a single
    polymorphic reference field, e.g. Task.WhatId -> Account/Opportunity)
    is {"field", "targets", "extra_refs"} -- name does NOT appear in
    primary_parent/secondary_*_parents at all; it's nested once per target
    instead (a separate cohort per possible value, tagged with a literal
    `_ParentType` column so the transform can build a CASE per target),
    each cohort still carrying extra_refs the normal way.
    Raises ValueError on unresolved circular dependencies, a missing count,
    or more than one polymorphic reference field in scope for one child
    (not supported -- narrow the object list or build the recipe by hand).
    """
    missing_counts = [n for n in object_names if n not in counts]
    if missing_counts:
        raise ValueError(f"Missing --count for: {missing_counts}")

    edges = lo.build_dependency_edges(sf, object_names)
    result = lo.compute_load_order(object_names, edges)
    if result["unresolved_cycles"]:
        raise ValueError(
            f"Unresolved circular dependencies among {object_names}: "
            f"{result['unresolved_cycles']} -- can't auto-build a nested "
            f"recipe for objects that mutually depend on each other. "
            f"Narrow the object list or build the recipe by hand."
        )

    level_by_object = {row["object"]: row["level"] for row in result["order"]}
    self_ref_fields_by_object = result["self_references"]

    # Group edges by (child, field) to detect a genuinely polymorphic field
    # -- one field (e.g. Task.WhatId) with more than one in-scope target
    # (Account, Opportunity) means "one target OR the other, per row," not
    # "both simultaneously" the way two different fields pointing at two
    # different objects would (e.g. Opportunity's own AccountId + ContactId).
    # Conflating the two would wrongly force every mock row of a
    # polymorphic child to reference every target at once.
    field_targets_by_child = {}
    for edge in edges:
        if edge["child"] == edge["parent"]:
            continue  # self-reference, handled via self_ref_fields_by_object
        field_targets_by_child.setdefault(edge["child"], {}).setdefault(
            edge["field"], set()
        ).add(edge["parent"])

    polymorphic_field_by_child = {}
    for child, targets_by_field in field_targets_by_child.items():
        poly_fields = [f for f, targets in targets_by_field.items() if len(targets) > 1]
        if len(poly_fields) > 1:
            raise ValueError(
                f"{child} has more than one polymorphic reference field in scope "
                f"({poly_fields}) -- not supported, narrow the object list or "
                f"build the recipe by hand."
            )
        if poly_fields:
            polymorphic_field_by_child[child] = poly_fields[0]

    # Non-polymorphic parents only, per child -- a polymorphic child's other
    # (single-target) fields still flow through the normal primary/secondary
    # machinery below; its polymorphic field's own targets are handled
    # afterward instead, as separate cohorts (see below build_recipe logic).
    parents_by_child = {}
    for edge in edges:
        if edge["child"] == edge["parent"]:
            continue  # self-reference, handled via self_ref_fields_by_object
        if polymorphic_field_by_child.get(edge["child"]) == edge["field"]:
            continue
        parents_by_child.setdefault(edge["child"], set()).add(edge["parent"])

    # Choose each object's primary (nesting) parent as its DEEPEST in-scope
    # parent, not its shallowest -- confirmed live that a nested `reference:
    # <Object>` resolves up the *entire* ancestor chain, not just the
    # immediate parent, so nesting under the deepest parent maximizes the
    # chance that any *other* in-scope parent is already an ancestor of it.
    # Any additional parent that IS already an ancestor gets a plain nested
    # `reference:` too (exact, not random) -- `random_reference` is only a
    # fallback for a genuinely unrelated second parent (not itself an
    # ancestor of the chosen primary), where nothing better is possible.
    ancestors_of = {}  # object -> set of all its ancestors, built parent-first
    primary_parent, secondary_exact_parents, secondary_random_parents = {}, {}, {}
    for row in result["order"]:  # parents before children, guaranteed by load_order
        name = row["object"]
        parents = parents_by_child.get(name)
        if not parents:
            ancestors_of[name] = set()
            continue
        ordered_parents = sorted(parents, key=lambda p: (-level_by_object.get(p, 0), p))
        chosen = ordered_parents[0]
        primary_parent[name] = chosen
        chosen_ancestors = ancestors_of.get(chosen, set()) | {chosen}
        ancestors_of[name] = chosen_ancestors

        remaining = ordered_parents[1:]
        secondary_exact_parents[name] = [p for p in remaining if p in chosen_ancestors]
        secondary_random_parents[name] = [p for p in remaining if p not in chosen_ancestors]

    # A polymorphic child can't be nested under one single parent the normal
    # way (it needs one independent cohort per possible target -- see
    # build_node below), so pull it back out of the normal primary/
    # secondary bookkeeping. Its OTHER (non-polymorphic) parents, if any --
    # just computed above from the filtered parents_by_child -- become
    # "extra references" every cohort still needs to carry, e.g.
    # Task.WhoId -> Contact applies regardless of whether a given Task's
    # WhatId cohort landed under Account or Opportunity.
    polymorphic_extra_refs = {}
    for child in polymorphic_field_by_child:
        extra = [primary_parent[child]] if child in primary_parent else []
        extra += secondary_exact_parents.get(child, []) + secondary_random_parents.get(child, [])
        polymorphic_extra_refs[child] = extra
        primary_parent.pop(child, None)
        secondary_exact_parents.pop(child, None)
        secondary_random_parents.pop(child, None)

    skipped_by_object = {}
    fields_by_object = {}
    for name in object_names:
        fields, skipped = object_field_schema(sf, name)
        self_ref_fields = set(self_ref_fields_by_object.get(name, []))
        if self_ref_fields:
            fields = [(f, spec) for f, spec in fields if f["name"] not in self_ref_fields]
            skipped = skipped + [(f, "self-reference (two-pass load, not mocked)") for f in self_ref_fields]
        fields_by_object[name] = fields
        skipped_by_object[name] = skipped

    children_of = {}
    for child, parent in primary_parent.items():
        children_of.setdefault(parent, []).append(child)
    roots = [n for n in object_names if n not in primary_parent and n not in polymorphic_field_by_child]

    # One cohort entry per (polymorphic child, possible target) -- e.g.
    # Task appears once under Account and once under Opportunity, each a
    # fully independent nested node using the SAME --count expression (a
    # symmetric split, not a divided total), combining back into one
    # <Child>_Mock table afterward since Snowfakery tags every generated
    # row with its object name regardless of which nesting context
    # produced it.
    cohort_children_of = {}
    for child, field in polymorphic_field_by_child.items():
        for target in sorted(field_targets_by_child[child][field]):
            cohort_children_of.setdefault(target, []).append(child)

    def build_node(name, is_child):
        fields_yaml = {field["name"]: spec for field, spec in fields_by_object[name]}
        for secondary in secondary_exact_parents.get(name, []):
            # Already an ancestor of the chosen primary parent -- a plain
            # nested reference resolves to the *correct* (not random) row.
            fields_yaml[f"_SecondaryParentRef_{secondary}"] = {"reference": secondary}
        for secondary in secondary_random_parents.get(name, []):
            # Genuinely unrelated to the chosen primary parent -- no way to
            # pick a consistent one, so this is a real, disclosed limitation.
            fields_yaml[f"_SecondaryParentRef_{secondary}"] = {"random_reference": secondary}
        if is_child:
            fields_yaml["_ParentMockRef"] = {"reference": primary_parent[name]}
        for child in children_of.get(name, []):
            fields_yaml[f"_children_{child}"] = [build_node(child, is_child=True)]
        for child in cohort_children_of.get(name, []):
            fields_yaml[f"_children_{child}"] = [build_cohort_node(child, name)]
        return {"object": name, "count": counts[name], "fields": fields_yaml}

    def build_cohort_node(child, target_parent):
        """One polymorphic cohort of child, nested directly under
        target_parent -- e.g. Task nested under Account specifically.
        _ParentType records which target this cohort actually is, a
        literal Snowfakery accepts as a plain constant value (confirmed
        live), so the transform can build a WHEN _ParentType = '<Target>'
        CASE per possible target."""
        fields_yaml = {field["name"]: spec for field, spec in fields_by_object[child]}
        target_ancestors = ancestors_of.get(target_parent, set()) | {target_parent}
        for extra in polymorphic_extra_refs.get(child, []):
            if extra == target_parent:
                # Same object this cohort is already nested under (e.g.
                # Task's own separate AccountId field, alongside the
                # polymorphic WhatId that also targets Account) --
                # _ParentMockRef already points at this exact row, a
                # second column referencing it would just be redundant.
                continue
            if extra in target_ancestors:
                fields_yaml[f"_SecondaryParentRef_{extra}"] = {"reference": extra}
            else:
                fields_yaml[f"_SecondaryParentRef_{extra}"] = {"random_reference": extra}
        fields_yaml["_ParentMockRef"] = {"reference": target_parent}
        fields_yaml["_ParentType"] = target_parent
        return {"object": child, "count": counts[child], "fields": fields_yaml}

    recipe = [{"snowfakery_version": 3}] + [build_node(root, is_child=False) for root in roots]

    os.makedirs(stage_dir, exist_ok=True)
    recipe_path = os.path.join(stage_dir, "_".join(object_names) + "_recipe.yml")
    with open(recipe_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(recipe, fh, sort_keys=False, default_flow_style=False)

    polymorphic_children = {
        child: {
            "field": field,
            "targets": sorted(field_targets_by_child[child][field]),
            "extra_refs": polymorphic_extra_refs.get(child, []),
        }
        for child, field in polymorphic_field_by_child.items()
    }

    return (recipe_path, skipped_by_object, primary_parent, secondary_exact_parents,
            secondary_random_parents, fields_by_object, polymorphic_children)


def run_recipe(engine, recipe_path, object_names, fields_by_object, primary_parent=None,
                secondary_exact_parents=None, secondary_random_parents=None,
                polymorphic_children=None, schema="dbo", stage_dir="_stage"):
    """Run a recipe built by build_recipe() and load each object's rows
    into [schema].[<object_name>_Mock]. Returns {object_name: rows_written}.

    fields_by_object must be build_recipe()'s own return value for this
    exact recipe -- see its docstring. Required (not re-derived from
    describe() here) because Snowfakery's combined JSON output merges every
    object type's columns into one array (NaN-filled per row where
    irrelevant), and two different objects can coincidentally share a real
    describe() field name (e.g. Contact has its own non-createable `Name`
    field, same name as Account's own `Name`) -- re-deriving "does this
    column name exist on this object's describe() at all" would silently
    let another object's generated values leak in. Using the exact field
    list this recipe actually generated for each object avoids that
    entirely.

    primary_parent/secondary_exact_parents/secondary_random_parents/
    polymorphic_children are build_recipe()'s own other return values,
    needed for the same column-leakage reason: after filtering to one
    object's ROWS (`_table == name`), the DataFrame still carries every
    OTHER object's bookkeeping columns too (row-filtering doesn't drop
    columns from a pandas DataFrame built from the union of every record
    type) -- found via a real dogfood run, not a synthetic test: Task's
    own cohort-only columns (`_ParentType`, `_SecondaryParentRef_Contact`,
    `_SecondaryParentRef_Account`) were leaking into `Contact_Mock` as
    entirely-NULL columns, and an all-NULL column defeats pyodbc's
    fast_executemany type inference (mssql's `Invalid character value for
    cast specification`). Only the bookkeeping columns this exact object
    legitimately has are kept, computed from these four dicts rather than
    inferred from column presence.
    """
    os.makedirs(stage_dir, exist_ok=True)
    json_path = os.path.join(stage_dir, os.path.splitext(os.path.basename(recipe_path))[0] + ".json")
    generate_data(yaml_file=recipe_path, output_format="json", output_file=json_path)

    all_records = pd.read_json(json_path)
    rows_written = {}

    polymorphic_children = polymorphic_children or {}
    primary_parent = primary_parent or {}

    legit_secondary_parents = {}
    for name in object_names:
        legit_secondary_parents[name] = set(
            (secondary_exact_parents or {}).get(name, [])
        ) | set((secondary_random_parents or {}).get(name, []))
    for child, info in polymorphic_children.items():
        legit_secondary_parents[child] = legit_secondary_parents.get(child, set()) | set(info["extra_refs"])

    # _ParentMockRef only means something for an object that's actually
    # nested under a primary parent (a plain child) or a polymorphic
    # cohort child -- a root object (e.g. Account) never has this key set
    # on its own rows, but the column still appears in the merged
    # DataFrame because OTHER objects have it. _ParentType only means
    # something for a polymorphic cohort child (e.g. Task) -- no other
    # object ever sets it.
    has_parent_mock_ref = {name for name in object_names if name in primary_parent or name in polymorphic_children}
    has_parent_type = set(polymorphic_children)

    d = sql_dialect.for_engine(engine)

    for name in object_names:
        table_name = f"{name}_Mock"
        object_rows = all_records[all_records["_table"] == name].copy()
        if object_rows.empty:
            rows_written[name] = 0
            continue

        mapped_fields = [f for f, _spec in fields_by_object[name]]
        secondary_cols = [f"_SecondaryParentRef_{p}" for p in legit_secondary_parents.get(name, set())]
        bookkeeping_cols = ["id"]
        if name in has_parent_mock_ref:
            bookkeeping_cols.append("_ParentMockRef")
        if name in has_parent_type:
            bookkeeping_cols.append("_ParentType")
        keep_cols = [f["name"] for f in mapped_fields] + bookkeeping_cols + secondary_cols
        object_rows = object_rows[[c for c in keep_cols if c in object_rows.columns]].copy()
        object_rows = object_rows.rename(columns={"id": "_MockRowId"})

        # pd.read_json() above reads ALL object types' records at once --
        # any bookkeeping int column that's NaN for some OTHER object's
        # rows (e.g. _ParentMockRef is never set on a root object like
        # Account) gets upcast to float64 for the WHOLE DataFrame, and
        # that dtype survives even after filtering down to just this
        # object's own (never-NaN) rows: a real value like
        # _ParentMockRef=1 round-trips as the Python float 1.0, not the
        # int 1. Binding a float against a genuinely INT-typed SQL Server
        # column breaks pyodbc's fast_executemany parameter binding
        # (mssql "Invalid character value for cast specification") --
        # found via a real dogfood run, not a synthetic test. Cast to
        # pandas' nullable Int64 so a real value round-trips as a real
        # int and a missing one round-trips as NULL, not NaN-as-float.
        int_bookkeeping_cols = [c for c in ("_MockRowId", "_ParentMockRef", *secondary_cols)
                                 if c in object_rows.columns]
        for col in int_bookkeeping_cols:
            object_rows[col] = object_rows[col].astype("Int64")

        object_rows = truncate_to_field_lengths(object_rows, mapped_fields)
        object_rows = _fix_snowfakery_datetime_strings(object_rows, mapped_fields)
        object_rows = _parse_datetime_fields_to_real_datetime64(object_rows, mapped_fields)

        int_type = d.sf_type_to_sql({"type": "int"})
        extra_cols_sql = []
        if "_MockRowId" in object_rows.columns:
            extra_cols_sql.append(f"{d.quote_ident('_MockRowId')} {int_type} NULL")
        if "_ParentMockRef" in object_rows.columns:
            extra_cols_sql.append(f"{d.quote_ident('_ParentMockRef')} {int_type} NULL")
        if "_ParentType" in object_rows.columns:
            # A cohort discriminator string (e.g. "Account"/"Opportunity"),
            # not a mock row id -- text, not int_type.
            extra_cols_sql.append(f"{d.quote_ident('_ParentType')} {d.raw_text_type()} NULL")
        for secondary_col in [c for c in object_rows.columns if c.startswith("_SecondaryParentRef_")]:
            extra_cols_sql.append(f"{d.quote_ident(secondary_col)} {int_type} NULL")

        cols_sql = ",\n    ".join(
            [f'{d.quote_ident(f["name"])} {d.sf_type_to_sql(f)} NULL' for f in mapped_fields] + extra_cols_sql
        )
        qualified = d.qualify(schema, table_name)
        already_exists = d.table_exists(engine, schema, table_name)
        with engine.begin() as cx:
            if already_exists:
                cx.execute(text(f"DROP TABLE {qualified};"))
            cx.execute(text(f"CREATE TABLE {qualified} (\n    {cols_sql}\n);"))

        object_rows = d.normalize_datetime_columns(object_rows)
        object_rows.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)
        rows_written[name] = len(object_rows)

    return rows_written
