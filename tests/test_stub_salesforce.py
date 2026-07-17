"""Coverage for the shared stub Salesforce client itself (tests/
stub_salesforce.py) -- this is now shared infrastructure other tests and
ad hoc verification scripts depend on, so it earns its own direct tests
rather than only being exercised incidentally through bulkops.py."""
import pandas as pd
import pytest

from stub_salesforce import StubBulkHandler, StubSF, describe_fields


def test_describe_fields_marks_id_field_non_writable():
    fields = describe_fields(["Name", "LegacyId__c"])
    by_name = {f["name"]: f for f in fields}
    assert by_name["Id"]["createable"] is False
    assert by_name["Id"]["updateable"] is False
    assert by_name["Name"]["createable"] is True
    assert by_name["LegacyId__c"]["updateable"] is True


def test_stub_sf_dispatches_describe_and_bulk2_per_object(tmp_path):
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("Name\nWhatever\n")
    sf = StubSF(
        {"Account": describe_fields(["Name"]), "Contact": describe_fields(["LastName"])},
        {"Account": StubBulkHandler("Name,sf__Id\nAcme,001X\n", ""),
         "Contact": StubBulkHandler("LastName,sf__Id\nSmith,003X\n", "")},
    )
    assert sf.Account.describe()["fields"][0]["name"] == "Id"
    assert {f["name"] for f in sf.Contact.describe()["fields"]} == {"Id", "LastName"}
    assert sf.bulk2.Account is sf.bulk2.Account  # same handler instance each access

    sf.bulk2.Account.insert(str(csv_path))
    sf.bulk2.Contact.insert(str(csv_path))
    assert sf.bulk2.Account.get_successful_records("JOB1") == "Name,sf__Id\nAcme,001X\n"
    assert sf.bulk2.Contact.get_successful_records("JOB1") == "LastName,sf__Id\nSmith,003X\n"


def test_stub_bulk_handler_fixed_mode_ignores_csv_content(tmp_path):
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("Name\nWhatever\n")
    handler = StubBulkHandler(success_csv="Name,sf__Id\nA,001X\n", failure_csv="")
    jobs = handler.insert(str(csv_path))
    # numberRecordsProcessed/Failed match real simple_salesforce's own
    # _upload_data() return shape -- bulkops.py's _fetch_job_results()
    # relies on these being present and accurate (roadmap #74).
    assert jobs == [{"job_id": "JOB1", "numberRecordsProcessed": 1, "numberRecordsFailed": 0}]
    assert handler.get_successful_records("JOB1") == "Name,sf__Id\nA,001X\n"
    assert handler.get_failed_records("JOB1") == ""


def test_stub_bulk_handler_job_dict_counts_include_failures_in_processed(tmp_path):
    """numberRecordsProcessed is successes + failures combined (real Bulk
    API 2.0 semantics -- numberRecordsFailed is the failed subset WITHIN
    it, not additional to it). Getting this backwards in bulkops.py's own
    expected_total calculation once made every job with any failure at
    all retry its full backoff budget for real, found live when the test
    suite's own runtime ballooned from ~10s to ~265s."""
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("Name\nWhatever\n")
    handler = StubBulkHandler(
        success_csv="Name,sf__Id\nA,001X\n",
        failure_csv="Name,sf__Error\nB,SOME_ERROR:bad\n",
    )
    jobs = handler.insert(str(csv_path))
    assert jobs == [{"job_id": "JOB1", "numberRecordsProcessed": 2, "numberRecordsFailed": 1}]


def test_stub_bulk_handler_results_ready_after_calls_delays_both_reads(tmp_path):
    """Simulates the real Bulk API 2.0 race bulkops.py's _fetch_job_results()
    retries against: the first N-1 calls to EITHER get_successful_records()
    or get_failed_records() for a job return empty, real data from call N
    on -- tracked per (job_id, kind) so success and failure become ready
    together, matching how _fetch_job_results() always calls both once per
    retry attempt."""
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("Name\nWhatever\n")
    handler = StubBulkHandler(
        success_csv="Name,sf__Id\nA,001X\n", failure_csv="",
        results_ready_after_calls=3,
    )
    handler.insert(str(csv_path))

    assert handler.get_successful_records("JOB1") == ""
    assert handler.get_failed_records("JOB1") == ""
    assert handler.get_successful_records("JOB1") == ""
    assert handler.get_failed_records("JOB1") == ""
    assert handler.get_successful_records("JOB1") == "Name,sf__Id\nA,001X\n"
    assert handler.get_failed_records("JOB1") == ""


def test_stub_bulk_handler_dynamic_mode_assigns_sequential_ids_and_fails_every_nth(tmp_path):
    csv_path = tmp_path / "payload.csv"
    pd.DataFrame({"Name": [f"Row{i}" for i in range(1, 8)]}).to_csv(csv_path, index=False)

    handler = StubBulkHandler(echo_cols=["Name"], fail_every_n=3, id_prefix="001")
    handler.insert(str(csv_path))

    succ = pd.read_csv(pd.io.common.StringIO(handler.get_successful_records("JOB1")), dtype=str)
    fail = pd.read_csv(pd.io.common.StringIO(handler.get_failed_records("JOB1")), dtype=str)

    # Rows 3, 6 (1-indexed) fail; the other 5 succeed with sequential fake Ids.
    assert list(fail["Name"]) == ["Row3", "Row6"]
    assert list(succ["Name"]) == ["Row1", "Row2", "Row4", "Row5", "Row7"]
    assert list(succ["sf__Id"]) == [f"001{n:015d}" for n in range(1, 6)]
    assert all("deliberately failed" in msg for msg in fail["sf__Error"])


def test_stub_bulk_handler_dynamic_mode_splits_into_multiple_jobs(tmp_path):
    csv_path = tmp_path / "payload.csv"
    pd.DataFrame({"Name": [f"Row{i}" for i in range(1, 6)]}).to_csv(csv_path, index=False)

    handler = StubBulkHandler(echo_cols=["Name"], job_count=2, id_prefix="001")
    jobs = handler.insert(str(csv_path))

    assert [j["job_id"] for j in jobs] == ["JOB1", "JOB2"]
    job1 = pd.read_csv(pd.io.common.StringIO(handler.get_successful_records("JOB1")), dtype=str)
    job2 = pd.read_csv(pd.io.common.StringIO(handler.get_successful_records("JOB2")), dtype=str)
    # 5 rows split into 2 jobs, order-preserving, no row lost or duplicated.
    assert list(job1["Name"]) == ["Row1", "Row2", "Row3"]
    assert list(job2["Name"]) == ["Row4", "Row5"]
    # Fake Ids are globally sequential across jobs, not reset per job.
    assert list(job1["sf__Id"]) + list(job2["sf__Id"]) == [f"001{n:015d}" for n in range(1, 6)]


def test_stub_bulk_handler_fixed_mode_supports_multiple_jobs():
    handler = StubBulkHandler(jobs=[
        ("Name,sf__Id\nA,001X\n", ""),
        ("", "Name,sf__Error\nB,SOME_ERROR\n"),
    ])
    jobs = handler.insert("unused.csv")
    assert [j["job_id"] for j in jobs] == ["JOB1", "JOB2"]
    assert handler.get_successful_records("JOB1") == "Name,sf__Id\nA,001X\n"
    assert handler.get_failed_records("JOB1") == ""
    assert handler.get_successful_records("JOB2") == ""
    assert handler.get_failed_records("JOB2") == "Name,sf__Error\nB,SOME_ERROR\n"


def test_stub_bulk_handler_rejects_neither_mode_configured():
    with pytest.raises(ValueError, match="fixed mode.*dynamic mode|got neither"):
        StubBulkHandler()


def test_stub_bulk_handler_rejects_both_modes_configured():
    with pytest.raises(ValueError, match="not both"):
        StubBulkHandler(success_csv="x", jobs=[("x", "")])


def test_stub_bulk_handler_rejects_reuse_across_two_insert_calls(tmp_path):
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("Name\nWhatever\n")
    handler = StubBulkHandler(success_csv="Name,sf__Id\nA,001X\n", failure_csv="")
    handler.insert(str(csv_path))
    with pytest.raises(RuntimeError, match="already had a submission"):
        handler.insert(str(csv_path))
