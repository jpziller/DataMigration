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
"""
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


class StubBulkHandler:
    """A stub for one Salesforce object's sf.bulk2.<Object> handler.

    Two ways to use it:
    - **Fixed outcome** (precise unit tests -- exact control over which
      rows succeed/fail): pass success_csv/failure_csv directly, already
      shaped like bulk_op()'s _read_result_csv() expects (echo columns +
      sf__Id, or echo columns + sf__Error).
    - **Dynamic outcome** (volume/stress tests -- realistic-shaped fake
      Ids at whatever scale, with a real failure rate to exercise
      retry/error-tracking too): pass echo_cols and fail_every_n instead.
      Every row succeeds with an auto-generated sequential fake Id
      (id_prefix + a zero-padded counter, e.g. "001000000000000001") except
      every fail_every_n'th row, which fails with a canned error message.
    """
    def __init__(self, success_csv=None, failure_csv=None,
                 echo_cols=None, fail_every_n=None, id_prefix="001",
                 failure_message="DUPLICATE_VALUE:deliberately failed for this test"):
        self._success_csv = success_csv
        self._failure_csv = failure_csv
        self._echo_cols = echo_cols
        self._fail_every_n = fail_every_n
        self._id_prefix = id_prefix
        self._failure_message = failure_message
        self._next_id = 1

    def insert(self, csv_path, batch_size=None):
        if self._success_csv is not None or self._failure_csv is not None:
            return [{"job_id": "JOB1"}]  # fixed mode -- nothing to compute

        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[""])
        succ_rows, fail_rows = [], []
        for i, row in df.iterrows():
            if self._fail_every_n and (i + 1) % self._fail_every_n == 0:
                fail_rows.append(list(row[self._echo_cols]) + [self._failure_message])
            else:
                fake_id = f"{self._id_prefix}{self._next_id:015d}"
                self._next_id += 1
                succ_rows.append(list(row[self._echo_cols]) + [fake_id])

        succ_df = pd.DataFrame(succ_rows, columns=list(self._echo_cols) + ["sf__Id"])
        fail_df = pd.DataFrame(fail_rows, columns=list(self._echo_cols) + ["sf__Error"])
        self._success_csv = succ_df.to_csv(index=False)
        self._failure_csv = fail_df.to_csv(index=False)
        return [{"job_id": "JOB1"}]

    def get_successful_records(self, job_id):
        return self._success_csv or ""

    def get_failed_records(self, job_id):
        return self._failure_csv or ""


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
