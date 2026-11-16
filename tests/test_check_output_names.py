"""Tests for check 1 / A1: AIMET ONNX + --output_names (#366)."""

import json

import pytest

from qcsdoctor.checks.output_names import (
    check_output_names,
    check_output_names_file,
    is_aimet_onnx,
)
from qcsdoctor.fix import apply_fix, plan_output_names_fix
from qcsdoctor.onnx_parse import parse_onnx


def _varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field(number, payload):
    return _varint((number << 3) | 2) + _varint(len(payload)) + payload


def _var_field(number, value):
    return _varint(number << 3) + _varint(value)


def _text_field(number, text):
    return _field(number, text.encode("utf-8"))


def build_onnx(producer="aimet", ops=("QuantizeLinear", "DequantizeLinear", "MatMul")):
    """Minimal ModelProto bytes parseable by qcsdoctor.onnx_parse."""
    graph = _text_field(2, "test_graph")
    for op in ops:
        graph += _field(1, _text_field(4, op))
    opset = _text_field(1, "") + _var_field(2, 17)
    model = _text_field(2, producer)
    model += _field(8, opset)
    model += _field(7, graph)
    return model


def test_is_aimet_onnx_by_ops():
    info = parse_onnx(build_onnx(producer="pytorch"))
    assert is_aimet_onnx(info) is True  # QuantizeLinear present
    assert info["producer"] == "pytorch"


def test_is_aimet_onnx_by_producer():
    info = parse_onnx(build_onnx(producer="AIMET 2.37", ops=("MatMul",)))
    assert is_aimet_onnx(info) is True


def test_is_not_aimet_onnx():
    info = parse_onnx(build_onnx(producer="pytorch", ops=("MatMul", "Add")))
    assert is_aimet_onnx(info) is False


def test_fail_aimet_with_output_names():
    info = parse_onnx(build_onnx())
    result = check_output_names({"output_names": ["logits"], "input_shapes": {}},
                                onnx_info=info)
    assert result["status"] == "fail"
    assert result["fixable"] is True
    assert "#366" in result["detail"]
    assert "jp0x1z32p" in result["evidence"] or "#366" in result["evidence"]


def test_pass_aimet_without_output_names():
    info = parse_onnx(build_onnx())
    result = check_output_names({"input_shapes": {}}, onnx_info=info)
    assert result["status"] == "pass"


def test_pass_non_aimet_with_output_names():
    info = parse_onnx(build_onnx(producer="pytorch", ops=("MatMul",)))
    result = check_output_names({"output_names": ["logits"]}, onnx_info=info)
    assert result["status"] == "pass"


def test_warn_when_aimet_unknown():
    result = check_output_names({"output_names": ["logits"]})
    assert result["status"] == "warn"
    assert result["fixable"] is False


def test_skip_without_params():
    assert check_output_names(None)["status"] == "skip"


def test_version_note_old_and_new():
    info = parse_onnx(build_onnx())
    old = check_output_names({"input_shapes": {}}, onnx_info=info,
                             qai_hub_models_version="0.66.0")
    assert "0.67.0" in old["detail"]
    new = check_output_names({"input_shapes": {}}, onnx_info=info,
                             qai_hub_models_version="0.67.0")
    assert "0.67.0" in new["detail"]
    assert new["status"] == "pass"


def test_file_level_fail_and_fix(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"output_names": ["a"], "foo": 1}), encoding="utf-8")
    onnx = tmp_path / "model.onnx"
    onnx.write_bytes(build_onnx())
    result = check_output_names_file(params, onnx_path=onnx)
    assert result["status"] == "fail"
    plan = plan_output_names_fix(params, tmp_path / "work")
    assert "output_names" in plan["diff"]
    assert plan["sha256_before"] != plan["sha256_after"]
    applied = apply_fix(plan)
    assert applied["applied"] is True
    fixed = json.loads((tmp_path / "work" / "compile-params.fixed.json").read_text())
    assert "output_names" not in fixed and fixed["foo"] == 1
    # Original untouched.
    assert json.loads(params.read_text())["output_names"] == ["a"]


def test_file_level_missing_params(tmp_path):
    result = check_output_names_file(tmp_path / "nope.json")
    assert result["status"] == "skip"
