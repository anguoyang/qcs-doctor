"""Tests for check 5: downloader stalls with no timeout."""

import io
import zipfile

from qcsdoctor.checks.downloader import check_downloader, resume_command
from qcsdoctor.fix import apply_fix, plan_downloader_fix

URL = "https://example.com/assets/fp16mix.zip"
FAKE_CURL = "/usr/bin/curl"


def _make_zip(path, corrupt=False):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.txt", b"hello")
    if corrupt:
        # Flip a byte inside the stored file data (offset 30: local header
        # is 30 bytes for a 5-char name), so testzip's CRC check trips.
        data = bytearray(path.read_bytes())
        data[30] ^= 0xFF
        path.write_bytes(bytes(data))


def test_pass_complete_zip_cache(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    _make_zip(cache)
    result = check_downloader(URL, cache.stat().st_size, cache, curl_path=FAKE_CURL)
    assert result["status"] == "pass"


def test_pass_complete_non_zip_cache(tmp_path):
    cache = tmp_path / "model.bin"
    cache.write_bytes(b"x" * 100)
    result = check_downloader(URL, 100, cache, curl_path=FAKE_CURL)
    assert result["status"] == "pass"


def test_fail_missing_cache_fixable(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    result = check_downloader(URL, 9388733639, cache, curl_path=FAKE_CURL)
    assert result["status"] == "fail"
    assert result["fixable"] is True
    assert "curl -C -" in result["hint"]
    assert resume_command(URL, cache) == "curl -C - -o %s %s" % (cache, URL)


def test_fail_missing_cache_no_curl(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    result = check_downloader(URL, 9388733639, cache, curl_path=False)
    assert result["status"] == "fail"
    assert result["fixable"] is False


def test_fail_partial_cache_resume(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    cache.write_bytes(b"x" * 100)
    result = check_downloader(URL, 1000, cache, curl_path=FAKE_CURL)
    assert result["status"] == "fail"
    assert "Partial cache (100 of 1000 bytes" in result["detail"]
    assert result["fixable"] is True
    assert "curl -C -" in result["hint"]


def test_fail_partial_cache_no_curl(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    cache.write_bytes(b"x" * 10)
    result = check_downloader(URL, 100, cache, curl_path=False)
    assert result["status"] == "fail"
    assert result["fixable"] is False


def test_fail_oversize_cache(tmp_path):
    cache = tmp_path / "model.bin"
    cache.write_bytes(b"x" * 200)
    result = check_downloader(URL, 100, cache, curl_path=FAKE_CURL)
    assert result["status"] == "fail"
    assert "larger than expected" in result["detail"]


def test_fail_corrupt_zip(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    _make_zip(cache, corrupt=True)
    result = check_downloader(URL, cache.stat().st_size, cache, curl_path=FAKE_CURL)
    assert result["status"] == "fail"
    assert "corrupt" in result["detail"]


def test_warn_unknown_expected_size(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    result = check_downloader(URL, None, cache, curl_path=FAKE_CURL)
    assert result["status"] == "warn"


def test_fix_plan_writes_script(tmp_path):
    cache = tmp_path / "fp16mix.zip"
    plan = plan_downloader_fix(URL, cache, tmp_path / "work", expected_bytes=9388733639)
    assert plan["kind"] == "command"
    assert "curl -C -" in plan["diff"]
    applied = apply_fix(plan)
    script = tmp_path / "work" / "fetch-asset.sh"
    assert script.is_file()
    assert "curl -C -" in script.read_text()
    assert applied["applied"] is True
