# Design Requirement Checker — Internal Demo Status

[简体中文版](../docs-zh/demo-readiness.md)

**Status date:** 2026-09-23 · **Branch basis:** `main` at `96bfe48` (PR #8 merged, CI green)

## Milestone

**v0.1 Internal Demo.** This milestone means: a stable, usable internal demo.
It explicitly does **not** mean: Production Ready, Release Validated, or
Pilot Approved.

## Implemented demo capabilities

All items below exist in the production source under
`src/design_requirement_checker/` and are exercised by the repository test
suite:

- **DOCX import** using python-docx 1.2.0 + focused OOXML/lxml access
  (`docx_adapter.py`); the source `.docx` is never modified.
- **Paragraph/table source locations** with stable snapshot coordinates.
- **Effective strike interpretation** resolved through the full style chain
  (run → character style → paragraph style → default style → docDefaults);
  unknown formatting stays unknown.
- **COMPLETE / LIMITED coverage**: known unsupported structures (tracked
  revisions, text boxes, field codes, footnote/endnote references, smart
  tags, `w:altChunk`, excluded header/footer content, nested/invalid
  hyperlinks) force LIMITED rather than disappearing silently.
- **Deterministic matching** (`matching.py`): exact / normalized (validated
  N1–N3 allowlist) / alias detection with raw-source traceability;
  forward-only requirement-span association with explicit uncertainty
  reasons.
- **Evidence**: all qualifying occurrences retained in source order;
  `primary_evidence_id` is only an initial UI selection aid.
- **Results**: `CONFIGURED` / `MISSING` / `STRUCK_OUT` statuses plus a
  separate `UNRESOLVED` resolution (status unset); description comparison
  `SAME` / `DIFFERENT` / `NOT_COMPARED` is an independent, orthogonal
  dimension.
- **Multiple-evidence inspection and source-context inspection** in the Qt
  review workspace (`ui/main_window.py`): summary counts, priority ordering,
  filters (全部/已配置/未配置/已划除/待人工核查/仅异常), search, detail pane
  with expected vs actual, match method, reasons and reconstructed
  prev/current/next block context.
- **Background import and verification** off the UI thread with cooperative
  cancellation (`threading.Event`) and stale-result suppression
  (operation-generation token).
- **Local baseline management** (`ui/checklist_dialog.py`,
  `ui/item_editor_dialog.py`): add/edit/disable/confirmed-delete, duplicate
  code rejected, duplicate names / overlapping detection phrases flagged,
  stable `item_id` / `alias_id`.
- **Atomic JSON persistence** (`baseline_store.py`):
  `QStandardPaths.AppDataLocation / baseline.json`, `schemaVersion = 1`,
  two-temp-file atomic save, `baseline.json.bak` backup recovery, strict
  validation, unsupported-schema protection on both load and save.
- **Windows PyInstaller onedir build** via the manually triggered
  `build-windows.yml` workflow producing
  `dist/DesignRequirementChecker/DesignRequirementChecker.exe`.

## Demo evidence

- **Source-level CI**: GitHub Actions runs the full test/lint/format/type
  suite on `macos-latest / Python 3.13` and `windows-latest / Python 3.13`;
  green on `main` at `96bfe48`.
- **Windows PyInstaller workflow**: `build-windows.yml` exists and builds +
  uploads the onedir artifact (manually triggered).
- **Owner manual smoke check**: the owner downloaded the Windows executable
  artifact and ran it successfully on a company computer. This is recorded
  as a **demo smoke check only**. No OS version, administrator status,
  network state, endpoint-policy state or Python presence/absence was
  separately recorded for that run, and none may be inferred.

## Deferred validation (DEFERRED FOR DEMO MILESTONE)

These items are **not required** for the current internal-demo milestone.
They remain prerequisites before claiming production/pilot readiness.

**Formal Task 6 evidence — deferred:**

- real/sanitized independently labelled historical corpus
- measured precision / recall
- measured strike accuracy
- measured comparison accuracy
- measured unresolved / coverage rates
- measured review-time reduction
- release-threshold approval

The Task 6 evaluation tooling under `validation/` stays in the repository
for future use; it has produced no measured metrics (all metrics NOT
MEASURED, denominator 0).

**Formal Task 7 / S3 validation — deferred:**

- clean Windows 10 validation
- clean Windows 11 validation
- standard-user / no-admin validation matrix
- Python-absent machine test
- unchanged company Python 3.8 coexistence matrix
- fully offline clean-machine test
- enterprise endpoint-protection / policy validation
- application replacement / upgrade persistence validation
- formal error-log location validation

**Existing manual-validation gaps — deferred:**

- formal Windows DPI matrix
- formal Chinese-input validation matrix
- formal long-description layout matrix

## Demo limitations

- No measured historical precision/recall yet.
- No formal production release threshold.
- No clean-machine deployment matrix.
- No report export (V0.2 candidate).
- No fuzzy or semantic matching (deterministic rules only, by design).
- Unsupported Word structures produce LIMITED coverage rather than results.
- No automatic joining of requirement text across paragraphs or table cells.
- No automatic engineering acceptance: the tool surfaces evidence and
  uncertainty; a human reviewer decides.

## Final demo status

| Area | Status |
|---|---|
| DOCX ingestion | PASS |
| Deterministic verification | PASS |
| Qt review workspace | PASS |
| Baseline management | PASS |
| Local persistence | PASS |
| Source-level macOS CI | PASS |
| Source-level Windows CI | PASS |
| Windows portable build workflow | AVAILABLE |
| Owner manual Windows demo smoke test | PASS — owner reported |
| Historical measured validation | DEFERRED |
| Clean-machine Win10/11 validation | DEFERRED |
| No-admin/offline formal validation | DEFERRED |
| Release thresholds | DEFERRED |
| Report export | OUT OF SCOPE / V0.2 |

`PASS` is used only where actual evidence exists (test suite, CI runs, or
the owner-reported manual run). Nothing in this table claims deployment
certification.
