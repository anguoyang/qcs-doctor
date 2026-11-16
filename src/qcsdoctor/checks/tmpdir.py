"""Check 6: /tmp fills up (unpack temp files).

Evidence: qualcomm-recipe/QWEN3_0_6B_FAILURE_PATH_2026-11-13.md
(pre-death history: unpack temp files blew the 512 MB /tmp while the
main disk had 81 GB) and
qualcomm-recipe/INTERNVL35_2B_FAILURE_PATH_2026-11-16.md (a TMPDIR
pointing at a nonexistent directory fell back to the 512 MB /tmp and
died; redirecting TMPDIR to qualcomm-recipe/work/tmp fixed it).

The A-level fix is to check TMPDIR and free space before starting,
and redirect TMPDIR at a directory with room. This check never writes.
"""

import os
import shutil
from pathlib import Path
from typing import Callable, List, Optional

from . import result, skipped

CHECK_ID = "tmpdir"
EVIDENCE = ("qualcomm-recipe/QWEN3_0_6B_FAILURE_PATH_2026-11-13.md "
            "(512 MB /tmp blown, 81 GB free on main disk); "
            "qualcomm-recipe/INTERNVL35_2B_FAILURE_PATH_2026-11-16.md "
            "(TMPDIR fell back to 512 MB /tmp)")

# Candidates, in order, for a redirected TMPDIR. /tmp itself is excluded:
# it is the directory that blew up.
CANDIDATES = ("~/tmp", ".qcsdoctor-tmp", "/var/tmp")


def _free_bytes(path: Path, disk_usage: Callable) -> Optional[int]:
    try:
        return disk_usage(str(path)).free
    except OSError:
        return None


def pick_tmpdir(need_bytes: int, disk_usage: Callable = shutil.disk_usage,
                cwd: Optional[Path] = None) -> Optional[Path]:
    """First candidate directory with at least need_bytes free, else None."""
    base = cwd or Path.cwd()
    for raw in CANDIDATES:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        free = _free_bytes(candidate, disk_usage)
        if free is not None and free >= need_bytes:
            return candidate
    return None


def check_tmpdir(tmpdir: Optional[str] = None, need_bytes: int = 2 * 1024 ** 3,
                 disk_usage: Callable = shutil.disk_usage) -> dict:
    """Check the temp directory has room for the planned work.

    tmpdir: directory to check (default $TMPDIR, else /tmp).
    need_bytes: bytes the pipeline is expected to need in temp space.
    disk_usage: injectable for tests; defaults to shutil.disk_usage.
    """
    title = "Temp directory space (/tmp blow-up)"
    directory = Path(tmpdir or os.environ.get("TMPDIR") or "/tmp")
    value = {"tmpdir": str(directory), "need_bytes": need_bytes,
             "free_bytes": None}
    if not directory.is_dir():
        alternative = pick_tmpdir(need_bytes, disk_usage)
        return result(CHECK_ID, title, "fail", value,
                      "Temp directory does not exist: %s" % directory,
                      ("Set TMPDIR to %s." % alternative) if alternative
                      else "Create a temp directory on a disk with room.",
                      fixable=alternative is not None, evidence=EVIDENCE)
    free = _free_bytes(directory, disk_usage)
    if free is None:
        return skipped(CHECK_ID, title,
                       "Cannot read free space for %s." % directory,
                       "Check the directory exists and is readable.",
                       evidence=EVIDENCE)
    value["free_bytes"] = free
    if free >= need_bytes:
        detail = ("Temp directory %s has %d bytes free for %d needed."
                  % (directory, free, need_bytes))
        if str(directory) == "/tmp":
            detail += (" Note: /tmp is the directory that blew up in the "
                       "failure path; it passes only because it has room "
                       "right now.")
        return result(CHECK_ID, title, "pass", value, detail,
                      evidence=EVIDENCE)
    alternative = pick_tmpdir(need_bytes, disk_usage)
    return result(CHECK_ID, title, "fail", value,
                  "Temp directory %s has %d bytes free, need %d."
                  % (directory, free, need_bytes),
                  ("Redirect TMPDIR to %s." % alternative) if alternative
                  else "Free disk space; no candidate directory has room.",
                  fixable=alternative is not None, evidence=EVIDENCE)
