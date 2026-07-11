import validators_lookup as vl


def test_list_system_validators_empty_when_missing(tmp_path):
    assert vl.list_system_validators(str(tmp_path / "does_not_exist")) == []


def test_list_system_validators_sorted_md_only(tmp_path):
    system_dir = tmp_path / "system"
    system_dir.mkdir()
    (system_dir / "migration-key-integrity.md").write_text("")
    (system_dir / "parent-batch-sort.md").write_text("")
    (system_dir / "notes.txt").write_text("")
    assert vl.list_system_validators(str(tmp_path)) == [
        "migration-key-integrity.md", "parent-batch-sort.md",
    ]


def test_object_validator_path_none_when_missing(tmp_path):
    assert vl.object_validator_path("Task", str(tmp_path)) is None


def test_object_validator_path_found(tmp_path):
    (tmp_path / "Task.md").write_text("# Task validator")
    path = vl.object_validator_path("Task", str(tmp_path))
    assert path is not None
    assert path.endswith("Task.md")


def test_read_object_validator_returns_none_when_missing(tmp_path):
    assert vl.read_object_validator("Task", str(tmp_path)) is None


def test_read_object_validator_returns_contents(tmp_path):
    (tmp_path / "Task.md").write_text("# Task validator\n\nSome content.", encoding="utf-8")
    content = vl.read_object_validator("Task", str(tmp_path))
    assert content == "# Task validator\n\nSome content."
