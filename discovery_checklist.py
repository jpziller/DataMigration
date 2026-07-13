"""Discovery question checklist generator (roadmap #60).

The companion to migration_brief.py (#59), running the other direction:
instead of *starting* from a discovery output, generates the questions an
architect should be *asking* during discovery, derived from what this
framework already knows how to check rather than a generic template a
human has to remember. Given a candidate object list:

  - risk_analyzer.py's analyze_object_risk() already finds active
    validation rules per object -- each one becomes a real question
    naming its ErrorDisplayField/ErrorMessage, not a generic "any
    validation rules?".
  - An object carrying RecordTypeId (the RecordType Resolution Rule,
    #15/#36) becomes "does the client use Record Types here, get the
    exact DeveloperName for each one in scope."
  - A reference field pointing at an object NOT yet in the candidate
    list becomes "confirm that object is in scope too, or that target
    records already exist for it" -- deliberately the OPPOSITE scoping
    load_order.py's own build_dependency_edges() uses (that function
    only records edges *within* scope; this generator needs exactly the
    ones *outside* it, so it reads describe() directly rather than
    reusing that function against its own grain).

Mostly a new presentation layer over data risk_analyzer.py/describe()
already fetch, not a new integration -- the value is turning "what
should I ask" into something derived from the org's actual complexity
signals, not memory or a generic checklist template. Purely read-only
against Salesforce (describe() + a live Tooling API risk scan per
object) -- no engine/mirror-DB dependency at all, so this can run before
the SQL Server side of a project even exists yet, during discovery
itself.

Plain Markdown output for v1, same "ship the simple version, decide on
polish later" discipline as #52/#66's own v1 framing -- landing
questions as starter rows in a Migration Run Book's Pre-Migration phase
instead (or in addition) remains a future enhancement, not built here.
"""
from simple_salesforce.exceptions import SalesforceResourceNotFound

import risk_analyzer


def _out_of_scope_dependencies(sf, object_name, in_scope_names):
    """Reference field targets on object_name that aren't in
    in_scope_names and aren't a self-reference -- the deliberately
    inverted scoping load_order.build_dependency_edges() doesn't do."""
    desc = getattr(sf, object_name).describe()
    out_of_scope = set()
    for field in desc["fields"]:
        if field["type"] != "reference":
            continue
        for target in field.get("referenceTo") or []:
            if target != object_name and target not in in_scope_names:
                out_of_scope.add(target)
    return sorted(out_of_scope)


def _has_record_type_id(sf, object_name):
    desc = getattr(sf, object_name).describe()
    return any(f["name"] == "RecordTypeId" for f in desc["fields"])


def generate_discovery_checklist(sf, object_names):
    """Return [{"object", "questions": [...], "risk_summary": {...} or
    None}, ...] in the order given. "questions" is a plain-English list
    derived from real, live org signals -- empty for an object with none
    of the three signals below, not padded with generic filler.

    An object that isn't real (typo, not deployed, removed) gets
    "risk_summary": None and a single problem-report question instead of
    crashing the whole checklist -- found in review: analyze_object_risk()
    alone can't detect this (its own Tooling/Query API calls for a
    nonexistent object just come back empty, not an error, since each is
    independently wrapped in its own try/except), so a real describe()
    call is the actual existence check here, same as
    migration_brief.py's own _confirm_objects_exist()."""
    in_scope = set(object_names)
    checklist = []

    for object_name in object_names:
        try:
            getattr(sf, object_name).describe()
        except (SalesforceResourceNotFound, AttributeError, TypeError):
            checklist.append({
                "object": object_name,
                "questions": [
                    f"'{object_name}' is not a valid object name in this org (typo, not deployed, "
                    "removed, or not a real object name at all) -- fix it and re-run."
                ],
                "risk_summary": None,
            })
            continue

        risk = risk_analyzer.analyze_object_risk(sf, object_name)
        active_rules = [r for r in risk["validation_rules"] if r.get("Active")]

        questions = []
        if active_rules:
            questions.append(
                f"{len(active_rules)} active validation rule(s) found on {object_name}:"
            )
            for r in active_rules:
                name = r.get("ValidationName") or r.get("Id") or "(unnamed)"
                field = r.get("ErrorDisplayField")
                message = r.get("ErrorMessage") or "no error message on file"
                if field:
                    questions.append(
                        f"  - '{name}': confirm source data will satisfy '{field}' -- {message}"
                    )
                else:
                    questions.append(f"  - '{name}': confirm source data will satisfy this rule -- {message}")

        if _has_record_type_id(sf, object_name):
            questions.append(
                f"Does the client use Record Types on {object_name}? Get the exact DeveloperName "
                "for each one in scope (the RecordType Resolution Rule, #15/#36)."
            )

        for parent in _out_of_scope_dependencies(sf, object_name, in_scope):
            questions.append(
                f"{object_name} depends on {parent}, which isn't in this candidate list yet -- "
                f"confirm {parent} is in scope too, or that target {parent} records already exist "
                "in the org for this migration to reference."
            )

        checklist.append({
            "object": object_name,
            "questions": questions,
            "risk_summary": {
                "active_validation_rules": len(active_rules),
                "apex_triggers": len(risk["apex_triggers"]),
                "workflow_rules": len(risk["workflow_rules"]),
                "active_flows": risk["active_flow_count"],
                "approval_processes": len(risk["approval_processes"]),
            },
        })

    return checklist


def format_discovery_checklist_markdown(checklist):
    """Render generate_discovery_checklist()'s result as a plain
    Markdown document, ready to write straight to a .md file."""
    lines = ["# Discovery Checklist", ""]
    for entry in checklist:
        lines.append(f"## {entry['object']}")
        lines.append("")
        s = entry["risk_summary"]
        if s is not None:
            lines.append(
                f"*{s['active_validation_rules']} active validation rule(s), {s['apex_triggers']} Apex "
                f"trigger(s), {s['active_flows']} active record-triggered flow(s), {s['workflow_rules']} "
                f"legacy workflow rule(s), {s['approval_processes']} approval process(es).*"
            )
            lines.append("")
        if entry["questions"]:
            for q in entry["questions"]:
                lines.append(f"- {q}" if not q.startswith("  ") else q)
        else:
            lines.append("No specific questions surfaced from live org signals for this object.")
        lines.append("")
    return "\n".join(lines)
