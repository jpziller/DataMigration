"""Reusable stub Salesforce client for exercising bulkops.py's real logic
(pre-flight checks, batch sizing, fingerprint-based result mapping,
writeback, activity logging) without ever calling a live org -- hard rule
2 forbids running bulkops against a real org "to test," so this is the
one and only way that logic gets a real workout in this repo, whether
from a permanent pytest file or an ad hoc verification script.

Written once here, imported everywhere -- previously hand-rewritten
slightly differently in two places in the same session (a permanent test
file and a scratch script) before being consolidated into this module.

Only `insert` is implemented, since that's the only operation anything
built on this so far has needed -- extend `StubBulkHandler` with
update/upsert/delete simulation only once something actually exercises it.

`StubBulkDownloadHandler`/`StubSF.download_mode` (bottom of this file)
stub replicate.py's read side (`sf.bulk2.<Object>.download()`) instead --
a previously-untested code path (found in review: replicate.py had zero
test coverage at all before this), needed for a real, honest
integration test of subset_replication.py (roadmap #34) rather than
only unit-testing its pure WHERE-building logic.
"""
import os
import re

import pandas as pd


class StubObjectDescribe:
    """Wraps a plain describe()-shaped field list -- enough structure for
    bulkops.py's _preflight_check(), not a real schema."""
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


def describe_fields(columns, id_field="Id"):
    """Build a minimal describe()-shaped field list: id_field as a real,
    non-writable Id field, plus every name in columns as a generic
    createable/updateable/nillable string field. Good enough to pass
    _preflight_check() when the point of a test/demo is exercising
    bulkops.py's own logic, not modeling a specific object's real schema."""
    fields = [{"name": id_field, "type": "id", "createable": False,
               "updateable": False, "nillable": True}]
    for c in columns:
        if c == id_field:
            continue
        fields.append({
            "name": c, "type": "string", "createable": True, "updateable": True,
            "nillable": True, "defaultedOnCreate": False,
        })
    return fields


def _chunk_dataframe(df, n_chunks):
    """Split df into n_chunks roughly-equal, order-preserving pieces --
    plain Python/pandas, no numpy dependency added just for this."""
    if n_chunks <= 1 or len(df) == 0:
        return [df]
    chunk_size = -(-len(df) // n_chunks)  # ceil division
    return [df.iloc[i:i + chunk_size] for i in range(0, len(df), chunk_size)]


class StubBulkHandler:
    """A stub for one Salesforce object's sf.bulk2.<Object> handler --
    insert/update/upsert/delete all share the same simulation logic (Bulk
    API 2.0 shapes every operation's request/response the same way: submit
    a CSV, get back job ids, fetch success/failure records per job).

    **One instance is good for exactly one submission** -- real handlers
    aren't reused across bulk_op() calls either, and reuse would silently
    mix up which submission a stored result belongs to. Calling
    insert/update/upsert/delete a second time on the same instance raises.

    Two ways to use it:
    - **Fixed outcome** (precise unit tests -- exact control over which
      rows succeed/fail, including simulating more than one Bulk API job):
      pass `jobs` -- a list of (success_csv, failure_csv) tuples, one per
      simulated job, each already shaped like bulk_op()'s
      _read_result_csv() expects (echo columns + sf__Id, or echo columns +
      sf__Error). `success_csv`/`failure_csv` remain as shorthand for the
      common single-job case (`jobs=[(success_csv, failure_csv)]`).
    - **Dynamic outcome** (volume/stress tests -- realistic-shaped fake
      Ids at whatever scale, with a real failure rate to exercise
      retry/error-tracking too): pass echo_cols (required) and, optionally,
      fail_every_n and job_count. Every row succeeds with an
      auto-generated sequential fake Id (id_prefix + a zero-padded
      counter, e.g. "001000000000000001") except every fail_every_n'th
      row, which fails with a canned error message. job_count > 1 splits
      the submitted rows across that many simulated jobs, in submission
      order -- the only way anything in this repo exercises bulk_op()'s
      own cross-job success/failure aggregation loop.
    """
    def __init__(self, success_csv=None, failure_csv=None, jobs=None,
                 echo_cols=None, fail_every_n=None, job_count=1, id_prefix="001",
                 failure_message="DUPLICATE_VALUE:deliberately failed for this test"):
        if jobs is not None and (success_csv is not None or failure_csv is not None):
            raise ValueError("Pass either jobs=[...] or success_csv/failure_csv, not both.")
        if success_csv is not None or failure_csv is not None:
            jobs = [(success_csv or "", failure_csv or "")]

        if jobs is None and not echo_cols:
            raise ValueError(
                "StubBulkHandler needs either jobs=[...] / success_csv+failure_csv "
                "(fixed mode) or echo_cols (dynamic mode) -- got neither."
            )

        self._fixed_jobs = jobs
        self._echo_cols = echo_cols
        self._fail_every_n = fail_every_n
        self._job_count = job_count
        self._id_prefix = id_prefix
        self._failure_message = failure_message
        self._next_id = 1
        self._results_by_job = None  # set by insert(); reuse guard

    def insert(self, csv_file=None, batch_size=None):
        return self._submit(csv_file)

    def update(self, csv_file=None, batch_size=None):
        return self._submit(csv_file)

    def upsert(self, csv_file=None, records=None, external_id_field=None, batch_size=None):
        # Matches the real simple_salesforce.bulk2.SFBulk2Handler.upsert()
        # signature's actual parameter ORDER -- external_id_field is the
        # THIRD parameter, not the second (that's `records`, a genuine
        # positional slot here too, even though this stub never uses it,
        # specifically so a positional call binds WRONG the same way it
        # would against the real library). A prior version of this stub
        # omitted `records` entirely and put external_id_field second,
        # which meant a positional call `upsert(csv_path, external_id, ...)`
        # happened to bind correctly against the STUB even though it's
        # wrong against the real library -- found via review: the stub's
        # own regression test still passed with the old buggy positional
        # bulkops.py call reintroduced, because the stub's signature didn't
        # actually reproduce the real bug's mechanics. Require
        # external_id_field so a caller reverting to the old positional-call
        # bug fails here too, not just against a live org.
        if external_id_field is None:
            raise TypeError("upsert() requires external_id_field (by keyword)")
        return self._submit(csv_file)

    def delete(self, csv_file=None, batch_size=None):
        return self._submit(csv_file)

    def _submit(self, csv_path):
        if self._results_by_job is not None:
            raise RuntimeError(
                "This StubBulkHandler already had a submission -- construct "
                "a fresh instance per bulk_op() call (real handlers aren't "
                "reused across calls either, and reuse would silently mix "
                "up which submission a stored result belongs to)."
            )
        self._results_by_job = {}

        if self._fixed_jobs is not None:
            job_ids = []
            for i, (succ, fail) in enumerate(self._fixed_jobs):
                job_id = f"JOB{i + 1}"
                self._results_by_job[job_id] = (succ, fail)
                job_ids.append(job_id)
            return [{"job_id": j} for j in job_ids]

        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[""])
        job_ids = []
        for i, chunk_df in enumerate(_chunk_dataframe(df, self._job_count)):
            job_id = f"JOB{i + 1}"
            succ_rows, fail_rows = [], []
            for row_i, row in chunk_df.iterrows():
                if self._fail_every_n and (row_i + 1) % self._fail_every_n == 0:
                    fail_rows.append(list(row[self._echo_cols]) + [self._failure_message])
                else:
                    fake_id = f"{self._id_prefix}{self._next_id:015d}"
                    self._next_id += 1
                    succ_rows.append(list(row[self._echo_cols]) + [fake_id])

            succ_df = pd.DataFrame(succ_rows, columns=list(self._echo_cols) + ["sf__Id"])
            fail_df = pd.DataFrame(fail_rows, columns=list(self._echo_cols) + ["sf__Error"])
            self._results_by_job[job_id] = (succ_df.to_csv(index=False), fail_df.to_csv(index=False))
            job_ids.append(job_id)
        return [{"job_id": j} for j in job_ids]

    def get_successful_records(self, job_id):
        return self._results_by_job[job_id][0] or ""

    def get_failed_records(self, job_id):
        return self._results_by_job[job_id][1] or ""


class StubBulk2:
    """sf.bulk2.<ObjectName> -> that object's StubBulkHandler
    (handler_by_object[name]) -- matches simple_salesforce's own
    getattr-by-object-name shape closely enough for bulkops.py's call sites.
    Works for a single object (a one-entry dict) or several at once."""
    def __init__(self, handler_by_object):
        self._handler_by_object = handler_by_object

    def __getattr__(self, name):
        return self._handler_by_object[name]


class StubSF:
    """getattr(sf, object_name) -> a StubObjectDescribe for that object's
    fields (describe_by_object[object_name]); sf.bulk2.<name> -> that
    object's StubBulkHandler, via StubBulk2."""
    def __init__(self, describe_by_object, handler_by_object):
        self._describe_by_object = describe_by_object
        self.bulk2 = StubBulk2(handler_by_object)

    def __getattr__(self, name):
        return StubObjectDescribe(self._describe_by_object[name])


def _split_top_level(expr, delimiter):
    """Split expr on delimiter, but only where paren-depth is 0 -- so a
    delimiter inside a parenthesized group is never treated as a split
    point. Minimal, built only to match this project's own generated
    WHERE clauses (replicate.py's `where`, subset_replication.py's
    _build_child_where/_in_clause) -- not a general SOQL parser."""
    parts, depth, start = [], 0, 0
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and expr[i:i + len(delimiter)] == delimiter:
            parts.append(expr[start:i])
            i += len(delimiter)
            start = i
            continue
        i += 1
    parts.append(expr[start:])
    return parts


def _eval_soql_where(where_clause, row):
    """True/False: does row (a dict of column -> string value) match
    where_clause? Supports 'A AND B', 'A OR B' (top-level only -- this
    project's own generators never mix precedence), redundant enclosing
    parens, 'FIELD IN (...)', and 'FIELD = 'value''/'FIELD LIKE
    'pattern%''. Raises on anything else, deliberately, rather than
    silently matching or not matching an unsupported shape."""
    expr = where_clause.strip()

    or_parts = _split_top_level(expr, " OR ")
    if len(or_parts) > 1:
        return any(_eval_soql_where(p, row) for p in or_parts)
    and_parts = _split_top_level(expr, " AND ")
    if len(and_parts) > 1:
        return all(_eval_soql_where(p, row) for p in and_parts)

    atom = expr.strip()
    while atom.startswith("(") and atom.endswith(")"):
        atom = atom[1:-1].strip()

    m = re.match(r"^(\w+)\s+IN\s+\((.*)\)$", atom)
    if m:
        field, raw_values = m.groups()
        values = {v.strip().strip("'") for v in raw_values.split(",")}
        return row.get(field) in values
    m = re.match(r"^(\w+)\s*=\s*'(.*)'$", atom)
    if m:
        field, value = m.groups()
        return row.get(field) == value
    m = re.match(r"^(\w+)\s+LIKE\s+'(.*)'$", atom)
    if m:
        field, pattern = m.groups()
        regex = "^" + re.escape(pattern).replace("%", ".*") + "$"
        return bool(re.match(regex, row.get(field) or ""))
    raise ValueError(f"Stub SOQL WHERE evaluator doesn't understand: {atom!r}")


class StubBulkDownloadHandler:
    """Stub for sf.bulk2.<Object>.download(soql, path, max_records) --
    replicate.py's read side. Applies a minimal WHERE/LIMIT evaluator
    (see _eval_soql_where/_split_top_level above) against a fixed
    in-memory row set and writes the filtered/limited result as one CSV
    part file into path, real Bulk-API-2.0-CSV-part shape (all values
    strings). Not a general SOQL engine -- built only to understand the
    shapes this project's own code actually generates."""
    def __init__(self, rows):
        # rows: list of dicts, e.g. [{"Id": "001A", "Name": "Acme", ...}]
        self._rows = rows

    def download(self, soql, path=None, max_records=None):
        select_match = re.match(r"SELECT\s+(.*?)\s+FROM\s+\w+", soql, re.IGNORECASE)
        columns = [c.strip() for c in select_match.group(1).split(",")]

        where_match = re.search(r"\bWHERE\b(.*?)(\bLIMIT\b|$)", soql, re.IGNORECASE | re.DOTALL)
        where_clause = where_match.group(1).strip() if where_match and where_match.group(1).strip() else None
        limit_match = re.search(r"\bLIMIT\s+(\d+)\b", soql, re.IGNORECASE)
        limit = int(limit_match.group(1)) if limit_match else None

        matched = [r for r in self._rows if where_clause is None or _eval_soql_where(where_clause, r)]
        if limit is not None:
            matched = matched[:limit]

        os.makedirs(path, exist_ok=True)
        rows_out = [{c: r.get(c, "") for c in columns} for r in matched]
        df = pd.DataFrame(rows_out, columns=columns)
        df.to_csv(os.path.join(path, "part-0001.csv"), index=False)
