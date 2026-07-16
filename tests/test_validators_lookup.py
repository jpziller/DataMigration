import pytest

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


@pytest.mark.parametrize("bad_name", [
    "../../etc/passwd", "..\\..\\secrets", "sub/dir", "sub\\dir", "..", "",
])
def test_object_validator_path_rejects_path_traversal(tmp_path, bad_name):
    with pytest.raises(ValueError):
        vl.object_validator_path(bad_name, str(tmp_path))


def test_parse_frontmatter_full():
    text = (
        "---\n"
        "type: ObjectValidator\n"
        "title: Task validator\n"
        "tags:\n"
        "  - task\n"
        "  - polymorphic-lookup\n"
        "---\n"
        "# Task validator\n\nBody content.\n"
    )
    meta, body = vl.parse_frontmatter(text)
    assert meta["type"] == "ObjectValidator"
    assert meta["title"] == "Task validator"
    assert meta["tags"] == ["task", "polymorphic-lookup"]
    assert body == "# Task validator\n\nBody content.\n"


def test_parse_frontmatter_absent():
    text = "# Plain validator\n\nNo frontmatter here.\n"
    meta, body = vl.parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_malformed_yaml_tolerated():
    text = "---\n: : :\n---\n# Body\n"
    meta, body = vl.parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_unclosed_fence_tolerated():
    text = "---\ntype: SystemValidator\n# Body without a closing fence\n"
    meta, body = vl.parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_non_dict_yaml_tolerated():
    text = "---\n- a\n- b\n---\n# Body\n"
    meta, body = vl.parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_list_system_validators_excludes_okf_reserved_names(tmp_path):
    system_dir = tmp_path / "system"
    system_dir.mkdir()
    (system_dir / "parent-batch-sort.md").write_text("")
    (system_dir / "index.md").write_text("")
    (system_dir / "log.md").write_text("")
    assert vl.list_system_validators(str(tmp_path)) == ["parent-batch-sort.md"]
