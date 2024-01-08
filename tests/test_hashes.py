"""Tests for content-hash duplicate detection."""

from phototidy.hashes import choose_keepers, file_digest, find_duplicates, group_by_digest


def test_digest_is_stable_for_the_same_bytes(tmp_path):
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"same payload")
    second.write_bytes(b"same payload")
    assert file_digest(str(first)) == file_digest(str(second))


def test_digest_differs_for_different_bytes(tmp_path):
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    assert file_digest(str(first)) != file_digest(str(second))


def test_digest_handles_several_blocks(tmp_path):
    path = tmp_path / "big.bin"
    path.write_bytes(b"x" * 5000)
    assert len(file_digest(str(path), block_size=64)) == 64


def test_group_by_digest_drops_unique_files(tmp_path):
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    alone = tmp_path / "c.bin"
    first.write_bytes(b"dup")
    second.write_bytes(b"dup")
    alone.write_bytes(b"unique")
    groups = group_by_digest([str(first), str(second), str(alone)])
    assert len(groups) == 1
    assert sorted(list(groups.values())[0]) == sorted([str(first), str(second)])


def test_group_by_digest_survives_a_missing_file(tmp_path):
    present = tmp_path / "a.bin"
    present.write_bytes(b"dup")
    groups = group_by_digest([str(present), str(tmp_path / "gone.bin")])
    assert groups == {}


def test_choose_keepers_prefers_the_earliest_capture(tmp_path):
    early = tmp_path / "early.jpg"
    late = tmp_path / "late.jpg"
    taken = {str(early): 1, str(late): 2}
    keep, drop = choose_keepers([str(late), str(early)], taken)
    assert keep == str(early)
    assert drop == [str(late)]


def test_choose_keepers_prefers_the_shallower_path_on_a_tie(tmp_path):
    shallow = tmp_path / "x.jpg"
    deep = tmp_path / "deep__sep__y.jpg"
    keep, drop = choose_keepers([str(deep), str(shallow)], {})
    assert keep == str(shallow)


def test_choose_keepers_breaks_remaining_ties_alphabetically(tmp_path):
    first = tmp_path / "a.jpg"
    second = tmp_path / "b.jpg"
    keep, drop = choose_keepers([str(second), str(first)], {})
    assert keep == str(first)


def test_find_duplicates_reports_the_dropped_copy(make_jpeg, tmp_path):
    first = make_jpeg("a.jpg", datetime_original="2020:01:01 00:00:00")
    second = tmp_path / "copy.jpg"
    second.write_bytes(open(first, "rb").read())
    pairs = find_duplicates([first, str(second)])
    assert pairs == [(first, str(second))]


def test_find_duplicates_is_empty_without_copies(make_jpeg):
    paths = [
        make_jpeg("a.jpg", datetime_original="2020:01:01 00:00:00"),
        make_jpeg("b.jpg", datetime_original="2020:02:02 00:00:00"),
    ]
    assert find_duplicates(paths) == []


def test_find_duplicates_collapses_three_copies_once(make_jpeg, tmp_path):
    first = make_jpeg("a.jpg", datetime_original="2020:01:01 00:00:00")
    payload = open(first, "rb").read()
    others = []
    for name in ("b.jpg", "c.jpg"):
        path = tmp_path / name
        path.write_bytes(payload)
        others.append(str(path))
    pairs = find_duplicates([first] + others)
    assert len(pairs) == 2
    assert {pair[0] for pair in pairs} == {first}
