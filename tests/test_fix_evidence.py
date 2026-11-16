"""Tests for the fix executor (BUILD 2) and evidence pack (BUILD 3)."""

import hashlib
import json
from pathlib import Path

import pytest

from qcsdoctor.evidence import build_evidence_pack
from qcsdoctor.fix import (
    apply_fix,
    describe,
    plan_output_names_fix,
    plan_tmpdir_fix,
    sha256_file,
    sha256_text,
)


def test_sha256_helpers(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"abc")
    assert sha256_file(path) == hashlib.sha256(b"abc").hexdigest()
    assert sha256_text("abc") == hashlib.sha256(b"abc").hexdigest()


def test_apply_verifies_hash_and_leaves_original(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"output_names": ["a"], "keep": 1}), encoding="utf-8")
    plan = plan_output_names_fix(params, tmp_path / "work")
    applied = apply_fix(plan)
    assert applied["applied"] is True
    assert applied["sha256_actual"] == plan["sha256_after"]
    assert json.loads(params.read_text())["output_names"] == ["a"]


def test_apply_refuses_tampered_plan(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"output_names": ["a"]}), encoding="utf-8")
    plan = plan_output_names_fix(params, tmp_path / "work")
    plan["sha256_after"] = "0" * 64  # tampered expectation
    with pytest.raises(ValueError, match="hash mismatch"):
        apply_fix(plan)
    assert not (tmp_path / "work" / "compile-params.fixed.json").exists()


def test_tmpdir_fix_snippet(tmp_path):
    plan = plan_tmpdir_fix(Path("/data/big-tmp"), tmp_path / "work")
    assert plan["kind"] == "patch"
    assert "export TMPDIR=/data/big-tmp" in plan["diff"]
    applied = apply_fix(plan)
    assert applied["applied"] is True
    assert "export TMPDIR=/data/big-tmp" in (tmp_path / "work" / "tmpdir.env").read_text()


def test_describe_dry_run(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"output_names": ["a"]}), encoding="utf-8")
    plan = plan_output_names_fix(params, tmp_path / "work")
    text = describe(plan)
    assert "dry-run" in text
    assert "sha256 before" in text


def test_evidence_pack_scaffold(tmp_path):
    manifest = build_evidence_pack(
        "check8", "Unquantized tensor in vendor AOT asset",
        ["layers.2/mlp/down_proj/Conv_bias is FP32 at link time"],
        ["INTERNVL35 failure path hurdle 4"],
        tmp_path / "pack")
    assert manifest["status"] == "REPORT-ONLY"
    assert manifest["check_id"] == "check8"
    assert (tmp_path / "pack" / "manifest.json").is_file()
    assert (tmp_path / "pack" / "EVIDENCE_PACK.md").is_file()
    assert "REPORT-ONLY" in (tmp_path / "pack" / "EVIDENCE_PACK.md").read_text()
