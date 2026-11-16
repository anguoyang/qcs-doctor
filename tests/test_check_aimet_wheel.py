"""Tests for check A2: aimet-onnx wheel missing for this platform."""

from qcsdoctor.checks.aimet_wheel import check_aimet_wheel, python_tag


def test_fail_aarch64_cp312():
    result = check_aimet_wheel(machine="aarch64", tag="cp312")
    assert result["status"] == "fail"
    assert result["fixable"] is False  # pre-check only; no auto-fix
    assert "no wheel" in result["detail"]
    assert "x86_64" in (result["hint"] or "")


def test_pass_x86_64():
    result = check_aimet_wheel(machine="x86_64", tag="cp312")
    assert result["status"] == "pass"


def test_skip_unknown_combo():
    # aarch64/cp313 has no recorded data: unknown, never guessed.
    result = check_aimet_wheel(machine="aarch64", tag="cp313")
    assert result["status"] == "skip"


def test_defaults_describe_this_host():
    result = check_aimet_wheel()
    assert result["value"]["machine"]
    assert result["value"]["python_tag"] == python_tag()
    assert result["status"] in ("pass", "fail", "skip")
