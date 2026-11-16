"""Check 1 / A1: AIMET ONNX + ``--output_names`` (issue #366).

Evidence: qualcomm-recipe/QWEN3_0_6B_FAILURE_PATH_2026-11-13.md.
The Hub compiler rejects ``--output_names`` for AIMET-quantized ONNX
(``--output_names is not supported for AIMET ONNX models``). Two Hub jobs
died the same way on two devices (jp0x1z32p / jp2z70o4p). The manual
workaround — drop the flag from the compile params and pin the input
shapes — then compiled all four graphs and landed the first public
QCS6490 GenAI numbers (prefill 1,555 tok/s, decode 24.6 tok/s).
Maintainer confirmed #366; fixed in qai_hub_models 0.67.0.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from ..onnx_parse import OnnxParseError, parse_onnx
from . import result, skipped

CHECK_ID = "output_names"
EVIDENCE = ("qualcomm-recipe/QWEN3_0_6B_FAILURE_PATH_2026-11-13.md "
            "(issue #366, jobs jp0x1z32p / jp2z70o4p)")
FIXED_IN_VERSION = (0, 67, 0)


def is_aimet_onnx(info: Dict[str, Any]) -> bool:
    """Heuristic AIMET detection from the parsed ONNX structure.

    AIMET-quantized exports carry QuantizeLinear/DequantizeLinear nodes
    (and usually an AIMET producer string). Weight values are never read.
    """
    producer = (info.get("producer") or "").lower()
    if "aimet" in producer:
        return True
    ops = info.get("op_hist") or {}
    return bool(ops.get("QuantizeLinear") or ops.get("DequantizeLinear"))


def load_onnx(path: Path) -> Dict[str, Any]:
    return parse_onnx(path.read_bytes())


def _version_tuple(text: str) -> Optional[tuple]:
    try:
        parts = [int(p) for p in text.strip().split(".")[:3]]
    except ValueError:
        return None
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_output_names(compile_params: Optional[Dict[str, Any]] = None,
                       onnx_info: Optional[Dict[str, Any]] = None,
                       aimet: Optional[bool] = None,
                       qai_hub_models_version: Optional[str] = None) -> dict:
    """Inspect one compile-params dict for the #366 pitfall.

    compile_params: the dict that would be handed to the Hub compile job
        (e.g. the params read back from a failed job).
    onnx_info: parsed ONNX structure from onnx_parse.parse_onnx, or None.
    aimet: caller assertion that the model is AIMET-quantized; overrides
        detection when onnx_info is absent. None means unknown.
    """
    title = "AIMET ONNX + --output_names (#366)"
    if compile_params is None:
        return skipped(CHECK_ID, title,
                       "No compile params supplied; nothing to inspect.",
                       "Pass --compile-params with the params JSON of the "
                       "compile job (read them back from a failed job).",
                       evidence=EVIDENCE)
    if onnx_info is not None:
        aimet = is_aimet_onnx(onnx_info)
    has_flag = "output_names" in compile_params
    version_note = ""
    if qai_hub_models_version:
        parsed = _version_tuple(qai_hub_models_version)
        if parsed is not None and parsed < FIXED_IN_VERSION:
            version_note = (" qai_hub_models %s predates the official "
                            "#366 fix (0.67.0); upgrade when available."
                            % qai_hub_models_version)
        elif parsed is not None:
            version_note = (" qai_hub_models %s already carries the "
                            "official #366 fix." % qai_hub_models_version)
    value = {"output_names": compile_params.get("output_names"),
             "aimet": aimet,
             "qai_hub_models_version": qai_hub_models_version}
    if has_flag and aimet:
        return result(CHECK_ID, title, "fail", value,
                      "AIMET-quantized ONNX with --output_names in the "
                      "compile params: the Hub compiler rejects this "
                      "combination (issue #366)." + version_note,
                      "Drop output_names from the params and pin the input "
                      "shapes (manual chain in the failure path), or "
                      "upgrade qai_hub_models to >= 0.67.0.",
                      fixable=True, evidence=EVIDENCE)
    if has_flag and aimet is None:
        return result(CHECK_ID, title, "warn", value,
                      "output_names is present but whether the ONNX is "
                      "AIMET-quantized could not be determined; the Hub "
                      "rejects the flag only for AIMET ONNX." + version_note,
                      "Pass --onnx (or --aimet) so the check can decide.",
                      fixable=False, evidence=EVIDENCE)
    return result(CHECK_ID, title, "pass", value,
                  "No --output_names pitfall: flag absent, or model is not "
                  "AIMET-quantized so the Hub accepts it." + version_note,
                  evidence=EVIDENCE)


def check_output_names_file(params_path: Path,
                            onnx_path: Optional[Path] = None,
                            aimet: Optional[bool] = None,
                            qai_hub_models_version: Optional[str] = None) -> dict:
    """File-based wrapper: read params JSON, optionally parse an ONNX file."""
    import json

    title = "AIMET ONNX + --output_names (#366)"
    if not params_path.is_file():
        return skipped(CHECK_ID, title,
                       "Compile params file not found: %s" % params_path,
                       "Pass the params JSON read back from the Hub job.",
                       evidence=EVIDENCE)
    try:
        params = json.loads(params_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        return skipped(CHECK_ID, title,
                       "Cannot read compile params JSON: %s" % error,
                       "Pass a JSON object of compile params.",
                       evidence=EVIDENCE)
    if not isinstance(params, dict):
        return skipped(CHECK_ID, title,
                       "Compile params JSON is not an object.",
                       "Pass a JSON object of compile params.",
                       evidence=EVIDENCE)
    info = None
    if onnx_path is not None:
        if not onnx_path.is_file():
            return skipped(CHECK_ID, title,
                           "ONNX file not found: %s" % onnx_path,
                           "Pass an existing .onnx file.",
                           evidence=EVIDENCE)
        try:
            info = load_onnx(onnx_path)
        except (OSError, OnnxParseError) as error:
            return skipped(CHECK_ID, title,
                           "Cannot parse ONNX: %s" % error,
                           "Pass a readable .onnx file.",
                           evidence=EVIDENCE)
    return check_output_names(params, onnx_info=info, aimet=aimet,
                              qai_hub_models_version=qai_hub_models_version)
