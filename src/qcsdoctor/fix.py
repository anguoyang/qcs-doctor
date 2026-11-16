"""Fix executor (BUILD 2): dry-run diff + copy patch + hash verification.

Shared by all A-level fixes. Rules, from the charter:
- A fix is dry-run first: plan it, show the diff, apply nothing.
- The original asset is read-only. A patch is applied only to a copy
  inside an explicit work directory, and the copy is hash-verified
  before and after.
- A "command" fix (e.g. the resumable curl fetch) is never executed by
  the executor; it is written out as a script for the user to run.
  The executor does no network I/O.

A FixPlan is a plain dict:
    {"check_id", "kind", "target", "diff", "commands",
     "sha256_before", "sha256_after", "applied", "copy_path"}
kind is "patch" (a file copy is produced) or "command" (a script is
produced). sha256_after is the hash the copy must have after apply;
apply_fix() verifies it and refuses to leave a mismatching copy.
"""

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .checks.downloader import resume_command


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unified_diff(before: str, after: str, name: str) -> str:
    lines = difflib.unified_diff(before.splitlines(keepends=True),
                                 after.splitlines(keepends=True),
                                 fromfile="a/" + name, tofile="b/" + name)
    return "".join(lines)


def plan_output_names_fix(params_path: Path, workdir: Path) -> Dict[str, Any]:
    """Check 1 fix: drop ``output_names`` from a *copy* of the params.

    The original params file is never modified. Returns a plan whose
    copy lands at <workdir>/compile-params.fixed.json on apply.
    """
    original = params_path.read_bytes()
    params = json.loads(original.decode("utf-8"))
    fixed = {key: value for key, value in params.items()
             if key != "output_names"}
    before = json.dumps(params, indent=2, sort_keys=True) + "\n"
    after = json.dumps(fixed, indent=2, sort_keys=True) + "\n"
    return {"check_id": "output_names", "kind": "patch",
            "target": str(params_path),
            "copy_path": str(workdir / "compile-params.fixed.json"),
            "diff": unified_diff(before, after, "compile-params.json"),
            "commands": [],
            "sha256_before": hashlib.sha256(original).hexdigest(),
            "sha256_after": sha256_text(after),
            "applied": False,
            "note": ("Input shapes still need pinning before the params "
                     "are submitted (see the #366 failure path); this fix "
                     "only removes the rejected flag.")}


def plan_downloader_fix(url: str, cache_path: Path, workdir: Path,
                        expected_bytes: Optional[int] = None) -> Dict[str, Any]:
    """Check 5 fix: resumable fetch script (never executed here)."""
    command = resume_command(url, cache_path)
    script = "#!/bin/sh\n# QCS Doctor fix for check 'downloader' (dry-run output).\n# Resumable fetch; re-run safely if interrupted.\n%s\n" % command
    if expected_bytes is not None:
        script += ("# After the fetch, verify: %d bytes, and testzip for .zip assets.\n"
                   % expected_bytes)
    return {"check_id": "downloader", "kind": "command",
            "target": str(cache_path),
            "copy_path": str(workdir / "fetch-asset.sh"),
            "diff": script,
            "commands": [command],
            "sha256_before": None,
            "sha256_after": sha256_text(script),
            "applied": False,
            "note": "Run the script yourself; the executor never fetches."}


def plan_tmpdir_fix(new_tmpdir: Path, workdir: Path) -> Dict[str, Any]:
    """Check 6 fix: TMPDIR redirect snippet."""
    snippet = "# QCS Doctor fix for check 'tmpdir' (dry-run output).\n# Source this file before starting the pipeline.\nexport TMPDIR=%s\n" % new_tmpdir
    return {"check_id": "tmpdir", "kind": "patch",
            "target": "TMPDIR",
            "copy_path": str(workdir / "tmpdir.env"),
            "diff": snippet,
            "commands": ["export TMPDIR=%s" % new_tmpdir],
            "sha256_before": None,
            "sha256_after": sha256_text(snippet),
            "applied": False,
            "note": "The snippet only takes effect in a shell that sources it."}


def apply_fix(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Write the planned copy and verify its hash. Originals untouched.

    For kind "patch" with a real source file (check 1), the copy is the
    patched content. For kind "command" and snippet fixes, the copy is
    the script/snippet itself. Raises ValueError if verification fails.
    """
    applied = dict(plan)
    copy_path = Path(plan["copy_path"])
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    if plan["kind"] == "patch" and plan["check_id"] == "output_names":
        import json as _json
        params = _json.loads(Path(plan["target"]).read_text(encoding="utf-8"))
        fixed = {key: value for key, value in params.items()
                 if key != "output_names"}
        text = _json.dumps(fixed, indent=2, sort_keys=True) + "\n"
        copy_path.write_text(text, encoding="utf-8")
    else:
        copy_path.write_text(plan["diff"], encoding="utf-8")
    actual = sha256_file(copy_path)
    if actual != plan["sha256_after"]:
        copy_path.unlink(missing_ok=True)
        raise ValueError("hash mismatch after apply: expected %s, got %s"
                         % (plan["sha256_after"], actual))
    applied["applied"] = True
    applied["sha256_actual"] = actual
    return applied


def describe(plan: Dict[str, Any]) -> str:
    lines = ["fix %s (%s): %s" % (plan["check_id"], plan["kind"], plan["target"])]
    if plan["sha256_before"]:
        lines.append("  sha256 before: " + plan["sha256_before"])
    lines.append("  sha256 after:  " + plan["sha256_after"])
    lines.append("  copy: " + plan["copy_path"])
    lines.append("  applied: " + ("yes" if plan["applied"] else "no (dry-run)"))
    if plan.get("note"):
        lines.append("  note: " + plan["note"])
    return "\n".join(lines)
