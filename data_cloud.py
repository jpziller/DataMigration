"""Data Cloud (D360) query and status tooling (roadmap #18).

Turns today's live-verified findings into real, reusable commands instead
of ad hoc scripts -- so a different data architect picking up this repo
later just runs a command, without needing to hand-derive the token
exchange or already know which standard object holds which status.

TWO GENUINELY DIFFERENT AUTH PATHS, confirmed live against a real Data
Cloud-provisioned org (`D360_PLAYGROUND`) -- mixing them up fails
silently or errors outright, the same lesson `risk_analyzer.py`'s build
already taught for a different pair of APIs:

1. **Status objects are plain core-org SOQL, same as any CRM object.**
   `MktCalculatedInsight`, `DataStream`, `IdentityResolution`, and
   `MktDataTransform` are all standard objects queryable through the
   *exact* same `sf.query()` this framework already uses everywhere else
   -- no Data Cloud tenant token needed. Confirmed live for all four.
2. **Actual Data Cloud row-level SQL querying (DMOs/DLOs beyond basic
   SOQL, and Calculated Insight *data*) needs a separate Data Cloud
   tenant token.** `get_data_cloud_session()` does the exchange (`POST
   {core-instance}/services/a360/token`, `grant_type=urn:salesforce:
   grant-type:external:cdp`) and returns a genuinely different
   instance_url/access_token pair -- confirmed live, this is not
   optional plumbing, the exchange really does fail without a connected
   app / External Client App that has Data Cloud OAuth scopes (`cdp_
   query_api` etc.) granted. See `README.md`'s jwt-mode note and
   `ROADMAP.md` #18 for the tested setup walkthrough -- the default `cli`
   auth mode's `sf`-provided connected app can never satisfy this.

Basic DLO/DMO lookups (finding #1) don't need any of this -- they already
work through `query_tool.py`'s existing `sf.query()` path unmodified.
This module is specifically for what that path *can't* do: the Data
Cloud tenant's own SQL query API, Calculated Insight metadata/data, and
status checks across the four monitoring objects above.
"""
import requests

from query_tool import run_query

STATUS_OBJECTS = {
    "calculated-insight": {
        "object": "MktCalculatedInsight",
        "fields": ["Id", "Name", "CalculatedInsightStatus", "LastRunStatus",
                   "LastRunStatusErrorCode", "LastRunDateTime"],
    },
    "data-stream": {
        "object": "DataStream",
        "fields": ["Id", "Name", "DataStreamStatus", "ImportRunStatus",
                   "LastRefreshDate", "TotalNumberOfRowsAdded",
                   "LastDataChangeStatusErrorCode", "ExternalStreamErrorCode"],
    },
    "identity-resolution": {
        "object": "IdentityResolution",
        "fields": ["Id", "Name", "Status", "LastRunStatus", "LastRunStatusDateTime",
                   "SourceCount", "MatchedCount", "UnifiedCount", "ConsolidationRate",
                   "ErrorCode", "ErrorMessage"],
    },
    "data-transform": {
        "object": "MktDataTransform",
        "fields": ["Id", "Name", "DataTransformStatus", "LastRunStatus", "LastRunTime",
                   "TargetObject", "LastDataChangeStatusErrorCode"],
    },
    "dso": {
        # DataLakeObjectInstance -- the actual DSO (raw ingested layer),
        # genuinely distinct from "data-stream" (the ingestion connector
        # that feeds it) -- confirmed live, both are real, separate
        # objects, not two names for the same thing.
        "object": "DataLakeObjectInstance",
        "fields": ["Id", "Name", "DataLakeObjectStatus", "SyncStatus", "HydrationStatus",
                   "LastRefreshDate", "TotalRecords", "ExternalObjectErrorStatus",
                   "ExternalObjectErrorCode", "LastDataChangeStatusErrorCode"],
    },
}


def check_status(sf, status_type, name=None):
    """Query one of the four standard Data Cloud monitoring objects above
    via plain core-org SOQL -- no Data Cloud tenant token needed. Returns
    the same (records, total_size, truncated) shape query_tool.run_query
    does, so cli.py's existing _print_table/--csv/--excel handling works
    unchanged.

    status_type: one of STATUS_OBJECTS' keys.
    name: optional exact Name filter (e.g. a specific Calculated Insight,
    Data Stream, Identity Resolution ruleset, or Data Transform).

    Identity Resolution's *resulting* Unified DMO rows (not just its run
    status) are a plain DMO like any other -- query it with `query` or
    `data-cloud-query` once you know its name, same as any DLO/DMO.
    """
    if status_type not in STATUS_OBJECTS:
        raise ValueError(
            f"Unknown status type {status_type!r}. Choose from: "
            f"{', '.join(STATUS_OBJECTS)}"
        )
    spec = STATUS_OBJECTS[status_type]
    soql = f"SELECT {', '.join(spec['fields'])} FROM {spec['object']}"
    if name:
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        soql += f" WHERE Name = '{escaped}'"
    return run_query(sf, soql)


def get_data_cloud_session(sf):
    """Exchange the current core-org session for a Data Cloud tenant
    access_token/instance_url pair. See this module's docstring -- this
    is a genuinely separate host/token from the core org's, required for
    anything beyond basic SOQL against DLOs/DMOs.

    Raises ValueError with a clear, actionable message on failure rather
    than letting a raw HTTP error surface -- the most common real cause
    (confirmed live) is a connected app with no Data Cloud OAuth scopes,
    not a user permission problem.
    """
    core_instance_url = f"https://{sf.sf_instance}"
    resp = requests.post(
        f"{core_instance_url}/services/a360/token",
        data={
            "grant_type": "urn:salesforce:grant-type:external:cdp",
            "subject_token": sf.session_id,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        },
    )
    if not resp.ok:
        body = resp.text
        if "invalid_scope" in body:
            raise ValueError(
                "Data Cloud token exchange failed with invalid_scope. This means the "
                "connected app / External Client App behind your current auth doesn't "
                "have Data Cloud OAuth scopes (cdp_query_api, etc.) granted -- this is "
                "an app-scope problem, not a user permission problem, and the default "
                "`cli` auth mode's sf-provided connected app can never satisfy it. See "
                "README.md's jwt-mode note and ROADMAP.md #18 for the tested setup "
                "(an External Client App with JWT Bearer Flow + those scopes + the "
                "refresh_token scope, non-obviously required even though JWT bearer "
                "flow doesn't use one)."
            )
        raise ValueError(f"Data Cloud token exchange failed ({resp.status_code}): {body}")

    body = resp.json()
    return body["access_token"], body["instance_url"]


def _rows_from_data_cloud_response(body):
    """Data Cloud's row-level query APIs don't agree on one response shape
    -- confirmed live, not assumed: /api/v2/query returns {"data": [[...]],
    "metadata": {"col": {"placeInOrder": N, ...}}} (a positional array,
    metadata required to know column order), but the Calculated Insight
    data endpoint returns {"data": [{...}], "metadata": {}} -- rows are
    already plain dicts and metadata is empty. Handle both rather than
    assume one -- zip against metadata only when a row isn't already a
    dict, matching whichever shape actually came back."""
    rows = body.get("data", [])
    if rows and isinstance(rows[0], dict):
        return rows
    columns = sorted(body.get("metadata", {}).items(), key=lambda kv: kv[1]["placeInOrder"])
    column_names = [name for name, _ in columns]
    return [dict(zip(column_names, row)) for row in rows]


def query_data_cloud(sf, sql):
    """Run ANSI SQL against the Data Cloud tenant's own query API
    (/api/v2/query -- confirmed live; NOT /api/v3/query, an earlier
    doc-only guess this framework's own research corrected). Returns the
    same (records, total_size, truncated) shape query_tool.run_query does.
    """
    token, instance_url = get_data_cloud_session(sf)
    resp = requests.post(
        f"https://{instance_url}/api/v2/query",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"sql": sql},
    )
    resp.raise_for_status()
    body = resp.json()
    records = _rows_from_data_cloud_response(body)
    return records, body.get("rowCount", len(records)), not body.get("done", True)


def list_calculated_insights(sf):
    """List every Calculated Insight's metadata (dimensions, measures,
    process timestamps) via GET /api/v1/insight/metadata -- confirmed
    live. Returns the parsed metadata list as-is (not the positional row
    format -- this endpoint is already a normal JSON list of dicts)."""
    token, instance_url = get_data_cloud_session(sf)
    resp = requests.get(
        f"https://{instance_url}/api/v1/insight/metadata",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json().get("metadata", [])


def query_calculated_insight(sf, ci_name):
    """Query a specific Calculated Insight's actual data via GET
    /api/v1/insight/calculated-insights/{ci_name} -- confirmed live
    (including the empty-but-valid response before a CI has finished
    processing). Returns the same (records, total_size, truncated) shape
    query_tool.run_query does."""
    token, instance_url = get_data_cloud_session(sf)
    resp = requests.get(
        f"https://{instance_url}/api/v1/insight/calculated-insights/{ci_name}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    body = resp.json()
    records = _rows_from_data_cloud_response(body)
    return records, len(records), not body.get("done", True)


def query_unified_profile(sf, data_model_name, filters, fields=None, limit=None, offset=None, orderby=None):
    """Look up Unified Profile data via GET /api/v1/profile/{dataModelName}
    -- finding #4, confirmed live. The CLI equivalent of Data Cloud's own
    Profile Explorer (pick a Data Space, an entity, an attribute,
    repeatedly) -- one shot instead.

    filters is REQUIRED by the API itself (confirmed live: omitting it
    entirely fails with a missing-parameter error regardless of
    data_model_name) -- this is a profile *lookup* API (find a known
    person/record), not a bulk browse endpoint. Syntax: `[Field=Value]`,
    equality only, AND-combined by comma-separating inside the brackets
    (`[FieldA=X,FieldB=Y]`) -- confirmed live, a second bracket group
    (`[FieldA=X],[FieldB=Y]`) works identically.

    No Data Space parameter needed in the API itself (unlike the Setup UI,
    which makes you pick one even when "default" is the only option) --
    confirmed live against this org, which only has one Data Space.

    fields: comma-separated string or a list -- omit for up to 10
    arbitrary fields per Salesforce's own documented default.
    """
    token, instance_url = get_data_cloud_session(sf)
    params = {"filters": filters}
    if fields:
        params["fields"] = ",".join(fields) if isinstance(fields, (list, tuple)) else fields
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if orderby:
        params["orderby"] = orderby

    resp = requests.get(
        f"https://{instance_url}/api/v1/profile/{data_model_name}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    resp.raise_for_status()
    body = resp.json()
    records = _rows_from_data_cloud_response(body)
    return records, len(records), not body.get("done", True)
