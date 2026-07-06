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
import load_order as lo
import profiling as pf
import query_tool as qt
import mock_data as mkd
import mapping_doc as mpd
import auto_mapper as am
import solution_doc as sd
import risk_analyzer as ra
import parquet_import as pqi


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
def bulkops_cmd(object_name, operation, source_table, external_id, key_column, schema):
    s, sf, engine = _ctx()
    summary = bo.bulk_op(sf, engine, object_name, operation, source_table,
                         external_id=external_id, key_column=key_column,
                         schema=schema, stage_dir=s.stage_dir)
    warnings = summary.pop("preflight_warnings", [])
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
        click.echo("Not all matching records were fetched -- pass --all to retrieve everything, "
                   "or add/tighten a LIMIT.")


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


if __name__ == "__main__":
    cli()
