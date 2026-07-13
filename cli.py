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
    python cli.py check-mapping-balance Account mapping/Migration_Mapping.xlsx sql/transformations/<NNN>_account_load.sql
    python cli.py auto-map Account mapping/Migration_Mapping.xlsx SourceAccounts
    python cli.py generate-solution-doc Solution.docx Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx
    python cli.py analyze-org-risk Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx
    python cli.py import-parquet ./data/accounts.parquet SourceAccounts
"""
import os

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
import migration_run_book as mrb
import source_ingestion as si
import reference_record as rr
import record_types as rt
import data_model_diagram as dmd
import load_table_prep as ltp
import orchestrator as orch
import script_numbering as sn
import validators_lookup as vl
import failure_triage as ft
import adversarial_mock_data as amd
import pass_summary as ps
import dev_cycle as devc
import reconciliation as rc
import readiness as rdy
import migration_brief as mbf
import discovery_checklist as dch


def _ctx():
    s = get_settings()
    return s, connect_salesforce(s), make_engine(s)


def _parse_object_value_pairs(items, option_name):
    """Parse a repeatable Object=Value CLI option (--load-table,
    --migration-key) into a dict, rejecting malformed syntax AND a
    repeated Object with a clear error -- found in review: the identical
    dict-keyed-by-name silent-overwrite bug already fixed once for
    --scenario existed independently at all four of this pattern's other
    call sites, silently keeping only the last value for a repeated key
    with no warning at all."""
    result = {}
    for item in items:
        if "=" not in item:
            raise click.BadParameter(f"{option_name} must be Object=Value, got: {item!r}")
        obj, _, value = item.partition("=")
        if obj in result:
            raise click.BadParameter(f"{option_name} '{obj}' was given more than once.")
        result[obj] = value
    return result


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


@cli.command("validate-external-id")
@click.argument("object_name")
@click.argument("field_name")
def validate_external_id_cmd(object_name, field_name):
    """Confirm field_name is genuinely externalId+unique in the live org's
    describe() before it's trusted as a migration key (roadmap #50, hard
    rule 12). Read-only, no confirmation needed. Exits nonzero on failure
    so this can gate a script, not just be eyeballed."""
    _, sf, _e = _ctx()
    result = md.validate_external_id_field(sf, object_name, field_name)
    if result["ok"]:
        click.echo(f"OK -- {field_name} on {object_name} is a real, externalId+unique field.")
        return
    click.echo(f"NOT VALID -- {field_name} on {object_name} cannot be trusted as a migration key:")
    for problem in result["problems"]:
        click.echo(f"  {problem}")
    raise SystemExit(1)


@cli.command("next-script-number")
@click.option("--dir", "target_dir", type=click.Choice(["transformations", "source_ingestion"]),
              default="transformations", help="Which numbered script folder to check.")
@click.option("--after", type=int, default=None, help="Insert between two existing scripts: the number immediately before the gap (use with --before).")
@click.option("--before", type=int, default=None, help="Insert between two existing scripts: the number immediately after the gap (use with --after).")
def next_script_number_cmd(target_dir, after, before):
    """Suggests the next number for a new sql/transformations/ or
    sql/source_ingestion/ script (roadmap: numbering gaps of 10 so a later
    insertion doesn't force a renumber). With no options: the next
    top-level slot. With --after/--before: an unused number strictly
    between two existing scripts, for inserting one later. Read-only,
    advisory only -- never creates or renames a file itself."""
    directory = f"sql/{target_dir}"
    try:
        n = sn.next_number(directory, after=after, before=before)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(sn.format_number(n))


@cli.command("check-validators")
@click.argument("object_name")
def check_validators_cmd(object_name):
    """Print validators/<object_name>.md (if it exists) and the list of
    universal system validators -- run before building a transform for
    this object (Standard Workflow step 1). Read-only, safe without
    confirmation; see validators/README.md for the full convention."""
    system_validators = vl.list_system_validators()
    click.echo("System validators (apply to every object):")
    if system_validators:
        for name in system_validators:
            click.echo(f"  validators/system/{name}")
    else:
        click.echo("  (none found)")
    click.echo("")

    content = vl.read_object_validator(object_name)
    if content is None:
        click.echo(f"No object-specific validator found for '{object_name}' yet.")
        click.echo("If this build turns up something worth capturing, write it into "
                    f"validators/{object_name}.md -- see validators/README.md for the format.")
        return
    click.echo(f"validators/{object_name}.md:")
    click.echo(content)


@cli.command("record-counts")
@click.argument("object_names", nargs=-1)
@click.option("--all-objects", "all_objects", is_flag=True, help="Every object in the org, not just the ones named -- can be a large response for a real org.")
def record_counts_cmd(object_names, all_objects):
    if not object_names and not all_objects:
        raise click.UsageError("Pass one or more object names, or --all-objects for the whole org.")
    _, sf, _e = _ctx()
    counts = md.record_counts(sf, list(object_names) if object_names else None)
    for name in sorted(counts):
        click.echo(f"{name:40} {counts[name]:>12,}")
    click.echo("(Approximate, cached snapshot -- Salesforce's own docs: 'may not accurately "
               "represent the number of records'. Use profile-salesforce for an exact count.)")


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


@cli.command("import-csv-directory")
@click.argument("csv_dir")
@click.option("--schema", default="dbo")
@click.option("--sql-dir", default=None, help="Where generated scripts live (defaults to sql/source_ingestion).")
@click.option("--ticket", default=None, help="Ticket reference for any newly generated or --rebuild'd script (hard rule 10) -- required only when a script doesn't exist yet, or is being rebuilt.")
@click.option("--rebuild", "rebuild_tables", multiple=True, help="Table name(s) to explicitly regenerate the script for, after reviewing a reported drift. Never automatic.")
@click.option("--run-book", "run_book_path", default=None, help="Migration Run Book workbook path -- with --run-book-tab, auto-syncs this batch's SourceIngestionLog rows into that tab's Pre-Migration phase right after it's written.")
@click.option("--run-book-tab", default=None, help="Migration Run Book tab name to sync into -- requires --run-book.")
def import_csv_directory_cmd(csv_dir, schema, sql_dir, ticket, rebuild_tables, run_book_path, run_book_tab):
    """Bulk-ingest every *.csv in csv_dir (roadmap #46): generates a numbered
    BULK INSERT script per new file, reuses an existing script unchanged on
    a later pass, and hard-stops (without touching that table) if the CSV's
    current structure no longer matches what its script expects."""
    if bool(run_book_path) != bool(run_book_tab):
        raise click.BadParameter("--run-book and --run-book-tab must be given together.")
    _, _, engine = _ctx()
    kwargs = {
        "schema": schema, "ticket": ticket, "rebuild": list(rebuild_tables),
        "run_book_path": run_book_path, "run_book_tab": run_book_tab,
    }
    if sql_dir:
        kwargs["sql_dir"] = sql_dir
    results = si.import_directory(engine, csv_dir, **kwargs)

    if not results:
        click.echo(f"No *.csv files found in {csv_dir}.")
        return

    for r in results:
        if "run_book_sync_error" in r:
            click.echo(f"Migration Run Book sync failed (load results above are unaffected): {r['run_book_sync_error']}")
        elif r["status"] == "drift_blocked":
            d = r["drift"]
            parts = []
            if d["added"]:
                parts.append(f"added: {', '.join(d['added'])}")
            if d["removed"]:
                parts.append(f"removed: {', '.join(d['removed'])}")
            if d["reordered"]:
                parts.append("column order changed")
            click.echo(f"BLOCKED  {r['csv']} -> {r['table']}: {'; '.join(parts)} "
                       f"(script: {r['script']}) -- review and pass --rebuild {r['table']} once confirmed safe.")
        else:
            click.echo(f"{r['status'].upper():9} {r['csv']} -> {schema}.{r['table']} "
                       f"({r['rows']} rows, {r['duration_seconds']:.1f}s) [{r['script']}]")

    blocked = sum(1 for r in results if r["status"] == "drift_blocked")
    if blocked:
        click.echo(f"\n{blocked} of {len(results)} file(s) blocked on structure drift -- see above.")


@cli.command("enable-source-ingestion-logging")
@click.option("--schema", default="dbo", help="Schema to enable logging for -- each schema is opted in independently.")
def enable_source_ingestion_logging_cmd(schema):
    _, _, engine = _ctx()
    si.enable_source_ingestion_logging(engine, schema=schema)
    click.echo(f"Source ingestion logging enabled for schema '{schema}' -- {schema}.SourceIngestionLog created.")
    click.echo("Every import-csv-directory call against this schema will now log automatically.")


@cli.command("disable-source-ingestion-logging")
@click.option("--schema", default="dbo", help="Schema to disable logging for.")
def disable_source_ingestion_logging_cmd(schema):
    _, _, engine = _ctx()
    si.disable_source_ingestion_logging(engine, schema=schema)
    click.echo(f"Source ingestion logging disabled for schema '{schema}' -- {schema}.SourceIngestionLog dropped, history discarded.")


@cli.command("bulkops")
@click.argument("object_name")
@click.argument("operation", type=click.Choice(["insert", "update", "upsert", "delete"]))
@click.argument("source_table", required=False, default=None)
@click.option("--where", default=None, help="Purge mode (delete only, no source table): SOQL WHERE clause selecting the records to delete, e.g. \"AccountNumber LIKE 'MOCKACCT-%'\". Matching Ids are resolved via SOQL into <Object>_Purge, then deleted through the normal path. No delete-everything default -- purging a whole object means writing \"Id != null\" explicitly.")
@click.option("--dry-run", is_flag=True, help="With --where: report the matched count and sample Ids without touching SQL Server or Salesforce.")
@click.option("--external-id", default=None, help="External id field (upsert; also delete -- resolved to real Ids via a query first, since Bulk API 2.0's delete only ever accepts Id).")
@click.option("--key-column", default="LoadId", help="Local unique key for in-place writeback.")
@click.option("--fingerprint-columns", default=None, help="Comma-separated subset of the sent columns to match results on, instead of every sent column. Use this when a sent column can come back from Salesforce reformatted (e.g. a datetime echoed as '...+00:00' -> '...000Z') -- the default fingerprint (every sent column) would then fail to match that row at all. The migration key column alone (e.g. MigrationID__c) is normally the safest choice.")
@click.option("--ref-prefix", default="REF_", help="Load table columns starting with this prefix (case-insensitive) are human-only SQL-side audit fields (hard rule 13) -- excluded from the payload and never flagged as 'not a real field'.")
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
@click.option("--run-book", "run_book_path", default=None, help="Migration Run Book workbook path -- with --run-book-tab, auto-syncs this load's BulkOpsLog row into that tab's Load phase right after it's written.")
@click.option("--run-book-tab", default=None, help="Migration Run Book tab name to sync into -- requires --run-book.")
def bulkops_cmd(object_name, operation, source_table, where, dry_run, external_id,
                key_column, fingerprint_columns, ref_prefix, schema, email_deliverability, confirm_external_email_risk,
                batch_size, run_book_path, run_book_tab):
    fingerprint_columns = [c.strip() for c in fingerprint_columns.split(",")] if fingerprint_columns else None
    if bool(run_book_path) != bool(run_book_tab):
        raise click.BadParameter("--run-book and --run-book-tab must be given together.")
    if where and operation != "delete":
        raise click.UsageError("--where is purge mode and only valid with the delete operation.")
    if where and source_table:
        raise click.UsageError("--where and a source table are mutually exclusive -- "
                               "purge mode builds its own <Object>_Purge table from the filter.")
    if dry_run and not where:
        raise click.UsageError("--dry-run only applies to --where purge mode.")
    if not where and not source_table:
        raise click.UsageError("Pass a source table, or (delete only) --where \"<SOQL filter>\" to purge by filter.")
    s, sf, engine = _ctx()

    if where:
        summary = bo.purge_by_filter(sf, engine, object_name, where,
                                     schema=schema, stage_dir=s.stage_dir,
                                     batch_size=batch_size, dry_run=dry_run,
                                     run_book_path=run_book_path,
                                     run_book_tab=run_book_tab)
    else:
        summary = bo.bulk_op(sf, engine, object_name, operation, source_table,
                             external_id=external_id, key_column=key_column,
                             fingerprint_columns=fingerprint_columns,
                             ref_prefix=ref_prefix,
                             schema=schema, stage_dir=s.stage_dir,
                             email_deliverability=email_deliverability,
                             confirm_external_email_risk=confirm_external_email_risk,
                             batch_size=batch_size, run_book_path=run_book_path,
                             run_book_tab=run_book_tab)
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


@cli.command("triage-failures")
@click.argument("table")
@click.option("--schema", default="dbo")
@click.option("--error-column", default="Error")
@click.option("--object", "object_name", default=None, help="Enables real cross-references: dbo.ObjectAutomationRisk's active validation rules (FIELD_CUSTOM_VALIDATION_EXCEPTION), and whether a REQUIRED_FIELD_MISSING field was ever mapped (with --mapping-path).")
@click.option("--mapping-path", default=None, help="Mapping workbook -- with --object, checks whether a REQUIRED_FIELD_MISSING field was ever chosen as a Target Field at all.")
def triage_failures_cmd(table, schema, error_column, object_name, mapping_path):
    """Group a completed bulkops run's failures (roadmap #61) by
    normalized error signature and map well-known Salesforce Bulk API
    error codes to a likely root cause + suggested next command --
    turning "N rows failed" into "1 root cause, here's where to look."
    Read-only, advisory only -- never changes data, never re-runs
    bulkops. `table` is the same load table (written back in place) or
    <table>_Result table bulkops-retry already reads."""
    _, _, engine = _ctx()
    results = ft.triage_failures(
        engine, table, schema=schema, error_column=error_column,
        object_name=object_name, mapping_path=mapping_path,
    )
    if not results:
        click.echo(f"No failed rows found in {schema}.{table} (column {error_column}) -- nothing to triage.")
        return

    total = sum(r["count"] for r in results)
    click.echo(f"{total} failed row(s) across {len(results)} distinct signature(s) in {schema}.{table}:")
    for r in results:
        click.echo(f"\n{r['count']}x {r['code']}: {r['cause']}")
        if r["fields"]:
            click.echo(f"  Field(s) named in the error: {', '.join(r['fields'])}")
        for step in r["next_steps"]:
            click.echo(f"  - {step}")
        for extra in r["detail"]:
            click.echo(f"    -> {extra}")


@cli.command("reset-dev-cycle")
@click.option("--objects", "object_names", multiple=True, required=True, help="Salesforce object name(s), repeatable.")
@click.option("--schema", default="dbo")
@click.option("--purge-org-where", "purge_wheres", multiple=True,
              help="Object:WHERE_CLAUSE, repeatable -- also purges matching org test data via a real "
                   "bulkops delete (Hard Rule 2 -- confirm the target org first). Omit entirely to "
                   "only reset mirror-DB tables.")
@click.option("--dry-run", is_flag=True, help="With --purge-org-where: report matched org record counts without deleting anything.")
def reset_dev_cycle_cmd(object_names, schema, purge_wheres, dry_run):
    """Reset a Dev-cycle iteration (roadmap #63): drop every _Mock/
    _Mock_Adversarial/_Load/_Load_Result/_Load_Retry/_Purge/_Purge_Result
    table for the given objects, and clear their profiling data so the
    next profile-salesforce/profile-sql-table call doesn't silently skip
    re-profiling a rebuilt table. Never touches sql/transformations/*.sql,
    mapping docs, or org-metadata caches (ObjectAutomationRisk,
    RecordTypeMap, SourceRegistry/AutoMapSuggestions)."""
    s, sf, engine = _ctx()
    object_names = list(object_names)

    result = devc.reset_dev_cycle_tables(engine, object_names, schema=schema)
    if result["dropped"]:
        click.echo(f"Dropped {len(result['dropped'])} table(s):")
        for t in result["dropped"]:
            click.echo(f"  {t}")
    else:
        click.echo("No mock/load/purge tables found to drop for these objects.")
    if result["profiling_cleared"]:
        click.echo(f"Cleared profiling data for: {', '.join(result['profiling_cleared'])}")

    for item in purge_wheres:
        if ":" not in item:
            raise click.BadParameter(f"--purge-org-where must be Object:WHERE_CLAUSE, got: {item!r}")
        object_name, _, where = item.partition(":")
        summary = devc.purge_org_test_data(sf, engine, object_name, where, schema=schema, dry_run=dry_run)
        if dry_run:
            click.echo(f"[dry run] {object_name}: {summary['matched']} record(s) match \"{where}\" -- nothing deleted.")
        else:
            click.echo(f"{object_name}: purged {summary.get('matched', 0)} record(s) matching \"{where}\".")


@cli.command("reconcile-load-counts")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--schema", default="dbo")
@click.option("--mapping-path", default=None, help="Mapping workbook -- enables the source-table row count via each object's own 'Source Object:' header cell.")
@click.option("--load-table", "load_tables", multiple=True, help="Object=TableName, repeatable -- overrides the <Object>_Load default.")
def reconcile_load_counts_cmd(object_names, schema, mapping_path, load_tables):
    """Cross-check source table row count -> Load table row count ->
    bulkops' most recent submitted/succeeded/failed counts (roadmap #64)
    for each object, flagging anywhere they don't reconcile the way
    they're supposed to. Read-only, aggregates data every one of these
    tools already produces."""
    _, _, engine = _ctx()
    load_table_map = _parse_object_value_pairs(load_tables, "--load-table")

    results = rc.reconcile_load_counts(
        engine, list(object_names), schema=schema, mapping_path=mapping_path, load_tables=load_table_map,
    )
    for r in results:
        click.echo(
            f"\n{r['object']}: source={r['source_count'] if r['source_count'] is not None else 'n/a'}, "
            f"load={r['load_count'] if r['load_count'] is not None else 'n/a'}, "
            f"bulkops submitted/succeeded/failed="
            f"{r['bulkops_submitted']}/{r['bulkops_succeeded']}/{r['bulkops_failed']}"
        )
        if r["flags"]:
            for flag in r["flags"]:
                click.echo(f"  ! {flag}")
        else:
            click.echo("  Clean -- source/Load/bulkops counts reconcile.")


@cli.command("assess-migration-readiness")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--schema", default="dbo")
@click.option("--mapping-path", default=None, help="Mapping workbook -- enables the check-mapping-balance and row-count-reconciliation source-count gates.")
@click.option("--migration-key", "migration_keys", multiple=True,
              help="Object=Field, repeatable -- enables the Migration Key Integrity and Live Migration Key Validation gates for that object.")
@click.option("--load-table", "load_tables", multiple=True, help="Object=TableName, repeatable -- overrides the <Object>_Load default.")
def assess_migration_readiness_cmd(object_names, schema, mapping_path, migration_keys, load_tables):
    """One aggregate go/no-go readiness view per object (roadmap #65) --
    re-checks or re-presents every gate this framework already enforces
    individually (hard rules 6/7/12, analyze-org-risk coverage,
    check-mapping-balance, Email Deliverability attestation, and #64's
    row-count reconciliation), instead of checking five different
    tables/commands by hand. Read-only -- no new checks invented. A gate
    left "not checked" (no --migration-key/--mapping-path given) is
    reported but never blocks the overall verdict by itself; only an
    explicit failure does."""
    _, sf, engine = _ctx()
    key_map = _parse_object_value_pairs(migration_keys, "--migration-key")
    load_table_map = _parse_object_value_pairs(load_tables, "--load-table")

    results = rdy.assess_migration_readiness(
        sf, engine, list(object_names), schema=schema,
        migration_keys=key_map, mapping_path=mapping_path, load_tables=load_table_map,
    )
    for r in results:
        verdict = "READY" if r["ready"] else "NOT READY"
        click.echo(f"\n{r['object']} ({r['load_table']}): {verdict}")
        for gate_name, gate in r["gates"].items():
            symbol = "OK" if gate["ok"] else ("--" if gate["ok"] is None else "FAIL")
            click.echo(f"  [{symbol}] {gate_name}: {gate['detail']}")


@cli.command("bootstrap-project")
@click.argument("brief_path")
@click.argument("run_book_path")
@click.option("--tab", "tab_name", required=True, help="New Migration Run Book tab name (refuses to overwrite an existing tab).")
@click.option("--schema", default="dbo")
def bootstrap_project_cmd(brief_path, run_book_path, tab_name, schema):
    """Bootstrap a new migration project from a brief (roadmap #59) --
    closes the hand-off gap between upstream client discovery (the
    architect, often with another AI session's help) and this
    framework's own build/validate/run tooling. Confirms every object
    named in the brief is real via live describe(), runs
    analyze-load-order across the ones that are, and scaffolds a
    Migration Run Book with that object list wired in. Never guesses
    mapping, field lists, or transform logic from the brief's own
    notes -- that's still generate-mapping-doc/auto-map's job, on the
    real source tables, once they exist."""
    s, sf, engine = _ctx()
    result = mbf.bootstrap_project(
        sf, engine, brief_path, run_book_path, tab_name, schema=schema,
        configured_org_alias=s.sf_org_alias or None,
    )

    if result["project"]:
        click.echo(f"Project: {result['project']}")
    if result["ticket"]:
        click.echo(f"Ticket: {result['ticket']} -- remember this for the Script Ticket Traceability Rule "
                   "(hard rule 10) once real transform scripts get built.")
    if result["org_alias_warning"]:
        click.echo(f"! {result['org_alias_warning']}")

    click.echo(f"Confirmed {len(result['valid_objects'])} object(s): {', '.join(result['valid_objects']) or '(none)'}")
    if result["problems"]:
        click.echo(f"{len(result['problems'])} problem(s):")
        for p in result["problems"]:
            click.echo(f"  ! {p}")

    if result["run_book_path"]:
        click.echo(f"Load order analyzed and Migration Run Book scaffolded at {result['run_book_path']} (tab '{tab_name}').")
        click.echo("Next: profile the source tables, then generate-mapping-doc/auto-map -- this bootstrap "
                   "never guesses mapping, field lists, or transform logic.")
    else:
        click.echo("No valid objects -- nothing to analyze or scaffold. Fix the brief and try again.")


@cli.command("generate-discovery-checklist")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--output", "output_path", default=None, help="Write the checklist to this .md file instead of only printing it.")
def generate_discovery_checklist_cmd(object_names, output_path):
    """Generate the discovery questions an architect should be asking
    about each object (roadmap #60) -- derived from live org signals
    (analyze-org-risk's active validation rules, whether the object
    carries RecordTypeId, and any reference field pointing at an object
    not yet in this candidate list), not a generic template. The
    companion to bootstrap-project (#59), running the other direction.
    Purely read-only against Salesforce -- no engine/mirror-DB dependency,
    so this can run before the SQL Server side of a project even exists."""
    _, sf, _e = _ctx()
    checklist = dch.generate_discovery_checklist(sf, list(object_names))
    markdown = dch.format_discovery_checklist_markdown(checklist)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        click.echo(f"Wrote {output_path}")
    else:
        click.echo(markdown)


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


@cli.command("orchestrator-assess")
@click.argument("object_name")
@click.option("--log-id", type=int, default=None, help="Assess a specific BulkOpsLog row instead of the most recent one for this object.")
@click.option("--schema", default="dbo")
@click.option("--environment", type=click.Choice(["uat", "prod"]), default="uat",
              help="Threshold profile from reference/orchestrator_thresholds.json -- prod is materially tighter.")
def orchestrator_assess_cmd(object_name, log_id, schema, environment):
    """Deterministic tier assessment (1-4) for a completed bulkops run --
    orchestrator Phase 1 (roadmap #53, docs/ORCHESTRATOR_DESIGN.md).
    Read-only; every individual bulkops call is still exactly as
    ask-gated as it always was -- this never changes that, it only
    observes and reports. Logs to <schema>.OrchestratorRunEvent if
    enable-orchestrator-logging has been run for this schema."""
    _, _, engine = _ctx()
    resolved_log_id, result = orch.assess_from_log(engine, object_name, log_id=log_id, schema=schema, environment=environment)
    click.echo(f"BulkOpsLog #{resolved_log_id} ({object_name}, {environment}): "
               f"Tier {result['tier']} ({result['tier_name']})")
    for reason in result["reasons"]:
        click.echo(f"  - {reason}")
    click.echo(f"Coarse-approval eligible: {result['coarse_approval_eligible']}"
               + ("" if result["coarse_approval_eligible"] else " (no prior history for this object -- Stage 1/shadow mode only)"))
    logged = orch.log_run_event(engine, resolved_log_id, object_name, result, schema=schema, environment=environment)
    if not logged:
        click.echo(f"(Not logged -- run enable-orchestrator-logging --schema {schema} to keep a shadow-mode history.)")


@cli.command("enable-orchestrator-logging")
@click.option("--schema", default="dbo", help="Schema to enable logging for -- each schema is opted in independently.")
def enable_orchestrator_logging_cmd(schema):
    _, _, engine = _ctx()
    orch.enable_orchestrator_logging(engine, schema=schema)
    click.echo(f"Orchestrator shadow-mode logging enabled for schema '{schema}' -- {schema}.OrchestratorRunEvent created.")
    click.echo("Every orchestrator-assess call against this schema will now log automatically; no per-call flag needed.")


@cli.command("disable-orchestrator-logging")
@click.option("--schema", default="dbo", help="Schema to disable logging for.")
def disable_orchestrator_logging_cmd(schema):
    _, _, engine = _ctx()
    click.echo(f"This permanently drops {schema}.OrchestratorRunEvent and all of its history.")
    orch.disable_orchestrator_logging(engine, schema=schema)
    click.echo(f"Orchestrator shadow-mode logging disabled for schema '{schema}'.")


@cli.command("add-bulk-load-sort-column")
@click.argument("table_name")
@click.argument("parent_key_column")
@click.option("--schema", default="dbo")
def add_bulk_load_sort_column_cmd(table_name, parent_key_column, schema):
    """Hard rule 6: add/refresh a [Sort] column on TABLE_NAME, numbered by
    ROW_NUMBER() OVER (ORDER BY PARENT_KEY_COLUMN), so bulkops submits
    same-parent rows in the same batch. Replaces the old
    EXEC dbo.AddBulkLoadSortColumn stored-procedure step -- run this before
    bulkops for any load table with a parent lookup/master-detail field."""
    _, _, engine = _ctx()
    bad_ranges = ltp.add_bulk_load_sort_column(engine, table_name, parent_key_column, schema=schema)
    click.echo(f"[Sort] column added/refreshed on {schema}.{table_name}, ordered by {parent_key_column}.")
    if not bad_ranges:
        click.echo("Verification: every parent key's rows landed in a contiguous Sort range. Clean.")
        return
    click.echo(f"Verification FAILED -- {len(bad_ranges)} parent key(s) have a non-contiguous Sort range:")
    for r in bad_ranges:
        click.echo(f"  {r['ParentKey']}: Sort {r['MinSort']}-{r['MaxSort']} "
                   f"({r['RowCount']} rows, span {r['SortSpan']})")


@cli.command("check-load-table-duplicate-keys")
@click.argument("table_name")
@click.argument("key_column")
@click.option("--schema", default="dbo")
def check_load_table_duplicate_keys_cmd(table_name, key_column, schema):
    """Hard rule 7: check TABLE_NAME's KEY_COLUMN for duplicate or missing
    values before bulkops -- either breaks fingerprint-based result mapping
    on insert (see bulkops.py's own docstring). Replaces the old
    EXEC dbo.CheckLoadTableDuplicateKeys stored-procedure step. Exits
    nonzero if anything is found, so this can gate a script."""
    _, _, engine = _ctx()
    duplicates, missing_key_count = ltp.check_load_table_duplicate_keys(
        engine, table_name, key_column, schema=schema
    )
    if not duplicates and not missing_key_count:
        click.echo(f"OK -- {key_column} on {schema}.{table_name} has no duplicates or missing values.")
        return
    if duplicates:
        click.echo(f"Duplicate {key_column} values in {schema}.{table_name}:")
        for d in duplicates:
            click.echo(f"  {d['DuplicateKey']!r} -- {d['Occurrences']} occurrences")
    if missing_key_count:
        click.echo(f"{missing_key_count} row(s) in {schema}.{table_name} have a NULL/missing {key_column}.")
    raise SystemExit(1)


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


@cli.command("resolve-record-types")
@click.argument("object_name")
@click.option("--schema", default="dbo")
def resolve_record_types_cmd(object_name, schema):
    """Query the target org's real RecordType rows for object_name and
    write them into [schema].[RecordTypeMap] (roadmap #36, hard rule 15)
    -- a plain reference table to JOIN against by DeveloperName when
    building a transform that populates RecordTypeId, instead of ever
    hand-copying a raw, org-specific Id from the source."""
    _, sf, engine = _ctx()
    count = rt.resolve_record_types(sf, engine, object_name, schema=schema)
    if count == 0:
        click.echo(f"No RecordType rows found for {object_name} in this org -- nothing written.")
        return
    click.echo(f"Wrote {count} RecordType row(s) for {object_name} to {schema}.RecordTypeMap.")


@cli.command("generate-target-data-model")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--output", "output_path", required=True, help="Output .md file path (contains a fenced ```mermaid``` block).")
@click.option("--mapping-path", default=None, help="Scope each object's attribute list to fields flagged Migrate Data = Yes instead of the Id/Name/required/reference default.")
def generate_target_data_model_cmd(object_names, output_path, mapping_path):
    """Generate a Mermaid ERD (roadmap #57) for a target-org data model --
    relationships come straight from live describe() via load_order.py,
    never guessed. Master-detail renders as a solid line, lookup as
    dashed -- the one real SDMN-style distinction Mermaid can express
    natively."""
    _, sf, _e = _ctx()
    text_out = dmd.generate_target_model_diagram(sf, list(object_names), mapping_path=mapping_path)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text_out)
    click.echo(f"Wrote {output_path} ({len(object_names)} object(s))")


@cli.command("generate-source-data-model")
@click.option("--subject-area", "subject_areas", multiple=True, required=True, help='Repeatable: "Name:Table1,Table2" -- an explicit, human-chosen grouping. Not auto-clustered.')
@click.option("--output-dir", required=True, help="Directory to write one <Name>.md file per subject area into.")
@click.option("--schema", default="dbo")
@click.option("--mapping-path", default=None, help="Scope each table's attribute list to source fields flagged Migrate Data = Yes instead of showing every column.")
def generate_source_data_model_cmd(subject_areas, output_dir, schema, mapping_path):
    """Generate one Mermaid ERD per subject area (roadmap #57) for source
    staging tables. Relationships are a NAMING-CONVENTION GUESS ONLY --
    staging tables carry no foreign keys -- always labeled "(guessed)" and
    printed here for explicit human review, never silently trusted."""
    _, _, engine = _ctx()
    os.makedirs(output_dir, exist_ok=True)

    for area in subject_areas:
        if ":" not in area:
            raise click.BadParameter(f'--subject-area must be "Name:Table1,Table2", got: {area!r}')
        name, tables_csv = area.split(":", 1)
        table_names = [t.strip() for t in tables_csv.split(",") if t.strip()]

        text_out, guesses = dmd.generate_source_model_diagram(engine, table_names, schema=schema, mapping_path=mapping_path)
        out_path = os.path.join(output_dir, f"{name}.md")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text_out)

        click.echo(f"Wrote {out_path} ({len(table_names)} table(s))")
        if guesses:
            click.echo(f"  {len(guesses)} guessed relationship(s) -- review before trusting:")
            for g in guesses:
                click.echo(f"    {g['child']}.{g['field']} -> {g['parent']} (guessed)")
        else:
            click.echo("  No relationships guessed for this subject area.")


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
@click.option("--reprofile", is_flag=True, help="Force a fresh profile even if this object was already profiled in this schema (roadmap #47). Default: skip and show the existing profile.")
def profile_salesforce_cmd(object_name, where, schema, top_n_values, reprofile):
    s, sf, engine = _ctx()
    if not reprofile:
        already, last_at = pf.is_already_profiled(engine, object_name, "salesforce", schema=schema)
        if already:
            click.echo(f"Already profiled on {last_at} -- pass --reprofile to force a refresh.")
            _print_profile_preview(engine, object_name, "salesforce", schema)
            return
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
@click.option("--reprofile", is_flag=True, help="Force a fresh profile even if this table was already profiled in this schema (roadmap #47). Default: skip and show the existing profile.")
def profile_sql_table_cmd(table_name, schema, top_n_values, distinct_threshold, reprofile):
    _, _, engine = _ctx()
    if not reprofile:
        already, last_at = pf.is_already_profiled(engine, table_name, "sql_table", schema=schema)
        if already:
            click.echo(f"Already profiled on {last_at} -- pass --reprofile to force a refresh.")
            _print_profile_preview(engine, table_name, "sql_table", schema)
            return
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


@cli.command("generate-adversarial-mock-data")
@click.argument("object_name")
@click.option("--count", default=50, help="Total mock rows to generate -- must be >= the sum of every --scenario's row count.")
@click.option("--scenario", "scenarios", multiple=True, required=True,
              help="scenario:field:rows, repeatable -- scenario is one of duplicate_key/oversized_string/"
                   "missing_required/invalid_picklist/bad_reference. Rows are assigned to scenarios in "
                   "disjoint ranges in the order given, so a row has at most one deliberate corruption.")
@click.option("--schema", default="dbo")
def generate_adversarial_mock_data_cmd(object_name, count, scenarios, schema):
    """Deliberately provoke known Salesforce Bulk API failure classes in
    mock data (roadmap #62), so a validation-rule collision or pre-flight-
    check gap surfaces during Dev testing, not during a real client load.
    Writes to <Object>_Mock_Adversarial (never <Object>_Mock), tagging
    every corrupted row's scenario in REF_AdversarialScenario -- REF_-
    prefixed (hard rule 13) so bulkops.py never sends it to Salesforce;
    the table can go straight into a real bulkops call as-is."""
    s, sf, engine = _ctx()
    scenario_map = {}
    for item in scenarios:
        parts = item.split(":")
        if len(parts) != 3 or not parts[2].isdigit():
            raise click.BadParameter(f"--scenario must be scenario:field:rows, got: {item!r}")
        name, field, rows = parts
        if name in scenario_map:
            # Found in review: a repeated scenario name used to silently
            # overwrite the earlier one (dict-keyed-by-name), dropping a
            # --scenario flag the user explicitly passed with no warning
            # at all -- each of the 5 scenario types only ever targets one
            # field/row-count today, so a repeat is always a mistake, not
            # a way to apply the same scenario to two fields.
            raise click.BadParameter(f"--scenario '{name}' was given more than once -- each scenario can only be used once per run.")
        scenario_map[name] = {"field": field, "rows": int(rows)}

    rows_written, applied, skipped = amd.generate_adversarial_mock_data(
        sf, engine, object_name, count, s.mockaroo_api_key, scenario_map, schema=schema,
    )
    click.echo(f"Wrote {rows_written} mock row(s) to {schema}.{object_name}_Mock_Adversarial")
    for a in applied:
        click.echo(f"  {a['scenario']}: {a['rows']} row(s) corrupted on {a['field']} (see REF_AdversarialScenario)")
    if skipped:
        click.echo(f"Skipped {len(skipped)} field(s) with no mock mapping (reference/multipicklist/etc.):")
        for name, typ in skipped:
            click.echo(f"  {name} ({typ})")


@cli.command("generate-related-mock-data")
@click.argument("object_names", nargs=-1, required=True)
@click.option("--count", "counts", multiple=True, required=True,
              help="NAME=N or NAME=N-M, repeatable. Top-level (no in-scope parent) objects get N "
                   "total rows; objects nested under a parent get N rows PER parent row. N-M picks "
                   "a random count per parent in that inclusive range (e.g. 1-2 for '1 or 2 children "
                   "each'; 0-1 for 'roughly half the parents get one') via Snowfakery's own "
                   "random_number() -- a statistical split, not a guaranteed exact percentage.")
@click.option("--schema", default="dbo")
def generate_related_mock_data_cmd(object_names, counts, schema):
    s, sf, engine = _ctx()
    object_names = list(object_names)

    count_map = {}
    for item in counts:
        if "=" not in item:
            raise click.BadParameter(f"--count must be NAME=N or NAME=N-M, got: {item!r}")
        name, _, n = item.partition("=")
        if "-" in n:
            lo_n, _, hi_n = n.partition("-")
            if not (lo_n.isdigit() and hi_n.isdigit()):
                raise click.BadParameter(f"--count range must be NAME=N-M with integers, got: {item!r}")
            count_map[name] = f"${{{{random_number(min={int(lo_n)},max={int(hi_n)})}}}}"
        else:
            count_map[name] = int(n)

    (recipe_path, skipped_by_object, primary_parent, secondary_exact_parents,
     secondary_random_parents, fields_by_object,
     polymorphic_children) = sfd.build_recipe(sf, object_names, count_map)
    click.echo(f"Recipe written to {recipe_path} (review/hand-edit, or re-run directly with `snowfakery {recipe_path}`)")
    for child, parent in primary_parent.items():
        note = ""
        if secondary_exact_parents.get(child):
            note += f"; also exactly references {', '.join(secondary_exact_parents[child])}"
        if secondary_random_parents.get(child):
            note += (f"; also randomly references {', '.join(secondary_random_parents[child])} "
                     f"(not scoped to the same {parent} -- see roadmap #6)")
        click.echo(f"  {child} nested under {parent}{note}")
    for child, info in polymorphic_children.items():
        note = ""
        if info["extra_refs"]:
            note = f"; each cohort also references {', '.join(info['extra_refs'])}"
        click.echo(
            f"  {child} split into one cohort per {info['field']} target "
            f"({', '.join(info['targets'])}), tagged via _ParentType{note}"
        )

    rows_written = sfd.run_recipe(
        engine, recipe_path, object_names, fields_by_object,
        primary_parent=primary_parent,
        secondary_exact_parents=secondary_exact_parents,
        secondary_random_parents=secondary_random_parents,
        polymorphic_children=polymorphic_children,
        schema=schema,
    )
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


@cli.command("set-mapping-script")
@click.argument("object_name")
@click.argument("mapping_path")
@click.option("--dir", "target_dir", type=click.Choice(["transformations", "source_ingestion"]),
              default="transformations", help="Which numbered script folder to resolve the script from.")
def set_mapping_script_cmd(object_name, mapping_path, target_dir):
    """Fill in the mapping doc's "Transform Script:" header field for
    object_name with the real transform script (auto-resolved, highest-
    numbered match) -- run this only after the script has actually been
    built, as its own step right after "Build the transform" in the
    standard workflow, never before."""
    filename = mpd.set_transform_script(mapping_path, object_name, script_subdir=target_dir)
    click.echo(f"{mapping_path} [{object_name}]: Transform Script set to {filename}")


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
    if result["duplicate_implemented_columns"]:
        click.echo(f"Duplicate column(s) in {transform_sql_path}'s own INSERT INTO/CREATE TABLE list "
                   "(hard rule 14 -- this breaks the SQL outright, fix before running it):")
        for field in result["duplicate_implemented_columns"]:
            click.echo(f"  {field}")
    if result["duplicate_target_fields"]:
        click.echo("Target field chosen by more than one row in this sheet (hard rule 14):")
        for target, sources in result["duplicate_target_fields"].items():
            click.echo(f"  {target}  <-  {', '.join(s or '(blank source)' for s in sources)}")
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


@cli.command("check-required-mappings")
@click.argument("object_name")
@click.argument("mapping_path")
def check_required_mappings_cmd(object_name, mapping_path):
    """Flag every mapping-doc row marked Migrate Data = Yes with no Target
    Field chosen yet (roadmap #49), and attempt a describe()-driven
    suggestion for each. Read-only -- never writes into the mapping doc."""
    _, sf, _e = _ctx()
    results = am.suggest_for_unmapped_required_fields(sf, mapping_path, object_name)

    if not results:
        click.echo(f"No gaps -- every Migrate Data = Yes row on {object_name} already has a Target Field.")
        return

    click.echo(f"{len(results)} field(s) flagged Migrate Data = Yes with no Target Field chosen on {object_name}:")
    for r in results:
        if r["suggested_target_field"]:
            click.echo(f"  {r['source_field']} -> suggest {r['suggested_target_field']} "
                       f"({r['match_method']}, {r['match_score']:.0%})")
        else:
            click.echo(f"  {r['source_field']} -> no confident suggestion found, needs manual review")


@cli.command("compare-reference-record")
@click.argument("object_name")
@click.argument("load_table")
@click.argument("record_id")
@click.option("--migration-key", "migration_key_field", required=True, help="Migration-key field name, e.g. Legacy_Id__c -- read directly off the live record to find its matching Load table row.")
@click.option("--schema", default="dbo")
@click.option("--key-column", default="LoadId", help="Load table's local unique key column (excluded from the diff).")
@click.option("--id-column", default="Id", help="Load table's Salesforce Id writeback column (excluded from the diff).")
@click.option("--error-column", default="Error", help="Load table's Error writeback column (excluded from the diff).")
@click.option("--ref-prefix", default="REF_", help="Load table columns starting with this prefix (case-insensitive) are human-only SQL-side audit fields (hard rule 13) -- excluded from the diff entirely.")
def compare_reference_record_cmd(object_name, load_table, record_id, migration_key_field,
                                  schema, key_column, id_column, error_column, ref_prefix):
    """Diff a live, hand-created reference record against the Load table
    row its migration key corresponds to (roadmap #51) -- a review aid for
    fixing the transform, never written back anywhere."""
    _, sf, engine = _ctx()
    result = rr.compare_reference_record(
        sf, engine, object_name, load_table, record_id, migration_key_field,
        schema=schema, key_column=key_column, id_column=id_column, error_column=error_column,
        ref_prefix=ref_prefix,
    )
    click.echo(f"Matched via {migration_key_field} = '{result['migration_key_value']}'")

    mismatches = [f for f in result["fields"] if not f["match"]]
    for f in result["fields"]:
        marker = "  " if f["match"] else "! "
        click.echo(f"{marker}{f['field']}: load={f['load_table_value']!r}  live={f['live_value']!r}")

    if mismatches:
        click.echo(f"\n{len(mismatches)} of {len(result['fields'])} field(s) differ -- see '!' rows above.")
    else:
        click.echo(f"\nAll {len(result['fields'])} field(s) match.")


@cli.command("auto-map")
@click.argument("object_name")
@click.argument("mapping_path")
@click.argument("source_table")
@click.option("--schema", default="dbo")
def auto_map_cmd(object_name, mapping_path, source_table, schema):
    s, sf, engine = _ctx()
    is_review_pass, last_mapped_at = am.was_already_auto_mapped(engine, source_table, object_name, schema=schema)

    suggestions = am.suggest_mappings(sf, engine, object_name, source_table, schema=schema)
    result = mpd.apply_auto_map_suggestions(mapping_path, object_name, object_name, suggestions)

    matched = sum(1 for s_ in suggestions if s_["target_field"])
    yes = sum(1 for s_ in suggestions if s_["migrate_recommended"] == "Yes")
    no = sum(1 for s_ in suggestions if s_["migrate_recommended"] == "No")
    review = sum(1 for s_ in suggestions if s_["migrate_recommended"] == "Review")

    if is_review_pass:
        # Roadmap #47: a later pass over the same source/target pair is a
        # review, not a first draft -- lead with what's actually useful to
        # know reviewing existing work (what a human already decided vs.
        # what's freshly suggested for the fields still blank), not the
        # first-pass-style single combined count.
        click.echo(f"Reviewing existing mapping (last auto-mapped {last_mapped_at}) for "
                   f"{source_table} -> {object_name}")
        click.echo(f"  {result['skipped_human_filled']} field(s) already decided by a human -- untouched")
        click.echo(f"  {result['applied']} field(s) still blank -- freshly suggested this pass "
                   f"({yes} Yes, {no} No, {review} Review)")
    else:
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


@cli.command("generate-migration-run-book")
@click.argument("output_path")
@click.option("--tab", "tab_name", required=True, help="New tab name (e.g. Dev1, UAT, PROD) -- refuses to overwrite an existing tab.")
@click.option("--objects", "object_names", multiple=True, help="Auto-fills the Load phase from analyze-load-order's results. Omit for a blank phase to fill in by hand.")
@click.option("--schema", default="dbo")
@click.option("--template", "template_path", default=None, help="Custom Migration Run Book template -- falls back to docs/MIGRATION_RUN_BOOK_TEMPLATE.md if omitted.")
@click.option("--project", "project_name", default=None, help="Project name shown in the header.")
@click.option("--source-env", default=None, help="Source environment shown in the header (defaults to the configured SQL Server mirror DB).")
@click.option("--target-env", default=None, help="Target environment shown in the header (defaults to the configured Salesforce org alias).")
@click.option("--ticket-url", default=None, help="Link to this project's ticket-system project, shown in the header (defaults to TICKET_SYSTEM_URL if configured).")
@click.option("--ticket-label", default=None, help="Ticket system name shown in the header, e.g. JIRA (defaults to TICKET_SYSTEM_LABEL).")
def generate_migration_run_book_cmd(output_path, tab_name, object_names, schema, template_path,
                           project_name, source_env, target_env, ticket_url, ticket_label):
    s, _, engine = _ctx()
    kwargs = {
        "schema": schema,
        "project_name": project_name,
        "source_env": source_env or f"SQL Server: {s.sql_database}",
        "target_env": target_env or (s.sf_org_alias or None),
        "ticket_url": ticket_url or (s.ticket_system_url or None),
        "ticket_label": ticket_label or s.ticket_system_label,
    }
    if template_path:
        kwargs["template_path"] = template_path
    if object_names:
        kwargs["engine"] = engine
        kwargs["object_names"] = list(object_names)
    path = mrb.generate_migration_run_book(output_path, tab_name, **kwargs)
    click.echo(f"Wrote {path} (tab '{tab_name}')")
    if object_names:
        click.echo(f"Load phase auto-filled from {schema}.ObjectLoadOrder for: {', '.join(object_names)}")


@cli.command("add-migration-run-book-pass")
@click.argument("path")
@click.option("--from-tab", required=True, help="Existing tab to copy the recipe from (e.g. Dev1).")
@click.option("--to-tab", required=True, help="New tab name for the fresh pass (e.g. UAT) -- refuses to overwrite an existing tab.")
@click.option("--project", "project_name", default=None, help="Override the carried-forward Project name.")
@click.option("--source-env", default=None, help="Override the carried-forward Source Environment.")
@click.option("--target-env", default=None, help="Target environment for this pass -- never carried forward automatically (Dev/UAT/PROD are different orgs); defaults to the configured Salesforce org alias.")
@click.option("--ticket-url", default=None, help="Override the carried-forward ticket-system project link.")
@click.option("--ticket-label", default=None, help="Override the carried-forward ticket system name.")
def add_migration_run_book_pass_cmd(path, from_tab, to_tab, project_name, source_env, target_env, ticket_url, ticket_label):
    s, _, _e = _ctx()
    mrb.add_migration_run_book_pass(
        path, from_tab, to_tab,
        project_name=project_name, source_env=source_env,
        target_env=target_env or (s.sf_org_alias or None),
        ticket_url=ticket_url, ticket_label=ticket_label,
    )
    click.echo(f"Copied '{from_tab}' -> '{to_tab}' in {path} (recipe carried forward, result columns blanked)")


@cli.command("update-migration-run-book")
@click.argument("path")
@click.option("--tab", "tab_name", required=True, help="Migration Run Book tab to sync into.")
@click.option("--schema", default="dbo")
def update_migration_run_book_cmd(path, tab_name, schema):
    _, _, engine = _ctx()
    result = mrb.sync_run_book_from_log(engine, path, tab_name, schema=schema)
    if result.get("message"):
        click.echo(result["message"])
    else:
        click.echo(f"Synced {result['synced']} new {schema}.BulkOpsLog row(s) into '{tab_name}': "
                   f"{result['updated']} filled in, {result['inserted']} inserted.")

    source_result = mrb.sync_source_ingestion_to_run_book(engine, path, tab_name, schema=schema)
    if source_result.get("message"):
        click.echo(source_result["message"])
    else:
        click.echo(f"Synced {source_result['synced']} new {schema}.SourceIngestionLog row(s) into '{tab_name}': "
                   f"{source_result['updated']} filled in, {source_result['inserted']} inserted.")


@cli.command("generate-run-book-flowchart")
@click.argument("path")
@click.option("--tab", "tab_name", required=True, help="Migration Run Book tab to diagram.")
@click.option("--output", "output_path", required=True, help="Output .md file path (contains a fenced ```mermaid``` block).")
def generate_run_book_flowchart_cmd(path, tab_name, output_path):
    """Generate a Mermaid process-flow diagram (roadmap #52) straight from
    a Migration Run Book tab's own Stage/Object/Dependency/Status columns
    -- one subgraph per phase, one node per step, edges from the
    Dependency column's "After: X" text, node color matching the
    workbook's own Status palette. Deliberately simple for v1: read-only,
    no Salesforce/SQL connection needed, just this local .xlsx file."""
    mermaid_text, summary = mrb.generate_run_book_flowchart(path, tab_name)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(mermaid_text)
    click.echo(f"Wrote {output_path} ({summary['phases']} phase(s), {summary['nodes']} step(s), {summary['edges']} dependency edge(s))")
    if summary["unresolved_dependencies"]:
        click.echo(f"Unresolved dependency mention(s), dropped rather than guessed: {summary['unresolved_dependencies']}")
    if summary["unparsed_dependency_notes"]:
        click.echo("Dependency note(s) that didn't match the 'After: X' format -- not drawn as an edge, may be a real dependency stated in free text:")
        for note in summary["unparsed_dependency_notes"]:
            click.echo(f"  {note}")


@cli.command("generate-pass-summary")
@click.argument("path")
@click.option("--tab", "tab_name", required=True, help="Migration Run Book tab to summarize.")
@click.option("--output", "output_path", required=True, help="Output .md file path.")
@click.option("--schema", default="dbo")
@click.option("--load-table", "load_tables", multiple=True,
              help="Object=TableName, repeatable -- enables a plain-language root cause (via triage-failures) "
                   "for that object's failures instead of just a raw failed count. Never guessed: an object "
                   "left out just points at the Run Book's own Notes/Error Details columns.")
def generate_pass_summary_cmd(path, tab_name, output_path, schema, load_tables):
    """Draft a plain-English, client-facing pass summary (roadmap #66)
    from a Migration Run Book tab's own Load-phase results -- object
    count, total/succeeded/failed records, and (with --load-table) a
    plain-language root cause per failure signature via triage-failures
    (#61). Plain Markdown for v1."""
    _, _, engine = _ctx()
    load_table_map = _parse_object_value_pairs(load_tables, "--load-table")

    summary_text = ps.generate_pass_summary(path, tab_name, engine=engine, schema=schema, load_tables=load_table_map)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(summary_text)
    click.echo(f"Wrote {output_path}")


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
