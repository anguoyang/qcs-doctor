"""Check A2: aimet-onnx has no wheel for this platform.

Evidence: qualcomm-recipe/INTERNVL35_2B_FAILURE_PATH_2026-11-16.md
hurdle 2. ``pip install aimet-onnx==2.37.0`` on gb10 (aarch64,
Python 3.12.3) reported ``Could not find a version that satisfies
the requirement aimet-onnx==2.37.0 (from versions: none)`` — neither
the official index nor the mirror carries an aarch64/cp312 wheel.
The template then fails at Collection build time because the vision
encoder eagerly constructs an AIMET QuantSim
(``NameError: name 'QuantizationSimModel' is not defined``,
templates/intern3_5_vl/model.py:902).

This is a pre-install check: it consults a table of wheel
availability recorded from real failures, and never touches the
network. Unknown platform/version combinations are reported as
"skip" (unknown), never guessed.
"""

import platform
import sys
from typing import Optional

from . import result, skipped

CHECK_ID = "aimet_wheel"
EVIDENCE = ("qualcomm-recipe/INTERNVL35_2B_FAILURE_PATH_2026-11-16.md "
            "hurdle 2 (no aarch64/cp312 wheel for aimet-onnx 2.37.0; "
            "model.py:902 NameError)")

# (machine, python tag) -> packages with no wheel on any index checked.
# Recorded from real failures only; absence from this table means
# "no recorded data", not "a wheel exists".
KNOWN_MISSING = {
    ("aarch64", "cp312"): ("aimet-onnx",),
}


def python_tag(major: int = sys.version_info.major,
               minor: int = sys.version_info.minor) -> str:
    return "cp%d%d" % (major, minor)


def check_aimet_wheel(machine: Optional[str] = None,
                      tag: Optional[str] = None,
                      package: str = "aimet-onnx",
                      version: str = "2.37.0") -> dict:
    """Pre-check whether a package wheel exists for this platform.

    machine: platform.machine() value (default: this host).
    tag: CPython tag like "cp312" (default: this interpreter).
    """
    title = "aimet-onnx wheel missing for this platform"
    machine = machine or platform.machine()
    tag = tag or python_tag()
    value = {"machine": machine, "python_tag": tag,
             "package": package, "version": version}
    missing = KNOWN_MISSING.get((machine, tag), ())
    if package in missing:
        return result(CHECK_ID, title, "fail", value,
                      "%s %s has no wheel for %s / %s on any index "
                      "checked (official or mirror); pip install fails "
                      "before anything is installed."
                      % (package, version, machine, tag),
                      "Do not install on this host. Either split the "
                      "model on an x86_64 host, or use the no-op "
                      "_init_quantized_session path with hash verification "
                      "of the serialized assets (see the failure path).",
                      fixable=False, evidence=EVIDENCE)
    if machine == "x86_64":
        return result(CHECK_ID, title, "pass", value,
                      "x86_64 wheels exist for %s; install can proceed."
                      % package,
                      evidence=EVIDENCE)
    return skipped(CHECK_ID, title,
                   "No recorded wheel data for %s / %s; availability is "
                   "unknown, not assumed." % (machine, tag),
                   "Verify with: pip download --no-deps --no-build-isolation "
                   "%s==%s" % (package, version),
                   evidence=EVIDENCE)
