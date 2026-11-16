"""Command-line entry point.

Two subcommands:
  check  — run the implemented checks against the supplied inputs.
           A check with no inputs is reported as "skip", never guessed.
  fix    — plan (dry-run by default) or --apply an A-level fix for one
           check. Fixes only ever write copies inside --workdir; the
           executor never fetches from the network and never modifies
           the original asset.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .checks.aimet_wheel import check_aimet_wheel
from .checks.downloader import check_downloader
from .checks.output_names import check_output_names_file
from .checks.tmpdir import check_tmpdir, pick_tmpdir
from .fix import (apply_fix, describe, plan_downloader_fix,
                  plan_output_names_fix, plan_tmpdir_fix)
from .report import build_report, terminal_report, write_reports


def _add_check_args(parser) -> None:
    parser.add_argument("--onnx", metavar="PATH", help="ONNX model for check 1")
    parser.add_argument("--compile-params", metavar="PATH", help="Compile params JSON for check 1")
    parser.add_argument("--aimet", action="store_true", help="Assert the ONNX is AIMET-quantized (check 1)")
    parser.add_argument("--qai-hub-models-version", metavar="VER", help="Installed qai_hub_models version (check 1)")
    parser.add_argument("--asset-url", metavar="URL", help="Asset URL for check 5")
    parser.add_argument("--expected-bytes", type=int, metavar="N", help="Exact asset size in bytes (check 5)")
    parser.add_argument("--cache", metavar="PATH", help="Asset cache path (check 5)")
    parser.add_argument("--tmpdir", metavar="DIR", help="Temp directory to check (check 6)")
    parser.add_argument("--need-bytes", type=int, default=2 * 1024 ** 3, metavar="N",
                        help="Temp bytes the pipeline needs (check 6, default 2 GiB)")
    parser.add_argument("--machine", metavar="M", help="Platform machine for check A2 (default: this host)")
    parser.add_argument("--python-tag", metavar="TAG", help="CPython tag like cp312 for check A2 (default: this interpreter)")
    parser.add_argument("--aimet-onnx-version", metavar="VER", default="2.37.0",
                        help="aimet-onnx version to pre-check (check A2, default 2.37.0)")
    parser.add_argument("--json", metavar="PATH", help="Write schema 1 JSON report")
    parser.add_argument("--html", metavar="PATH", help="Write a standalone HTML report")
    parser.add_argument("--quiet", action="store_true", help="Print only verdict and report paths")


def _run_checks(args) -> list:
    checks = []
    from .checks.output_names import check_output_names
    if args.compile_params:
        checks.append(check_output_names_file(
            Path(args.compile_params), onnx_path=Path(args.onnx) if args.onnx else None,
            aimet=args.aimet or None,
            qai_hub_models_version=args.qai_hub_models_version))
    else:
        checks.append(check_output_names(None))
    if args.asset_url and args.cache:
        checks.append(check_downloader(args.asset_url, args.expected_bytes, Path(args.cache)))
    else:
        from .checks import skipped
        from .checks.downloader import CHECK_ID, EVIDENCE
        checks.append(skipped(CHECK_ID, "Downloader stalls with no timeout",
                              "No --asset-url/--cache supplied; nothing to preflight.",
                              "Pass --asset-url, --expected-bytes and --cache.",
                              evidence=EVIDENCE))
    checks.append(check_tmpdir(tmpdir=args.tmpdir, need_bytes=args.need_bytes))
    checks.append(check_aimet_wheel(machine=args.machine, tag=args.python_tag,
                                    version=args.aimet_onnx_version))
    return checks


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="qcsdoctor",
                                     description="Diagnose and fix Qualcomm AI Hub deployment failures")
    parser.add_argument("--version", action="version", version="qcsdoctor " + __version__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Run the implemented checks")
    _add_check_args(check)
    fix = commands.add_parser("fix", help="Plan or apply one A-level fix (dry-run by default)")
    fix.add_argument("--check", required=True, choices=["output_names", "downloader", "tmpdir"],
                     help="Which check's fix to plan")
    fix.add_argument("--apply", action="store_true", help="Write the fix copy (default: dry-run, print diff only)")
    fix.add_argument("--workdir", default="qcsdoctor-fix", metavar="DIR",
                     help="Directory for fix copies (default qcsdoctor-fix)")
    _add_check_args(fix)
    args, extra = parser.parse_known_args(argv)
    if extra:
        parser.error("unrecognized arguments: " + " ".join(extra))

    if args.command == "fix":
        return _run_fix(args)

    checks = _run_checks(args)
    report = build_report(checks)
    try:
        write_reports(report, args.json, args.html)
    except (OSError, ValueError) as error:
        print("qcsdoctor: cannot write report: " + str(error), file=sys.stderr)
        return 1
    paths = [p for p in (args.json, args.html) if p]
    if args.quiet:
        from .report import verdict_line
        print(verdict_line(report, paths))
    else:
        print(terminal_report(report, paths))
    return 0


def _run_fix(args) -> int:
    workdir = Path(args.workdir)
    if args.check == "output_names":
        if not args.compile_params:
            print("qcsdoctor: fix output_names needs --compile-params", file=sys.stderr)
            return 2
        plan = plan_output_names_fix(Path(args.compile_params), workdir)
    elif args.check == "downloader":
        if not (args.asset_url and args.cache):
            print("qcsdoctor: fix downloader needs --asset-url and --cache", file=sys.stderr)
            return 2
        plan = plan_downloader_fix(args.asset_url, Path(args.cache), workdir,
                                   expected_bytes=args.expected_bytes)
    else:  # tmpdir
        alternative = pick_tmpdir(args.need_bytes)
        if alternative is None:
            print("qcsdoctor: no candidate directory has room for %d bytes"
                  % args.need_bytes, file=sys.stderr)
            return 1
        plan = plan_tmpdir_fix(alternative, workdir)
    print(describe(plan))
    print("--- diff ---")
    print(plan["diff"], end="" if plan["diff"].endswith("\n") else "\n")
    if not args.apply:
        print("(dry-run: nothing written; pass --apply to write the copy)")
        return 0
    try:
        applied = apply_fix(plan)
    except ValueError as error:
        print("qcsdoctor: fix failed verification: " + str(error), file=sys.stderr)
        return 1
    print("applied and hash-verified: " + applied["copy_path"])
    return 0
