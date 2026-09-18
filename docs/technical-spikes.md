# Technical validation for Python + PySide6 / Qt Widgets

[简体中文版](../docs-zh/technical-spikes.md)

Status: **S1/S2 EXECUTED 2026-09-18 on the macOS development machine — see "Executed evidence" below. S3, S6 and persistence validation remain PLANNED, NOT EXECUTED.** The owner has selected the production stack and confirmed product rules 1–7. Targets: Windows 10/11 x64, users without administrator/installation privileges. This document defines bounded validation inside the selected stack; it does not authorize further probes or production implementation. Timeboxes are effort caps, not delivery promises, with approximately eight hours/week available.

Development and CI use the same Python 3.13/PySide6 source on macOS and Windows.
Production remains Windows 10/11 x64. Windows packages are built on Windows only;
the initial candidate format is a PyInstaller onedir portable directory. This
infrastructure narrows S3 but does not count as clean-machine deployment evidence.

## Inputs and order

Obtain sanitized representative DOCX files, independent engineer labels, clean Windows 10 and 11 x64 test environments, exact OS builds, and IT rules for running portable/per-user applications. Initial distribution, extraction/installation, first launch and checking must be completely offline. Prepare the complete bundle before transfer through an approved offline channel; no target-side online downloads or package installation steps.

Before S1/S2, record the available development/build interpreter, permissions, Windows build host and exact candidate dependencies. Check current upstream requirements rather than attempting latest PySide6 installation into Python 3.8. Then run S1/S2 against the same fixtures, and S3 early before substantial UI work. S6 validates the already-approved rules rather than asking again whether partial strike or conflicting evidence should be unresolved. No parallel .NET/Electron/Tauri implementation is planned.

| Spike | Minimal question / experiment | Acceptance evidence | Effort cap and impact |
|---|---|---|---|
| S1 OOXML fidelity | Evaluate a Python document adapter, initially considering python-docx plus focused OOXML access. Extract body/table paragraphs and runs; inspect direct/inherited strike, explicit false, basedOn/defaults, double strike and tracked revisions as a distinct feature. | Raw text, original spans, effective strike and formatting origin match independent labels. Unknown/unsupported structures explicit; no None-to-false conversion. Record library/runtime versions and gaps. | 4–8 h initial probe. Select adapter approach within Python; do not build a full parser. |
| S2 Locations and coverage | Traverse body and cell paragraphs, nested/merged tables; reconstruct split runs; map conservative normalized text back to raw spans. Detect excluded parts/structures. | Every evidence location resolves in the same input snapshot; no cross-cell or cross-paragraph joins; merged-cell convention explicit; no duplicate extraction; COMPLETE/LIMITED coverage honest. | 3–5 h, can share fixtures with S1. Gate traceability. |
| S3 No-admin Windows deployment | Build the minimal Qt Widgets application on Windows x64 with the pinned PyInstaller onedir spec, then test the complete portable directory on Windows 10/11 x64 without developer runtimes or elevation. No installer or onefile package is in this initial scope. | Launch/check/replace/remove as ordinary user; no UAC, Program Files or required machine-wide writes; bundled dependencies; user-data resolved through Qt `QStandardPaths` and preserved outside the executable directory. Record OS builds, Python/Qt/PyInstaller versions, size, startup, Chinese paths/input, DPI and endpoint-policy findings. Disconnected transfer/setup/first-launch/checking is mandatory; test without cached prerequisites and with the existing Python 3.8 unchanged, plus a clean machine without Python. Record any dependency on PATH or external runtimes. | Windows CI may prove that the bundle builds and contains the executable, but S3 still requires real Windows/IT access. Failure blocks that distribution, not automatic stack replacement. |
| S4 Desktop/core IPC | Retired from the previous candidate comparison. Selected architecture has no sidecar or core server. | No work or protocol introduced. UI responsiveness remains S6/Qt validation. | 0 h. Reopen only after a new architectural decision. |
| S5 Future DOCX preservation | Deferred advisory probe: open/save a copy, optionally modify one run; compare package parts and Word rendering. | Preservation/loss evidence for styles/tables/relationships, no lossless claim from text equality. Original unchanged. | 2–4 h only if later authorized; not a gate while editing remains outside MVP. |
| S6 Deterministic rules and scale | Review detectionPhrase/aliases and associated requirement spans; test normalization allowlist, conflict and partial-strike rules, ambiguous similar phrases and representative file sizes. | Specific detection phrases establish intended function; broad related words do not. Numbers/units/negation retained. Single changed value → CONFIGURED + DIFFERENT; conflicting active values, mixed active/deleted, partial/unknown strike → UNRESOLVED. Empty expected description/unsupported comparison → NOT_COMPARED. Record memory/time and cancellation behavior. | 3–5 h initial probe. Complex cases become explicit unresolved outcomes, not hidden heuristics. |

## Executed evidence — S1 and S2 (2026-09-18)

Executed as one bounded slice on the macOS development machine only. No
Windows runtime, clean-machine, packaged-runtime or real-customer-document
evidence is claimed.

Environment (recorded from the actual probe run):

- OS: macOS 26.7 (x86_64); development platform only, not the production target.
- Python 3.13.7; python-docx 1.2.0 (+ lxml 6.1.3); PySide6 6.11.2 installed but unused by the probe.
- Probe code: `tests/docx_probe.py` — an exploratory adapter kept intentionally
  isolated from the production placeholders in `src/`.
- Fixtures: `tests/fixture_factory.py` builds nine deterministic synthetic
  documents per test session (normal, table, nested-merged, strike-matrix,
  docdefaults-strike, tracked-revisions, excluded-parts, empty, malformed),
  with small documented raw-OOXML patches for cases python-docx cannot
  generate (dstrike, invalid strike value, orphan rStyle, docDefaults strike,
  w:ins/w:del, w:sdt, text box, hidden vMerge continuation text).
- Expected labels are hand-written in `tests/test_spike_s1_oxml_fidelity.py`
  and `tests/test_spike_s2_locations_coverage.py`, not copied from probe
  output.

### S1 — OOXML fidelity: observed results

| Case (fixture) | Expected (independent label) | Observed | Outcome |
|---|---|---|---|
| Body paragraph text, split runs, adjacent same-format runs (normal) | exact texts; contiguous half-open code-point run offsets; empty paragraph is a zero-run block | matches | pass |
| Direct strike true / explicit false (strike-matrix) | True/False from run rPr | `run.font.strike` returns the direct value | pass |
| Partial strike, mixed runs (strike-matrix) | per-run False/True/False | matches | pass |
| Style-inherited strike via basedOn (strike-matrix) | True, origin paragraph style | `run.font.strike` is None (style value invisible to the API); element-level chain resolution works | pass — needs focused XML |
| Explicit-false override under inherited style strike (strike-matrix) | False, direct wins | matches | pass |
| docDefaults strike (docdefaults-strike) | True via rPrDefault; explicit run false overrides | matches via element-level read of `w:docDefaults` | pass — needs focused XML |
| Double strike `w:dstrike` (strike-matrix) | detectable; product classification open | `font.double_strike` is True; probe keeps effective strike unknown with `double-strike` reason | limited / open question |
| Invalid `w:strike w:val="maybe"` (strike-matrix) | unknown, never false | python-docx raises `InvalidXmlError` on `font.strike`; probe classifies unknown | pass — unknown preserved |
| Orphan `w:rStyle` reference (strike-matrix) | unknown | python-docx `run.style` silently falls back to "Default Paragraph Font"; probe detects the orphan reference itself and reports unknown | pass — API alone unsafe |
| Tracked revisions `w:ins`/`w:del` (tracked-revisions) | separate/unsupported, explicit | `paragraph.runs`/`.text` silently omit ins/del content; probe marks the block LIMITED (`tracked-revisions-unsupported`) and excludes revision text | limited by design |
| Malformed input (malformed) | explicit failure | `PackageNotFoundError`; coverage FAILED with error text, zero blocks | pass |
| Valid empty document (empty) | COMPLETE, zero blocks, no error | matches; distinct from FAILED | pass |
| Original bytes unchanged (all readable fixtures) | file hash identical before/after probe | matches | pass |

### S2 — locations and coverage: observed results

| Case (fixture) | Expected | Observed | Outcome |
|---|---|---|---|
| Body paragraph indices; table/cell paragraph indices; nested-table ancestor path (normal/table/nested-merged) | stable block ids (`body:pN`, `t0r1c1:table-cell:pN`, nested `t0r2c1>t0r0c0:table-cell:p0`), cell-local paragraph indices | matches; identical across re-probes | pass |
| Multi-paragraph cell; no cross-paragraph/cell joins (table) | separate blocks | matches | pass |
| Merged cells (nested-merged) | gridSpan/vMerge master extracted once at its master grid position | naive `Table.rows[i].cells` repeats merged cells (duplicate-extraction hazard confirmed); w:tc-level traversal extracts each master exactly once | pass — needs focused XML |
| vMerge continuation with hidden text (nested-merged) | excluded but explicit | no block; coverage LIMITED `merged-cell-continuation-content-excluded` | pass |
| Split-run reconstruction (all) | raw text equals concatenated run texts; contiguous half-open offsets | matches for every block | pass |
| Conservative normalization + raw-span mapping (normal) | whitespace collapse only; normalized spans map back to exact raw offsets ("B C" → raw "B\tC" at [3,6)) | matches; collapsed whitespace runs map to whole raw runs | pass — allowlist finalization deferred to S6 |
| Excluded structures (excluded-parts) | headers/footers, body-level `w:sdt` paragraphs and text-box text excluded with explicit LIMITED reasons | `doc.paragraphs` silently omits sdt/textbox content; probe reports `header-/footer-content-not-checked`, `content-control-content-excluded`, `textbox-content-excluded` | pass |
| Duplicate prevention (all) | unique block ids; merged text appears once | matches | pass |
| Coverage honesty (all) | COMPLETE only with zero reasons; LIMITED with reasons; FAILED distinct from valid-empty | matches | pass |

### Findings that shape Task 2

1. **Selected adapter strategy: python-docx 1.2.0 + focused OOXML/XML access**
   (lxml via python-docx). It is sufficient for the declared MVP scope:
   body/table/cell paragraphs, runs with code-point offsets, effective strike
   with unknown preservation, stable locations, explicit coverage warnings.
   The dependency is pinned in `pyproject.toml`.
2. Three silent-loss hazards in the python-docx API must be compensated in the
   production adapter: runs inside `w:ins`/`w:del` are omitted from
   `paragraph.runs`/`.text`; merged cells are duplicated by `row.cells`;
   body-level `w:sdt` and text-box content are invisible to `doc.paragraphs`.
   The probe compensates through element-level traversal plus explicit LIMITED
   reasons; the production adapter must do the same.
3. Effective strike cannot come from `run.font.strike` alone (direct value
   only; style/docDefaults values invisible; orphan rStyle silently falls back
   to the default character style). Chain resolution run rPr → character style
   chain → paragraph style chain → docDefaults → default-off is required, with
   unknown preserved for invalid values, orphan/broken chains and double strike.
4. Every unknown strike value in probe output carries an explicit reason
   (asserted by test); unknown is never converted to false.

### Not probed / remaining limitations

- Table-style character formatting, linked styles, `w:rPrChange` tracked
  formatting, field codes (`w:instrText`), hyperlink-wrapped runs,
  footnotes/endnotes, first-page/even-page headers, password-protected
  (encrypted) OOXML, `w:altChunk`, oversized documents.
- Only synthetic fixtures on macOS; no sanitized real customer documents, no
  Windows execution. CI runs the same tests on windows-latest, which is still
  not S3 deployment evidence.
- The normalization allowlist is deliberately minimal (whitespace collapse);
  punctuation/width mappings remain an S6 output.
- Effort: executed within a single bounded session, inside the combined S1+S2
  timebox guidance.

### Unresolved questions

- Product meaning of `w:dstrike`: should double strike count as deletion
  formatting (struck) or remain a distinct unknown? The probe reports unknown.
- Should text inside `w:ins` (tracked insertion) be included in extracted
  block text? Currently excluded with a LIMITED reason.

**Task 2 status: unblocked.** The document access strategy is established with
evidence; Task 2 (first DOCX vertical slice) can be implemented on this basis,
pending explicit authorization.

## Persistence validation inside the selected stack

Before checklist persistence implementation, compare the smallest viable local data formats for one baseline. Validate stable IDs, required detectionPhrase, Unicode, atomic save/recovery, permission failures, schema identification and restart. Use a user-writable application-data location separate from program files; no shared database service. Select a format in a short recorded decision, with a 1–2 h initial cap. This does not add multi-baseline or version-management features.

## Fixtures and evidence

Start with normal.docx, table.docx, strikethrough.docx, partial-strikethrough.docx, mixed-runs.docx, alias-match.docx, missing-function.docx and description-difference.docx. Add inherited-strike-override, active/deleted coexistence, conflicting active values, consistent repeated values, ambiguous/broad phrases, nested/merged tables, split paragraphs, tracked revisions, excluded parts, malformed/protected and large inputs. Synthetic fixtures isolate behavior; sanitized historical files validate representativeness.

Independently label expected function identity, requirement spans, formatting, locations, resolution and coverage before comparing implementation output. A protected/malformed input must fail explicitly. Bound ZIP/XML resource use and avoid external relationship fetches; no infrastructure is implied.

For every executed probe record hypothesis, exact versions/environment, fixture identity, observed output, pass/fail/unknown per case, effort spent and remaining limitations. Stop at the timebox, report gaps and agree follow-up. Approval of the stack is not evidence of a passing probe. Do not switch frameworks without a new owner decision.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
