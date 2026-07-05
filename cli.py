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
"""
import click

from config import get_settings
from sf_client import connect_salesforce
from sql_client import make_engine
import metadata as md
import replicate as rep
import bulkops as bo
import load_order as lo


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


if __name__ == "__main__":
    cli()
