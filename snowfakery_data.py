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

import pandas as pd
import yaml
from snowfakery import generate_data
from sqlalchemy import text

import load_order as lo
from mock_data import _UNSUPPORTED_TYPES, _DATA_DOT_COM_FIELDS, truncate_to_field_lengths
from type_map import is_compound, sf_type_to_sql

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
    if sf_type == "picklist":
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

    counts: {object_name: int} -- required for every name in object_names.

    Returns (recipe_path, skipped_by_object, primary_parent,
    secondary_exact_parents, secondary_random_parents, fields_by_object).
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
    JSON output really belong to it.
    Raises ValueError on unresolved circular dependencies or a missing count.
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

    parents_by_child = {}
    for edge in edges:
        if edge["child"] == edge["parent"]:
            continue  # self-reference, handled via self_ref_fields_by_object
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
    roots = [n for n in object_names if n not in primary_parent]

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
        return {"object": name, "count": counts[name], "fields": fields_yaml}

    recipe = [{"snowfakery_version": 3}] + [build_node(root, is_child=False) for root in roots]

    os.makedirs(stage_dir, exist_ok=True)
    recipe_path = os.path.join(stage_dir, "_".join(object_names) + "_recipe.yml")
    with open(recipe_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(recipe, fh, sort_keys=False, default_flow_style=False)

    return (recipe_path, skipped_by_object, primary_parent, secondary_exact_parents,
            secondary_random_parents, fields_by_object)


def run_recipe(engine, recipe_path, object_names, fields_by_object, schema="dbo", stage_dir="_stage"):
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
    """
    os.makedirs(stage_dir, exist_ok=True)
    json_path = os.path.join(stage_dir, os.path.splitext(os.path.basename(recipe_path))[0] + ".json")
    generate_data(yaml_file=recipe_path, output_format="json", output_file=json_path)

    all_records = pd.read_json(json_path)
    rows_written = {}

    for name in object_names:
        table_name = f"{name}_Mock"
        object_rows = all_records[all_records["_table"] == name].copy()
        if object_rows.empty:
            rows_written[name] = 0
            continue

        mapped_fields = [f for f, _spec in fields_by_object[name]]
        keep_cols = [f["name"] for f in mapped_fields] + [
            c for c in ("id", "_ParentMockRef") if c in object_rows.columns
        ] + [c for c in object_rows.columns if c.startswith("_SecondaryParentRef_")]
        object_rows = object_rows[[c for c in keep_cols if c in object_rows.columns]].copy()
        object_rows = object_rows.rename(columns={"id": "_MockRowId"})

        object_rows = truncate_to_field_lengths(object_rows, mapped_fields)

        extra_cols_sql = []
        if "_MockRowId" in object_rows.columns:
            extra_cols_sql.append("[_MockRowId] INT NULL")
        if "_ParentMockRef" in object_rows.columns:
            extra_cols_sql.append("[_ParentMockRef] INT NULL")
        for secondary_col in [c for c in object_rows.columns if c.startswith("_SecondaryParentRef_")]:
            extra_cols_sql.append(f"[{secondary_col}] INT NULL")

        cols_sql = ",\n    ".join(
            [f'[{f["name"]}] {sf_type_to_sql(f)} NULL' for f in mapped_fields] + extra_cols_sql
        )
        with engine.begin() as cx:
            cx.execute(text(
                f"IF OBJECT_ID('{schema}.{table_name}', 'U') IS NOT NULL "
                f"DROP TABLE [{schema}].[{table_name}];"
            ))
            cx.execute(text(f"CREATE TABLE [{schema}].[{table_name}] (\n    {cols_sql}\n);"))

        object_rows.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)
        rows_written[name] = len(object_rows)

    return rows_written
