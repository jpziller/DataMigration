"""Migration brief intake / project bootstrap (roadmap #59).

Closes the hand-off gap between upstream client discovery (the
architect, often with another AI session's help -- use cases, which
objects need migrating, special requirements) and this framework's own
build/validate/run tooling. Today that hand-off is a cold start: nothing
here reads a discovery output, so the architect re-types the object list
into the first describe()/analyze-load-order call by hand.

The brief format is deliberately minimal for v1 -- YAML, not a rigid
schema, since a real discovery session hasn't shown yet what's actually
useful beyond the basics (same "start empty, grow from real usage"
discipline as reference/field_synonyms.json):

    project: Acme Migration
    ticket: PROJ-123
    target_org_alias: ACME_UAT
    objects:
      - name: Account
        notes: Primary account records, ~5000 rows expected
      - name: Contact
        notes: Linked to Account via AccountId

bootstrap_project() does the boring, mechanical first pass and nothing
more: confirms every named object is real via live describe() (a typo or
a renamed object surfaces immediately, not three commands later), runs
analyze-load-order (#2) across the objects that ARE real, and scaffolds
a Migration Run Book (#16) with that object list already wired in.
Deliberately does NOT try to guess mapping, field lists, or transform
logic from the brief's own notes -- that's still generate-mapping-doc/
auto-map's job, on the real source tables, once they exist (same
first-pass-only scope discipline as auto_mapper.py, Hard Rule 11). The
brief's "ticket" field is reported back, not force-fit into
generate_migration_run_book()'s own ticket_url/ticket_label header
fields (a project-level ticket-SYSTEM link/name, not one specific
ticket number) -- it's a reminder for the Script Ticket Traceability
Rule (#10) once real transform scripts get built, not a Run Book field.
"""
import yaml
from simple_salesforce.exceptions import SalesforceResourceNotFound

import load_order
import migration_run_book


def parse_migration_brief(brief_path):
    """Read and lightly validate a migration brief YAML file.

    Returns {"project", "ticket", "target_org_alias", "objects":
    [{"name", "notes"}, ...]}. Raises ValueError on a structurally
    invalid brief (no "objects" list, or an entry with no name) -- never
    guesses a missing field."""
    with open(brief_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not data.get("objects"):
        raise ValueError(f"{brief_path} has no 'objects' list -- nothing to bootstrap.")

    objects = []
    for entry in data["objects"]:
        if isinstance(entry, str):
            objects.append({"name": entry, "notes": None})
        elif isinstance(entry, dict) and entry.get("name"):
            objects.append({"name": entry["name"], "notes": entry.get("notes")})
        else:
            raise ValueError(
                f"Invalid object entry in {brief_path}: {entry!r} -- each must be a plain "
                "name string or a mapping with at least a 'name' key."
            )

    return {
        "project": data.get("project"),
        "ticket": data.get("ticket"),
        "target_org_alias": data.get("target_org_alias"),
        "objects": objects,
    }


def _confirm_objects_exist(sf, object_names):
    """Confirm every name in object_names is a real object via live
    describe(). Returns (valid_names, problems) -- problems is a list of
    plain-English strings for anything that isn't real (typo, removed,
    not deployed).

    Also catches AttributeError/TypeError, not just
    SalesforceResourceNotFound (found in review): a brief object name
    that happens to collide with a real Python attribute (e.g. a name
    typo'd as "__class__") passes getattr() without raising at all --
    simple_salesforce's own __getattr__ is only ever consulted as a
    fallback, after normal attribute lookup already succeeds -- so the
    resulting object has no .describe() method and raises AttributeError
    instead. A non-string name (a YAML value like `name: 123` parsing to
    an int) raises TypeError from getattr() itself. Both are reported as
    the same "not a real object" problem, never left to crash the whole
    bootstrap over one malformed brief entry."""
    valid, problems = [], []
    for name in object_names:
        try:
            getattr(sf, name).describe()
            valid.append(name)
        except (SalesforceResourceNotFound, AttributeError, TypeError):
            problems.append(f"'{name}' is not a valid object name in this org (typo, not deployed, removed, or not a real object name at all).")
    return valid, problems


def bootstrap_project(sf, engine, brief_path, run_book_path, tab_name,
                       schema="dbo", configured_org_alias=None):
    """Read brief_path, confirm every named object is real, run
    analyze-load-order across the valid ones, and scaffold a Migration
    Run Book tab with that object list wired in.

    configured_org_alias: the org alias this session is actually
    connected to (Settings.sf_org_alias) -- compared against the
    brief's own target_org_alias, if given, purely as a warning (Hard
    Rule 2's spirit: confirm the target org) -- never blocks the
    bootstrap, since a brief written before the exact alias was
    finalized is a normal, non-error state.

    Returns {"project", "ticket", "org_alias_warning", "valid_objects",
    "problems", "load_order", "run_book_path"} -- run_book_path is None
    if no object was valid (nothing to scaffold)."""
    brief = parse_migration_brief(brief_path)
    object_names = [o["name"] for o in brief["objects"]]

    valid_objects, problems = _confirm_objects_exist(sf, object_names)

    org_alias_warning = None
    if brief["target_org_alias"] and configured_org_alias and brief["target_org_alias"] != configured_org_alias:
        org_alias_warning = (
            f"Brief says target org alias '{brief['target_org_alias']}', but this session is "
            f"connected to '{configured_org_alias}' -- confirm this is the intended target org."
        )

    load_order_result = None
    scaffolded_run_book_path = None
    if valid_objects:
        load_order_result = load_order.analyze_load_order(sf, engine, valid_objects, schema=schema)
        migration_run_book.generate_migration_run_book(
            run_book_path, tab_name, engine=engine, object_names=valid_objects, schema=schema,
            project_name=brief["project"], target_env=configured_org_alias,
        )
        scaffolded_run_book_path = run_book_path

    return {
        "project": brief["project"], "ticket": brief["ticket"],
        "org_alias_warning": org_alias_warning,
        "valid_objects": valid_objects, "problems": problems,
        "load_order": load_order_result, "run_book_path": scaffolded_run_book_path,
    }
