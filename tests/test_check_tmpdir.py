"""Tests for check 6: /tmp fills up."""

import shutil

from qcsdoctor.checks.tmpdir import check_tmpdir, pick_tmpdir


class _Usage:
    def __init__(self, free):
        self.free = free


def _fake_usage(free_by_path):
    def usage(path):
        return _Usage(free_by_path.get(path, 0))
    return usage


def test_pass_enough_space(tmp_path):
    result = check_tmpdir(str(tmp_path), need_bytes=1024)
    assert result["status"] == "pass"
    assert result["value"]["free_bytes"] >= 1024


def test_fail_not_enough_space(tmp_path):
    # need_bytes larger than any real disk: deterministic fail.
    result = check_tmpdir(str(tmp_path), need_bytes=10 ** 18)
    assert result["status"] == "fail"
    assert result["fixable"] is False  # no candidate has 10**18 free
    assert "need" in result["detail"]


def test_fail_missing_dir(tmp_path):
    missing = tmp_path / "no-such-dir"
    result = check_tmpdir(str(missing), need_bytes=1024)
    assert result["status"] == "fail"


def test_pick_tmpdir_prefers_first_with_room(tmp_path, monkeypatch):
    home_tmp = tmp_path / "tmp"
    home_tmp.mkdir()
    usage = _fake_usage({str(home_tmp): 10 * 1024 ** 3,
                         str(tmp_path / ".qcsdoctor-tmp"): 0,
                         "/var/tmp": 0})
    monkeypatch.setenv("HOME", str(tmp_path))
    picked = pick_tmpdir(2 * 1024 ** 3, disk_usage=usage, cwd=tmp_path)
    assert picked == home_tmp


def test_pick_tmpdir_none_when_nowhere_has_room(tmp_path):
    usage = _fake_usage({})
    assert pick_tmpdir(2 * 1024 ** 3, disk_usage=usage, cwd=tmp_path) is None


def test_fixable_fail_with_alternative(tmp_path, monkeypatch):
    # tmpdir itself has no room, but ~/tmp does: fixable.
    small = tmp_path / "small"
    small.mkdir()
    home_tmp = tmp_path / "tmp"
    home_tmp.mkdir()
    usage = _fake_usage({str(small): 100,
                         str(home_tmp): 10 * 1024 ** 3,
                         str(tmp_path / ".qcsdoctor-tmp"): 0,
                         "/var/tmp": 0})
    monkeypatch.setenv("HOME", str(tmp_path))
    result = check_tmpdir(str(small), need_bytes=2 * 1024 ** 3,
                          disk_usage=usage)
    assert result["status"] == "fail"
    assert result["fixable"] is True
    assert str(home_tmp) in (result["hint"] or "")
