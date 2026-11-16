"""Check 5: official downloader stalls with no timeout.

Evidence: qualcomm-recipe/QWEN3_0_6B_FAILURE_PATH_2026-11-13.md
(pre-death history: official downloader 15 minutes, 0 bytes) and
qualcomm-recipe/INTERNVL35_2B_FAILURE_PATH_2026-11-16.md hurdle 3
(9,388,733,639-byte fp16mix.zip stalled at 6,611,808,256 bytes, ~70%,
tqdm frozen, process alive but connection dead).

The A-level fix is to never trust the bundled downloader with a large
asset: pre-fetch with ``curl -C -`` (resumable), land the partial file
in its final cache position, verify byte count and (for zips) testzip,
and only then start the pipeline. This check is a preflight for one
planned download: it never touches the network itself.
"""

import shutil
import zipfile
from pathlib import Path
from typing import Optional

from . import result, skipped

CHECK_ID = "downloader"
EVIDENCE = ("qualcomm-recipe/QWEN3_0_6B_FAILURE_PATH_2026-11-13.md "
            "(15 min, 0 bytes); "
            "qualcomm-recipe/INTERNVL35_2B_FAILURE_PATH_2026-11-16.md "
            "hurdle 3 (9,388,733,639 bytes stalled at 6,611,808,256)")


def _zip_ok(path: Path) -> Optional[str]:
    """Return the first corrupt member name, or None if the zip is sound."""
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip()
    except zipfile.BadZipFile as error:
        return "bad zip: %s" % error


def check_downloader(url: str, expected_bytes: Optional[int],
                     cache_path: Path, curl_path: Optional[str] = None) -> dict:
    """Preflight one planned asset download.

    url: asset URL (recorded, never fetched by this check).
    expected_bytes: exact size from Content-Length, or None if unknown.
    cache_path: where the finished asset must land.
    curl_path: path to curl, or None to auto-detect (tests pass False
        explicitly to simulate a missing curl).
    """
    title = "Downloader stalls with no timeout"
    if curl_path is None:
        curl_path = shutil.which("curl")
    cache = Path(cache_path)
    value = {"url": url, "expected_bytes": expected_bytes,
             "cache": str(cache),
             "cache_bytes": cache.stat().st_size if cache.is_file() else None,
             "curl": curl_path}
    if expected_bytes is None:
        return result(CHECK_ID, title, "warn", value,
                      "Expected asset size unknown; completeness cannot be "
                      "verified after download.",
                      "Record Content-Length as --expected-bytes before "
                      "downloading.",
                      fixable=False, evidence=EVIDENCE)
    if not cache.is_file():
        if not curl_path:
            return result(CHECK_ID, title, "fail", value,
                          "Asset not cached and curl is not available: the "
                          "bundled downloader is known to stall with no "
                          "timeout.",
                          "Install curl, then fetch with curl -C -.",
                          fixable=False, evidence=EVIDENCE)
        return result(CHECK_ID, title, "fail", value,
                      "Asset not cached; fetch it with a resumable "
                      "downloader before starting the pipeline.",
                      "curl -C - -o %s %s, then verify %d bytes."
                      % (cache, url, expected_bytes),
                      fixable=True, evidence=EVIDENCE)
    size = cache.stat().st_size
    if size > expected_bytes:
        return result(CHECK_ID, title, "fail", value,
                      "Cache is larger than expected (%d > %d bytes); "
                      "the file is not the asset." % (size, expected_bytes),
                      "Delete the cache and re-fetch with curl -C -.",
                      fixable=True, evidence=EVIDENCE)
    if size < expected_bytes:
        if not curl_path:
            return result(CHECK_ID, title, "fail", value,
                          "Partial cache (%d of %d bytes) and curl is not "
                          "available; the bundled downloader cannot resume."
                          % (size, expected_bytes),
                          "Install curl, then resume with curl -C -.",
                          fixable=False, evidence=EVIDENCE)
        return result(CHECK_ID, title, "fail", value,
                      "Partial cache (%d of %d bytes, %.1f%%); resume it "
                      "instead of restarting." % (size, expected_bytes,
                                                  100.0 * size / expected_bytes),
                      "curl -C - -o %s %s, then verify %d bytes."
                      % (cache, url, expected_bytes),
                      fixable=True, evidence=EVIDENCE)
    if cache.suffix.lower() == ".zip":
        bad = _zip_ok(cache)
        if bad is not None:
            return result(CHECK_ID, title, "fail", value,
                          "Cache has the expected byte count but the zip "
                          "is corrupt (%s)." % bad,
                          "Delete the cache and re-fetch with curl -C -.",
                          fixable=True, evidence=EVIDENCE)
    return result(CHECK_ID, title, "pass", value,
                  "Cache complete (%d bytes) and verified; the pipeline "
                  "can start without downloading." % expected_bytes,
                  evidence=EVIDENCE)


def resume_command(url: str, cache_path: Path) -> str:
    """The resumable fetch command this check's fix emits."""
    return "curl -C - -o %s %s" % (cache_path, url)
