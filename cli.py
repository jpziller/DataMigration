"""Command-line entry point. Migration verbs: replicate, bulkops, describe.

Examples:
    python cli.py list-objects
    python cli.py describe Account
    python cli.py dump-describe Account
    python cli.py replicate Account
    python cli.py replicate Contact --where "CreatedDate = LAST_N_DAYS:30" --raw
    python cli.py bulkops Account insert Account_Load --key-column LoadId
    python cli.py bulkops Contact upsert Contact_Load --external-id Legacy_Id__c
    python cli.py bulkops-retry Contact_Load  # copies failed rows into Contact_Load_Retry for resubmission
    python cli.py analyze-load-order Account Contact Opportunity OpportunityLineItem
    python cli.py profile-salesforce Account
    python cli.py profile-sql-table Account
    python cli.py export-profile-excel profile.xlsx
    python cli.py query "SELECT Id, Name FROM Account LIMIT 10"
    python cli.py query "SELECT Id, Name, Account.Name FROM Contact" --csv out.csv
    python cli.py generate-mock-data Account --count 50
    python cli.py generate-mapping-doc Account mapping/Migration_Mapping.xlsx SourceAccounts
    python cli.py generate-mapping-doc Contact mapping/Migration_Mapping.xlsx SourceContacts  # same file -> adds a tab, doesn't overwrite
    python cli.py check-mapping-balance Account mapping/Migration_Mapping.xlsx sql/transformations/010_account_load.sql
    python cli.py auto-map Account mapping/Migration_Mapping.xlsx SourceAccounts
    python cli.py generate-solution-doc Solution.docx Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx
    python cli.py analyze-org-risk Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx
    python cli.py import-parquet ./data/accounts.parquet SourceAccounts
"""
import click
import pandas as pd
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from config import get_settings
from sf_client import connect_salesforce
from sql_client import make_engine
import metadata as md
import replicate as rep
import bulkops as bo
import batch_advisor as ba
import load_order as lo
import profiling as pf
import query_tool as qt
import data_cloud as dc
import mock_data as mkd
import snowfakery_data as sfd
import mapping_doc as mpd
import auto_mapper as am
import solution_doc as sd
import risk_analyzer as ra
import parquet_import as pqi
import run_book as rb


def _ctx():
    s = get_settings()
    return s, connect_salesforce(s), make_engine(s)


def _print_table(df, max_rows=50):
    """Render a DataFrame as a rich console table, truncated to max_rows."""
    if df.empty:
        return
    table = Table(show_lines=False)
    for col in df.columns:
        table.add_column(str(col))
    for _, row in df.head(max_rows).iterrows():
        table.add_row(*("" if pd.isna(v) else str(v) for v in row))
    Console().print(table)
    if len(df) > max_rows:
        Console().print(f"[dim]... {len(df) - max_rows} more row(s) not shown[/dim]")


@click.group()
def cli():
    pass


@cli.command("list-objects")
@click.option("--all", "show_all", is_flag=True, help="Include non-queryable objects.")
def list_objects(show_all):
    _, sf, _e = _ctx()
    for name, label, createable, updateable in md.list_objects(sf, queryable_only=not show_all):
        click.echo(f"{name:40} {label}")


@cli.command("describe")
@click.argument("object_name")
def describe(object_name):
    _, sf, _e = _ctx()
    click.echo(f"{'FIELD':30} {'TYPE':14} LEN  C U  REFERENCES / extId")
    for name, typ, length, createable, updateable, ref, ext in md.list_fields(sf, object_name):
        flags = f"{'Y' if createable else '-'} {'Y' if updateable else '-'}"
        extra = ref + (" [extId]" if ext else "")
        click.echo(f"{name:30} {typ:14} {str(length or ''):4} {flags}  {extra}")


@cli.command("dump-describe")
@click.argument("object_name")
def dump_describe(object_name):
    _, sf, _e = _ctx()
    click.echo(md.dump_describe(sf, object_name))


@cli.command("replicate")
@click.argument("object_name")
@click.option("--where", default=None, help="SOQL WHERE clause (no 'WHERE').")
@click.option("--schema", default="dbo")
@click.option("--raw", is_flag=True, help="All columns NVARCHAR(MAX); CAST later in T-SQL.")
def replicate_cmd(object_name, where, schema, raw):
    s, sf, engine = _ctx()
    n = rep.replicate(sf, engine, object_name, s.stage_dir,
                      schema=schema, where=where, raw=raw)
    click.echo(f"Replicated {n} rows into {schema}.{object_name}")


@cli.command("import-parquet")
@click.argument("parquet_path")
@click.argument("table_name")
@click.option("--schema", default="dbo")
@click.option("--append", is_flag=True, help="Add rows to an existing table instead of dropping/recreating it.")
def import_parquet_cmd(parquet_path, table_name, schema, append):
    _, _, engine = _ctx()
    n = pqi.import_parquet(engine, parquet_path, table_name, schema=schema, append=append)
    click.echo(f"Imported {n} row(s) into {schema}.{table_name}"
               f"{' (appended)' if append else ' (table recreated)'}")


@cli.command("bulkops")
@click.argument("object_name")
@click.argument("operation", type=click.Choice(["insert", "update", "upsert", "delete"]))
@click.argument("source_table")
@click.option("--external-id", default=None, help="External id field (upsert; also delete -- resolved to real Ids via a query first, since Bulk API 2.0's delete only ever accepts Id).")
@click.option("--key-column", default="LoadId", help="Local unique key for in-place writeback.")
@click.option("--schema", default="dbo")
@click.option("--email-deliverability", default=None,
              type=click.Choice(["no-access", "system-email-only", "all-email"]),
              help="Required for insert/upsert -- what Setup > Email Administration > Deliverability is currently set to (no API can read this; check manually first).")
@click.option("--confirm-external-email-risk", is_flag=True,
              help="Required in addition to --email-deliverability all-email, since that setting can send real outbound email to external contacts.")
@click.option("--batch-size", default="auto",
              help="Bulk API 2.0 records per job: 'auto' (default, recommend-batch-size's own logic), "
                   "'none' (one unchunked job), or an integer to pin a value yourself -- an explicit "
                   "number always wins and is never overridden.")
def bulkops_cmd(object_name, operation, source_table, external_id, key_column, schema,
                email_deliverability, confirm_external_email_risk, batch_size):
    s, sf, engine = _ctx()
    summary = bo.bulk_op(sf, engine, object_name, operation, source_table,
                         external_id=external_id, key_column=key_column,
                         schema=schema, stage_dir=s.stage_dir,
                         email_deliverability=email_deliverability,
                         confirm_external_email_risk=confirm_external_email_risk,
                         batch_size=batch_size)
    warnings = summary.pop("preflight_warnings", [])
    rationale = summary.pop("batch_size_rationale", [])
    if rationale:
        for line in rationale:
            click.echo(f"[batch-size] {line}")
    for k, v in summary.items():
        click.echo(f"{k:12}: {v}")
    if warnings:
        click.echo(f"Warning: required field(s) not sent (only fails if nothing else defaults them): {warnings}")


@cli.command("bulkops-retry")
@click.argument("table")
@click.option("--schema", default="dbo")
@click.option("--error-column", default="Error")
def bulkops_retry_cmd(table, schema, error_column):
    _, _, engine = _ctx()
    retry_table, count = bo.build_retry_table(engine, table, schema=schema, error_column=error_column)
    if count == 0:
        click.echo(f"No failed rows found in {schema}.{table} (column {error_column}) -- nothing to retry.")
    else:
        click.echo(f"Copied {count} failed row(s) from {schema}.{table} into {retry_table}")
        click.echo(f"Review it, then resubmit: python cli.py bulkops <Object> <operation> {retry_table.split('.')[-1]} ...")


@cli.command("enable-bulkops-logging")
@click.option("--schema", default="dbo", help="Schema to enable logging for -- each schema is opted in independently.")
def enable_bulkops_logging_cmd(schema):
    _, _, engine = _ctx()
    bo.enable_bulkops_logging(engine, schema=schema)
    click.echo(f"Bulk load logging enabled for schema '{schema}' -- {schema}.BulkOpsLog created.")
    click.echo("Every bulkops call against this schema will now log automatically; no per-call flag needed.")


@cli.command("disable-bulkops-logging")
@click.option("--schema", default="dbo", help="Schema to disable logging for.")
def disable_bulkops_logging_cmd(schema):
    _, _, engine = _ctx()
    click.echo(f"This permanently drops {schema}.BulkOpsLog and all of its history.")
    bo.disable_bulkops_logging(engine, schema=schema)
    click.echo(f"Bulk load logging disabled for schema '{schema}'.")


@cli.command("analyze-load-order")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--schema", default="dbo")
def analyze_load_order_cmd(object_names, schema):
    s, sf, engine = _ctx()
    result = lo.analyze_load_order(sf, engine, list(object_names), schema=schema)

    click.echo("Recommended load order (parents before children):")
    current_level = None
    for row in result["order"]:
        if row["level"] != current_level:
            current_level = row["level"]
            click.echo(f"  -- level {current_level} --")
        click.echo(f"  {row['sequence']:3}. {row['object']}")

    if result["self_references"]:
        click.echo("\nSelf-referencing fields (need a two-pass load: insert without it, then update it in):")
        for object_name, fields in result["self_references"].items():
            click.echo(f"  {object_name}: {', '.join(fields)}")

    if result["unresolved_cycles"]:
        click.echo("\nUnresolved circular dependencies (couldn't be auto-ordered -- resolve manually):")
        for group in result["unresolved_cycles"]:
            click.echo(f"  {', '.join(group)}")

    click.echo(f"\nWritten to {schema}.ObjectDependency and {schema}.ObjectLoadOrder")


def _print_profile_preview(engine, object_or_table, source_type, schema):
    # Deliberately narrow -- just enough to decide "does this field look
    # worth migrating" at a glance. Full detail (min/max, blank counts,
    # value distributions) is in dbo.FieldProfile/FieldProfileValues and
    # export-profile-excel, not crammed into a console preview.
    df = pd.read_sql(
        text(
            f"SELECT FieldName, DataType, PopulatedPct, DistinctCount "
            f"FROM [{schema}].[FieldProfile] "
            "WHERE ObjectOrTable = :name AND SourceType = :st ORDER BY FieldName"
        ),
        engine, params={"name": object_or_table, "st": source_type},
    )
    _print_table(df)


@cli.command("profile-salesforce")
@click.argument("object_name")
@click.option("--where", default=None, help="SOQL WHERE clause (no 'WHERE').")
@click.option("--schema", default="dbo")
@click.option("--top-n-values", default=50, help="Max distinct values to keep per low-cardinality field.")
def profile_salesforce_cmd(object_name, where, schema, top_n_values):
    s, sf, engine = _ctx()
    profiles, distributions = pf.profile_salesforce_object(
        sf, engine, object_name, where=where, schema=schema, top_n_values=top_n_values
    )
    click.echo(f"Profiled {len(profiles)} fields on {object_name} "
               f"({len(distributions)} with value distributions captured)")
    _print_profile_preview(engine, object_name, "salesforce", schema)
    click.echo(f"Results in {schema}.FieldProfile / {schema}.FieldProfileValues")


@cli.command("profile-sql-table")
@click.argument("table_name")
@click.option("--schema", default="dbo")
@click.option("--top-n-values", default=50, help="Max distinct values to keep per low-cardinality column.")
@click.option("--distinct-threshold", default=50, help="Columns with more distinct values than this skip value-distribution capture.")
def profile_sql_table_cmd(table_name, schema, top_n_values, distinct_threshold):
    _, _, engine = _ctx()
    profiles, distributions = pf.profile_sql_table(
        engine, table_name, schema=schema, top_n_values=top_n_values, distinct_threshold=distinct_threshold
    )
    click.echo(f"Profiled {len(profiles)} columns on {schema}.{table_name} "
               f"({len(distributions)} with value distributions captured)")
    _print_profile_preview(engine, table_name, "sql_table", schema)
    click.echo(f"Results in {schema}.FieldProfile / {schema}.FieldProfileValues")


@cli.command("export-profile-excel")
@click.argument("output_path")
@click.option("--schema", default="dbo")
@click.option("--object", "object_or_table", default=None, help="Limit export to one object/table.")
@click.option("--source-type", type=click.Choice(["salesforce", "sql_table"]), default=None)
def export_profile_excel_cmd(output_path, schema, object_or_table, source_type):
    _, _, engine = _ctx()
    path = pf.export_profile_to_excel(
        engine, output_path, schema=schema, object_or_table=object_or_table, source_type=source_type
    )
    click.echo(f"Wrote {path}")


@cli.command("query")
@click.argument("soql")
@click.option("--all", "fetch_all", is_flag=True, help="Fetch every matching record, not just the first page.")
@click.option("--csv", "csv_path", default=None, help="Write results to a CSV file instead of printing.")
@click.option("--excel", "excel_path", default=None, help="Write results to an Excel file instead of printing.")
@click.option("--max-print-rows", default=50, help="Console preview row cap (ignored for --csv/--excel).")
def query_cmd(soql, fetch_all, csv_path, excel_path, max_print_rows):
    _, sf, _e = _ctx()
    records, total_size, truncated = qt.run_query(sf, soql, fetch_all=fetch_all)
    _output_query_result(records, total_size, truncated, csv_path, excel_path, max_print_rows,
                         truncated_hint="Not all matching records were fetched -- pass --all "
                                        "to retrieve everything, or add/tighten a LIMIT.")


def _output_query_result(records, total_size, truncated, csv_path, excel_path, max_print_rows,
                         truncated_hint="Not all matching records were fetched."):
    if csv_path:
        qt.to_csv(records, csv_path)
        click.echo(f"Wrote {len(records)} row(s) to {csv_path}")
    elif excel_path:
        qt.to_excel(records, excel_path)
        click.echo(f"Wrote {len(records)} row(s) to {excel_path}")
    elif records:
        _print_table(pd.DataFrame(records), max_rows=max_print_rows)
    click.echo(f"\n{len(records)} of {total_size} total record(s) shown.")
    if truncated:
        click.echo(truncated_hint)


@cli.command("data-cloud-query")
@click.argument("sql")
@click.option("--csv", "csv_path", default=None, help="Write results to a CSV file instead of printing.")
@click.option("--excel", "excel_path", default=None, help="Write results to an Excel file instead of printing.")
@click.option("--max-print-rows", default=50, help="Console preview row cap (ignored for --csv/--excel).")
def data_cloud_query_cmd(sql, csv_path, excel_path, max_print_rows):
    """ANSI SQL against the Data Cloud tenant's own query API -- for
    complex/cross-object Data Cloud queries. Basic single-DLO/DMO lookups
    work fine through the plain `query` command already; reach for this
    one specifically when you need the Data Cloud tenant's own SQL engine."""
    _, sf, _e = _ctx()
    records, total_size, truncated = dc.query_data_cloud(sf, sql)
    _output_query_result(records, total_size, truncated, csv_path, excel_path, max_print_rows)


@cli.command("list-calculated-insights")
def list_calculated_insights_cmd():
    _, sf, _e = _ctx()
    insights = dc.list_calculated_insights(sf)
    if not insights:
        click.echo("No Calculated Insights found in this org.")
        return
    for ci in insights:
        dims = ", ".join(d["name"] for d in ci.get("dimensions", []))
        measures = ", ".join(m["name"] for m in ci.get("measures", []))
        click.echo(f"{ci['name']}  (dimensions: {dims or '-'}; measures: {measures or '-'}; "
                   f"last successful process: {ci.get('latestSuccessfulProcessTime', '-')})")


@cli.command("list-data-graphs")
def list_data_graphs_cmd():
    _, sf, _e = _ctx()
    graphs = dc.list_data_graphs(sf)
    if not graphs:
        click.echo("No Data Graphs found in this org.")
        return
    for g in graphs:
        click.echo(f"{g.get('name', g)}")


@cli.command("query-calculated-insight")
@click.argument("ci_name")
@click.option("--csv", "csv_path", default=None, help="Write results to a CSV file instead of printing.")
@click.option("--excel", "excel_path", default=None, help="Write results to an Excel file instead of printing.")
@click.option("--max-print-rows", default=50, help="Console preview row cap (ignored for --csv/--excel).")
def query_calculated_insight_cmd(ci_name, csv_path, excel_path, max_print_rows):
    """Query a specific Calculated Insight's actual computed data (the
    real object name, e.g. RateCount__cio -- see list-calculated-insights)."""
    _, sf, _e = _ctx()
    records, total_size, truncated = dc.query_calculated_insight(sf, ci_name)
    _output_query_result(records, total_size, truncated, csv_path, excel_path, max_print_rows)
    if not records:
        click.echo("(Empty is expected if this Calculated Insight hasn't finished "
                   "processing yet -- check with data-cloud-status calculated-insight.)")


@cli.command("data-cloud-status")
@click.argument("status_type", type=click.Choice(list(dc.STATUS_OBJECTS.keys())))
@click.argument("name", required=False)
@click.option("--csv", "csv_path", default=None, help="Write results to a CSV file instead of printing.")
@click.option("--excel", "excel_path", default=None, help="Write results to an Excel file instead of printing.")
def data_cloud_status_cmd(status_type, name, csv_path, excel_path):
    """Check status for a Data Cloud monitoring object -- calculated-insight,
    data-stream, dso, identity-resolution, data-transform, or data-graph.
    Omit NAME to list all."""
    _, sf, _e = _ctx()
    records, total_size, truncated = dc.check_status(sf, status_type, name=name)
    _output_query_result(records, total_size, truncated, csv_path, excel_path, 50)


@cli.command("data-cloud-profile")
@click.argument("data_model_name")
@click.argument("filter_expr")
@click.option("--fields", default=None, help="Comma-separated field list (omit for up to 10 arbitrary fields).")
@click.option("--limit", default=None, type=int)
@click.option("--offset", default=None, type=int)
@click.option("--orderby", default=None, help="Field to sort by; prefix with - for descending.")
@click.option("--csv", "csv_path", default=None, help="Write results to a CSV file instead of printing.")
@click.option("--excel", "excel_path", default=None, help="Write results to an Excel file instead of printing.")
@click.option("--max-print-rows", default=50, help="Console preview row cap (ignored for --csv/--excel).")
def data_cloud_profile_cmd(data_model_name, filter_expr, fields, limit, offset, orderby,
                          csv_path, excel_path, max_print_rows):
    """Look up Unified Profile data by data model name (e.g.
    UnifiedssotIndividualIndv__dlm) + a required equality filter (e.g.
    "[ssot__LastName__c=Smith]") -- the CLI alternative to Data Cloud's own
    Profile Explorer. Only equality/AND filters are supported (a real Data
    Cloud API constraint, not this framework's)."""
    _, sf, _e = _ctx()
    records, total_size, truncated = dc.query_unified_profile(
        sf, data_model_name, filter_expr, fields=fields, limit=limit, offset=offset, orderby=orderby
    )
    _output_query_result(records, total_size, truncated, csv_path, excel_path, max_print_rows)


@cli.command("generate-mock-data")
@click.argument("object_name")
@click.option("--count", default=50, help="Number of mock rows to generate (free tier caps at 5000/request).")
@click.option("--schema", default="dbo")
def generate_mock_data_cmd(object_name, count, schema):
    s, sf, engine = _ctx()
    rows, skipped = mkd.generate_mock_object_data(sf, engine, object_name, count, s.mockaroo_api_key, schema=schema)
    click.echo(f"Wrote {rows} mock row(s) to {schema}.{object_name}_Mock")
    if skipped:
        click.echo(f"Skipped {len(skipped)} field(s) with no mock mapping (reference/multipicklist/etc.):")
        for name, typ in skipped:
            click.echo(f"  {name} ({typ})")


@cli.command("generate-related-mock-data")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--count", "counts", multiple=True, required=True,
              help="NAME=N, repeatable. Top-level (no in-scope parent) objects get N total rows; "
                   "objects nested under a parent get N rows PER parent row.")
@click.option("--schema", default="dbo")
def generate_related_mock_data_cmd(object_names, counts, schema):
    s, sf, engine = _ctx()
    object_names = list(object_names)

    count_map = {}
    for item in counts:
        if "=" not in item:
            raise click.BadParameter(f"--count must be NAME=N, got: {item!r}")
        name, _, n = item.partition("=")
        count_map[name] = int(n)

    (recipe_path, skipped_by_object, primary_parent, secondary_exact_parents,
     secondary_random_parents, fields_by_object) = sfd.build_recipe(sf, object_names, count_map)
    click.echo(f"Recipe written to {recipe_path} (review/hand-edit, or re-run directly with `snowfakery {recipe_path}`)")
    for child, parent in primary_parent.items():
        note = ""
        if secondary_exact_parents.get(child):
            note += f"; also exactly references {', '.join(secondary_exact_parents[child])}"
        if secondary_random_parents.get(child):
            note += (f"; also randomly references {', '.join(secondary_random_parents[child])} "
                     f"(not scoped to the same {parent} -- see roadmap #6)")
        click.echo(f"  {child} nested under {parent}{note}")

    rows_written = sfd.run_recipe(engine, recipe_path, object_names, fields_by_object, schema=schema)
    for name in object_names:
        click.echo(f"Wrote {rows_written.get(name, 0)} mock row(s) to {schema}.{name}_Mock")
        skipped = skipped_by_object.get(name, [])
        if skipped:
            click.echo(f"  Skipped {len(skipped)} field(s):")
            for field_name, reason in skipped:
                click.echo(f"    {field_name} ({reason})")


@cli.command("generate-mapping-doc")
@click.argument("object_name")
@click.argument("output_path")
@click.argument("source_table")
@click.option("--schema", default="dbo")
def generate_mapping_doc_cmd(object_name, output_path, source_table, schema):
    _, sf, engine = _ctx()
    path = mpd.generate_mapping_workbook(sf, object_name, output_path, engine, source_table, schema=schema)
    click.echo(f"Wrote {path} ({source_table} -> {object_name})")


@cli.command("check-mapping-balance")
@click.argument("object_name")
@click.argument("mapping_path")
@click.argument("transform_sql_path")
@click.option("--load-table", default=None, help="Load table name to match in the INSERT INTO (defaults to the first one found).")
def check_mapping_balance_cmd(object_name, mapping_path, transform_sql_path, load_table):
    _, sf, _e = _ctx()
    result = mpd.check_mapping_balance(sf, mapping_path, object_name, transform_sql_path, load_table_name=load_table)

    if result["not_a_real_field"]:
        click.echo(f"Not a real field on {object_name} (typo, removed, or never deployed -- fix before loading):")
        for field in result["not_a_real_field"]:
            click.echo(f"  {field}")
    if result["documented_not_implemented"]:
        click.echo("Documented as mapped, but the transform doesn't populate them:")
        for field in result["documented_not_implemented"]:
            click.echo(f"  {field}")
    if result["implemented_not_documented"]:
        click.echo("Transform populates these, but they're not documented as mapped:")
        for field in result["implemented_not_documented"]:
            click.echo(f"  {field}")
    if not any(result.values()):
        click.echo("In balance -- mapping doc and transform agree, and every field is real.")


@cli.command("auto-map")
@click.argument("object_name")
@click.argument("mapping_path")
@click.argument("source_table")
@click.option("--schema", default="dbo")
def auto_map_cmd(object_name, mapping_path, source_table, schema):
    s, sf, engine = _ctx()
    suggestions = am.suggest_mappings(sf, engine, object_name, source_table, schema=schema)
    result = mpd.apply_auto_map_suggestions(mapping_path, object_name, object_name, suggestions)

    matched = sum(1 for s_ in suggestions if s_["target_field"])
    yes = sum(1 for s_ in suggestions if s_["migrate_recommended"] == "Yes")
    no = sum(1 for s_ in suggestions if s_["migrate_recommended"] == "No")
    review = sum(1 for s_ in suggestions if s_["migrate_recommended"] == "Review")

    click.echo(f"Suggested {matched} of {len(suggestions)} source field(s) on {source_table} -> {object_name}")
    click.echo(f"  Recommended: {yes} Yes, {no} No, {review} Review")
    click.echo(f"Applied to {mapping_path}: {result['applied']} row(s) written, "
               f"{result['skipped_human_filled']} skipped (already had a human-filled Target field)")
    click.echo(f"Results also in {schema}.AutoMapSuggestions / {schema}.SourceRegistry")


@cli.command("generate-solution-doc")
@click.argument("output_path")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--mapping-path", default=None, help="Mapping workbook (generate-mapping-doc/auto-map output) to pull field-mapping summaries from.")
@click.option("--template", "template_path", default=None, help="Custom branded .docx template with docxtpl tags -- falls back to the built-in default if omitted.")
@click.option("--company", "company_name", default=None, help="Company/client name shown on the cover.")
@click.option("--project", "project_name", default=None, help="Project name shown on the cover (defaults to a generic title).")
@click.option("--prepared-by", default=None)
@click.option("--schema", default="dbo")
@click.option("--appendix", is_flag=True, help="Include a full field-by-field mapping appendix (needs --mapping-path).")
def generate_solution_doc_cmd(output_path, object_names, mapping_path, template_path,
                               company_name, project_name, prepared_by, schema, appendix):
    s, sf, engine = _ctx()
    path, context = sd.generate_solution_doc(
        sf, engine, output_path, list(object_names), mapping_path=mapping_path,
        template_path=template_path, schema=schema, company_name=company_name,
        project_name=project_name, prepared_by=prepared_by, target_org_alias=s.sf_org_alias,
        include_appendix=appendix,
    )
    template_note = f"custom template {template_path}" if template_path else "built-in default template"
    click.echo(f"Wrote {path} covering {len(context['objects'])} object(s) ({template_note})")
    if context["unresolved_cycles"]:
        click.echo("Unresolved circular dependencies flagged in the document:")
        for group in context["unresolved_cycles"]:
            click.echo(f"  {', '.join(group)}")


@cli.command("generate-run-book")
@click.argument("output_path")
@click.option("--tab", "tab_name", required=True, help="New tab name (e.g. Dev1, UAT, PROD) -- refuses to overwrite an existing tab.")
@click.option("--objects", "object_names", multiple=True, help="Auto-fills the Script/Transformation section from analyze-load-order's results. Omit for a blank section to fill in by hand.")
@click.option("--schema", default="dbo")
@click.option("--template", "template_path", default=None, help="Custom run-book template -- falls back to docs/RUN_BOOK_TEMPLATE.md if omitted.")
def generate_run_book_cmd(output_path, tab_name, object_names, schema, template_path):
    _, _, engine = _ctx()
    kwargs = {"schema": schema}
    if template_path:
        kwargs["template_path"] = template_path
    if object_names:
        kwargs["engine"] = engine
        kwargs["object_names"] = list(object_names)
    path = rb.generate_run_book(output_path, tab_name, **kwargs)
    click.echo(f"Wrote {path} (tab '{tab_name}')")
    if object_names:
        click.echo(f"Script/Transformation section auto-filled from {schema}.ObjectLoadOrder for: {', '.join(object_names)}")


@cli.command("add-run-book-pass")
@click.argument("path")
@click.option("--from-tab", required=True, help="Existing tab to copy the recipe from (e.g. Dev1).")
@click.option("--to-tab", required=True, help="New tab name for the fresh pass (e.g. UAT) -- refuses to overwrite an existing tab.")
def add_run_book_pass_cmd(path, from_tab, to_tab):
    rb.add_run_book_pass(path, from_tab, to_tab)
    click.echo(f"Copied '{from_tab}' -> '{to_tab}' in {path} (recipe carried forward, result columns blanked)")


@cli.command("analyze-org-risk")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--mapping-path", default=None, help="Mapping workbook -- cross-references active validation rules' ErrorDisplayField against fields actually being migrated (Migrate Data == Yes).")
@click.option("--schema", default="dbo")
def analyze_org_risk_cmd(object_names, mapping_path, schema):
    _, sf, engine = _ctx()
    object_names = list(object_names)
    fields_in_scope = ra.fields_in_scope_from_mapping(mapping_path, object_names)
    results = ra.analyze_migration_risk(sf, object_names, fields_in_scope_by_object=fields_in_scope)
    ra.write_to_sql(engine, results, schema=schema)

    for r in results:
        click.echo(
            f"{r['object']}: {r['active_validation_rule_count']} active validation rule(s), "
            f"{len(r['apex_triggers'])} Apex trigger(s), {r['active_flow_count']} active record-triggered flow(s), "
            f"{len(r['workflow_rules'])} legacy workflow rule(s), {len(r['approval_processes'])} approval process(es)"
        )
        for vr in r["validation_rules"]:
            if vr.get("Active"):
                hit = "  [DIRECT HIT on a migrated field]" if vr.get("direct_hit") else ""
                name = vr.get("ValidationName") or vr.get("Id")
                click.echo(f"    - {name}: {vr.get('ErrorMessage')}{hit}")
        for w in r["warnings"]:
            click.echo(f"    Warning: {w}")

    click.echo(f"\nResults in {schema}.ObjectAutomationRisk")


@cli.command("recommend-batch-size")
@click.argument("object_name")
@click.option("--schema", default="dbo")
def recommend_batch_size_cmd(object_name, schema):
    """Print bulkops' batch-size recommendation for an object, with full
    rationale, without loading anything -- read-only, no Salesforce call."""
    _, _, engine = _ctx()
    size, rationale = ba.recommend_batch_size(engine, object_name, schema=schema)
    for line in rationale:
        click.echo(line)


@cli.command("suggest-batch-heuristics")
@click.option("--schema", default="dbo")
def suggest_batch_heuristics_cmd(schema):
    """Print candidate reference/batch_size_heuristics.json edits based on
    this project's own converged load history (dbo.BulkOpsLog) -- never
    writes the file; review and commit changes yourself, same as adding a
    new alias to the field-synonym thesaurus."""
    _, _, engine = _ctx()
    suggestions = ba.suggest_heuristic_updates(engine, schema=schema)
    if not suggestions:
        click.echo("No converged batch sizes to suggest yet -- needs several consecutive "
                   "clean runs at the same size for an object (see reference/batch_size_heuristics.json's "
                   "history_rules.clean_runs_to_increase).")
        return
    for s in suggestions:
        current = s["current_seed"] if s["current_seed"] is not None else "(no existing seed)"
        click.echo(f"{s['object']}: converged on {s['converged_size']} over {s['runs']} clean run(s) "
                   f"-- current seed: {current}")
    click.echo("\nReview and edit reference/batch_size_heuristics.json's object_seeds "
              "yourself, then commit deliberately -- this command never writes the file.")


if __name__ == "__main__":
    cli()
