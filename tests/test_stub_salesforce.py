"""Coverage for the shared stub Salesforce client itself (tests/
stub_salesforce.py) -- this is now shared infrastructure other tests and
ad hoc verification scripts depend on, so it earns its own direct tests
rather than only being exercised incidentally through bulkops.py."""
import pandas as pd

from stub_salesforce import StubBulkHandler, StubSF, describe_fields


def test_describe_fields_marks_id_field_non_writable():
    fields = describe_fields(["Name", "LegacyId__c"])
    by_name = {f["name"]: f for f in fields}
    assert by_name["Id"]["createable"] is False
    assert by_name["Id"]["updateable"] is False
    assert by_name["Name"]["createable"] is True
    assert by_name["LegacyId__c"]["updateable"] is True


def test_stub_sf_dispatches_describe_and_bulk2_per_object(tmp_path):
    sf = StubSF(
        {"Account": describe_fields(["Name"]), "Contact": describe_fields(["LastName"])},
        {"Account": StubBulkHandler("Name,sf__Id\nAcme,001X\n", ""),
         "Contact": StubBulkHandler("LastName,sf__Id\nSmith,003X\n", "")},
    )
    assert sf.Account.describe()["fields"][0]["name"] == "Id"
    assert {f["name"] for f in sf.Contact.describe()["fields"]} == {"Id", "LastName"}
    assert sf.bulk2.Account is sf.bulk2.Account  # same handler instance each access
    assert sf.bulk2.Account.get_successful_records("job") == "Name,sf__Id\nAcme,001X\n"
    assert sf.bulk2.Contact.get_successful_records("job") == "LastName,sf__Id\nSmith,003X\n"


def test_stub_bulk_handler_fixed_mode_ignores_csv_content(tmp_path):
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("Name\nWhatever\n")
    handler = StubBulkHandler(success_csv="Name,sf__Id\nA,001X\n", failure_csv="")
    jobs = handler.insert(str(csv_path))
    assert jobs == [{"job_id": "JOB1"}]
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
