# Changelog

## 0.1.0 — 2026-11-17

First round: repo skeleton + 4 checks.

- New repo `anguoyang/qcs-doctor`, CLI `qcsdoctor` (`check` / `fix`),
  schema-1 JSON + one-page HTML reports.
- Checks: `output_names` (#366, A-level), `downloader` (A-level),
  `tmpdir` (A-level), `aimet_wheel` (pre-check).
- Fix executor: dry-run diff + copy patch + SHA-256 verification;
  command fixes emitted as scripts, never executed.
- Evidence pack generator: scaffold only (C-level checks not yet
  implemented).
