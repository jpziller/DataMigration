"""Command-line entry point. Migration verbs: replicate, bulkops, describe.

Examples:
    python cli.py list-objects
    python cli.py describe Account
    python cli.py dump-describe Account
    python cli.py replicate Account
    python cli.py replicate Contact --where "CreatedDate = LAST_N_DAYS:30" --raw
    python cli.py bulkops Account insert Account_Load --key-column LoadId
    python cli.py bulkops Contact upsert Contact_Load --external-id Legacy_Id__c
    python cli.py analyze-load-order Account Contact Opportunity OpportunityLineItem
    python cli.py profile-salesforce Account
    python cli.py profile-sql-table Account
    python cli.py export-profile-excel profile.xlsx
    python cli.py query "SELECT Id, Name FROM Account LIMIT 10"
    python cli.py query "SELECT Id, Name, Account.Name FROM Contact" --csv out.csv
    python cli.py generate-mock-data Account --count 50
    python cli.py generate-mapping-doc Account mapping/Account_Mapping.xlsx --source-table SourceAccounts
    python cli.py check-mapping-balance Account mapping/Account_Mapping.xlsx sql/transformations/010_account_load.sql
"""
import click
import pandas as pd

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


def _ctx():
    s = get_settings()
    return s, connect_salesforce(s), make_engine(s)


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


@cli.command("bulkops")
@click.argument("object_name")
@click.argument("operation", type=click.Choice(["insert", "update", "upsert", "delete"]))
@click.argument("source_table")
@click.option("--external-id", default=None, help="External id field (upsert).")
@click.option("--key-column", default="LoadId", help="Local unique key for in-place writeback.")
@click.option("--schema", default="dbo")
def bulkops_cmd(object_name, operation, source_table, external_id, key_column, schema):
    s, sf, engine = _ctx()
    summary = bo.bulk_op(sf, engine, object_name, operation, source_table,
                         external_id=external_id, key_column=key_column,
                         schema=schema, stage_dir=s.stage_dir)
    for k, v in summary.items():
        click.echo(f"{k:12}: {v}")


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
        df = pd.DataFrame(records)
        with pd.option_context("display.max_rows", max_print_rows,
                                "display.max_columns", None, "display.width", None):
            click.echo(df.to_string(index=False))

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
@click.option("--source-table", default=None, help="A SQL Server table to list on a reference sheet.")
@click.option("--schema", default="dbo")
def generate_mapping_doc_cmd(object_name, output_path, source_table, schema):
    _, sf, engine = _ctx()
    path = mpd.generate_mapping_workbook(sf, object_name, output_path, engine=engine,
                                         source_table=source_table, schema=schema)
    click.echo(f"Wrote {path}")


@cli.command("check-mapping-balance")
@click.argument("object_name")
@click.argument("mapping_path")
@click.argument("transform_sql_path")
@click.option("--load-table", default=None, help="Load table name to match in the INSERT INTO (defaults to the first one found).")
def check_mapping_balance_cmd(object_name, mapping_path, transform_sql_path, load_table):
    result = mpd.check_mapping_balance(mapping_path, object_name, transform_sql_path, load_table_name=load_table)

    if result["documented_not_implemented"]:
        click.echo("Documented as mapped, but the transform doesn't populate them:")
        for field in result["documented_not_implemented"]:
            click.echo(f"  {field}")
    if result["implemented_not_documented"]:
        click.echo("Transform populates these, but they're not documented as mapped "
                   "(or don't exist as a field at all -- check for typos/removed fields):")
        for field in result["implemented_not_documented"]:
            click.echo(f"  {field}")
    if not result["documented_not_implemented"] and not result["implemented_not_documented"]:
        click.echo("In balance -- mapping doc and transform agree.")


if __name__ == "__main__":
    cli()
