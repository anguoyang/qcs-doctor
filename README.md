# QCS Doctor

Not just a check-up — a fix. QCS Doctor diagnoses Qualcomm AI Hub
deployment failures (export → compile → link → on-device profile) and,
where a fix is safe and reversible, produces it: dry-run diff first,
patch applied only to a copy with hash verification, original assets
read-only. Where the defect is in a vendor asset or pipeline, it
produces a failure-path record plus an issue evidence pack instead of
pretending to fix it.

Fix levels: **A** automatic (safe, reversible) · **B** guided (one
command, confirmed, logged) · **C** report-only (vendor defect).

Target chip in v0: QCS6490 (Dragonwing RB3 Gen 2). Every check is
grounded in a real failure path — no check without evidence.

## Install

Standard library only, Python ≥ 3.9:

```sh
pip install .
qcsdoctor --version
```

## Usage

```sh
# Run all implemented checks (missing inputs are reported as "skip")
qcsdoctor check --compile-params params.json --onnx model.onnx \
  --asset-url https://example.com/fp16mix.zip --expected-bytes 9388733639 \
  --cache ./cache/fp16mix.zip --tmpdir /tmp --need-bytes 2147483648 \
  --json report.json --html report.html

# Plan a fix (dry-run: prints the diff, writes nothing)
qcsdoctor fix --check output_names --compile-params params.json

# Apply it: the fixed copy lands in qcsdoctor-fix/, hash-verified
qcsdoctor fix --check output_names --compile-params params.json --apply
```

## Checks in v0.1.0 (4 of the 12 planned)

| ID | Level | What it catches | Evidence |
|----|-------|-----------------|----------|
| `output_names` | A | AIMET ONNX + `--output_names` in compile params (Hub rejects it) | QWEN3 failure path, issue #366, jobs jp0x1z32p / jp2z70o4p |
| `downloader` | A | Bundled downloader stalls with no timeout; preflight + `curl -C -` resume plan | QWEN3 pre-death history; INTERNVL35 hurdle 3 |
| `tmpdir` | A | Temp dir too small (512 MB /tmp blown); TMPDIR redirect | QWEN3 pre-death history; INTERNVL35 TMPDIR fallback |
| `aimet_wheel` | pre-check | `aimet-onnx` has no aarch64/cp312 wheel — catch it before install | INTERNVL35 hurdle 2 |

Planned, not yet implemented: checks 2, 3, 4, 7, 8, 9 and AIMET
group A3–A6 (12 checks total in v0). The full list and the failure
paths live in the charter; the v0 roadmap is tracked in
`REUSE_INVENTORY.md` and the changelog.

## Safety rules

- Fixes are dry-run first; the original asset is never modified.
- Patches apply only to copies, with SHA-256 verified before/after.
- The executor never fetches from the network; the resumable-download
  fix is emitted as a script for you to run.
- Hub credentials stay on your machine — never in logs or in the repo.
- No check without a failure-path source. Failures are recorded
  honestly, including the ones this tool cannot fix.

## Development

```sh
python -m pytest
```

Reuse inventory (what was ported from RK Edge Doctor, what was
adapted, what was built new): see `REUSE_INVENTORY.md`.

## License

Apache-2.0.
