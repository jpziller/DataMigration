import okf_lookup as okf


def _write(path, frontmatter, body="body"):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ""
    if frontmatter is not None:
        text += "---\n" + frontmatter + "\n---\n"
    text += body + "\n"
    path.write_text(text, encoding="utf-8")


def _bundle(tmp_path):
    """A small okf/-shaped bundle with two subject areas."""
    _write(
        tmp_path / "cloud-a" / "gift-commitment-auto.md",
        'type: PlatformFinding\n'
        'title: GiftCommitmentSchedule is auto-created\n'
        'description: A GiftCommitment auto-creates a schedule.\n'
        'tags: [npc, gift-commitment, gift-commitment-schedule, automation]',
    )
    _write(
        tmp_path / "cloud-a" / "contact-points.md",
        'type: PlatformFinding\n'
        'title: Contact Point parentage\n'
        'description: ContactPointAddress ParentId is polymorphic.\n'
        'tags: [npc, contact-point-address, contact-point-phone]',
    )
    _write(
        tmp_path / "recipes" / "external-sources.md",
        'type: Reference\n'
        'title: External recipe sources\n'
        'description: Where upstream recipes exist per cloud.\n'
        'tags: [snowfakery, consumer-goods-cloud, sales-cloud]\n'
        'resource: https://example.invalid/recipes',
    )
    # reserved files must never be surfaced as knowledge docs
    _write(tmp_path / "index.md", None, "# root index")
    _write(tmp_path / "cloud-a" / "index.md", None, "# cloud-a")
    _write(tmp_path / "log.md", None, "# log")
    return tmp_path


def test_missing_dir_returns_empty(tmp_path):
    assert okf.gather_okf(objects=["Account"], okf_dir=str(tmp_path / "nope")) == []
    assert okf.list_subject_areas(str(tmp_path / "nope")) == []


def test_reserved_files_never_surfaced(tmp_path):
    _bundle(tmp_path)
    paths = [r["path"] for r in okf.gather_okf(okf_dir=str(tmp_path))]
    assert not any(p.endswith("index.md") or p.endswith("log.md") for p in paths)
    # 3 real concept docs, no reserved ones
    assert len(paths) == 3


def test_object_match_hits_title_and_tags(tmp_path):
    _bundle(tmp_path)
    hits = okf.gather_okf(objects=["GiftCommitment"], okf_dir=str(tmp_path))
    titles = [h["meta"]["title"] for h in hits]
    assert "GiftCommitmentSchedule is auto-created" in titles
    # ContactPoints doc must NOT match GiftCommitment
    assert "Contact Point parentage" not in titles


def test_object_match_normalizes_hyphens_and_case(tmp_path):
    _bundle(tmp_path)
    # "ContactPointAddress" (no hyphens) must match the tag "contact-point-address"
    hits = okf.gather_okf(objects=["ContactPointAddress"], okf_dir=str(tmp_path))
    assert [h["meta"]["title"] for h in hits] == ["Contact Point parentage"]


def test_no_match_returns_empty(tmp_path):
    _bundle(tmp_path)
    assert okf.gather_okf(objects=["Widget"], okf_dir=str(tmp_path)) == []


def test_subject_area_lists_all_in_area(tmp_path):
    _bundle(tmp_path)
    hits = okf.gather_okf(subject_area="cloud-a", okf_dir=str(tmp_path))
    assert {h["meta"]["title"] for h in hits} == {
        "GiftCommitmentSchedule is auto-created", "Contact Point parentage",
    }
    # every hit really is in that area
    assert all(h["subject_area"] == "cloud-a" for h in hits)


def test_subject_area_plus_objects_intersect(tmp_path):
    _bundle(tmp_path)
    hits = okf.gather_okf(
        objects=["GiftCommitment"], subject_area="cloud-a", okf_dir=str(tmp_path))
    assert [h["meta"]["title"] for h in hits] == [
        "GiftCommitmentSchedule is auto-created"]


def test_no_filters_returns_full_catalog(tmp_path):
    _bundle(tmp_path)
    assert len(okf.gather_okf(okf_dir=str(tmp_path))) == 3


def test_cloud_tag_matches_via_objects(tmp_path):
    _bundle(tmp_path)
    # a cloud name passed as an "object" term matches the Reference doc's tags
    hits = okf.gather_okf(objects=["consumer-goods-cloud"], okf_dir=str(tmp_path))
    assert [h["meta"]["title"] for h in hits] == ["External recipe sources"]


def test_list_subject_areas(tmp_path):
    _bundle(tmp_path)
    assert okf.list_subject_areas(str(tmp_path)) == ["cloud-a", "recipes"]
