# Reuse inventory — QCS Doctor round 1 (2026-11-17)

Ported from RK Edge Doctor (`~/workspace/rk-edge-doctor/repo`, HEAD
ed96263) and qcs-bench, per the round-1 task book. BUILD cap is 3;
this round used all 3. Nothing beyond the cap was built.

## REUSE (taken as-is or with trivial renames)

| Capability | Source | Notes |
|---|---|---|
| `onnx_parse.py` (stdlib ONNX wire parser) | RK Edge Doctor `src/rkdoctor/onnx_parse.py` | Verbatim copy; used by check 1 to detect AIMET-quantized ONNX (QuantizeLinear/DequantizeLinear nodes, producer string) and to read graph input shapes |
| CLI subcommand skeleton (`check` / `fix`, argparse, `--json`/`--html`/`--quiet`, exit codes 0/1/2) | RK Edge Doctor `cli.py` | Same shape, QCS subcommands instead of board/model/rtsp/convert |
| Check result model (`result`/`skipped`, id/title/status/value/detail/hint) | RK Edge Doctor `checks/board.py::result` | Same dict shape, plus `fixable` and `evidence` fields |
| One-page report (schema 1 JSON, summary cards, HEALTHY/ATTENTION/CRITICAL, escaped HTML) | RK Edge Doctor `report.py` | Genericized: host block is the build host, not a board; one table incl. evidence column |
| Tests organization (pytest, `tests/`, `pythonpath=["src"]`, `-ra`) | RK Edge Doctor `pyproject.toml` | Same layout |
| Data JSON truth-source format | qcs-bench | Referenced only this round; bench writes not implemented (round 2+) |

## ADAPT (existing material reshaped into a formal action)

| Capability | Source | Change |
|---|---|---|
| Manual chain: drop `--output_names` + pin shapes | QWEN3 failure-path manual chain | Became check 1 + its fix plan (flag removal as a copy patch; shape pinning stays a documented follow-up, not automated) |
| `curl -C -` resume + byte-count + testzip | INTERNVL35 hurdle 3 rescue steps | Became check 5 preflight + fix script (executor never fetches) |
| TMPDIR redirect | INTERNVL35 TMPDIR fallback fix | Became check 6 + fix snippet, with a candidate-directory search |
| HF auth call pattern | `custom.huggingface` helper `hf.py` | Referenced only; no HF calls in round 1 |

## LIB (external, used as-is)

| Capability | Source |
|---|---|
| `qai_hub` / `qai_hub_models` official clients | Not imported in round 1; version string only (check 1 upgrade hint) |
| `hashlib.sha256`, `zipfile.testzip`, `shutil.disk_usage` | Python standard library |

## BUILD (new, 3/3 — at cap)

| # | Item | Contents |
|---|---|---|
| ① | Stage model + 4 checks on the REUSE frame | Check registry/result model extension, checks 1/5/6/A2 with tests; A5's parse layer reuses Edge Doctor `onnx_parse.py` (counted inside ①, not a separate BUILD) |
| ② | Fix executor (`fix.py`) | Dry-run diff + copy patch + SHA-256 verification, shared by A-level fixes; "command" fixes emitted as scripts, never executed |
| ③ | Evidence pack generator (`evidence.py`) | Manifest + markdown skeleton + interface; C-level checks 8/A6 NOT implemented this round — only the scaffold |

## Not built this round (deferred, not claimed)

- Checks 2 (default precision), 3 (torch gate), 4 (QuantSim no-op), 7 (HF gated), 8 (unquantized tensor, C-level), 9 (packaging combo), A3, A4, A5 (quantization completeness pre-check), A6 (manifest precision claim)
- Hub job submission / verification loop (validation closure; round 2+)
- qcs-bench JSON write path
