# Technical validation for Python + PySide6 / Qt Widgets

[简体中文版](../docs-zh/technical-spikes.md)

Status: **S1/S2 EXECUTED 2026-09-18 and S6 EXECUTED 2026-09-19 on the macOS development machine — see "Executed evidence" below. S3 and persistence validation remain PLANNED, NOT EXECUTED.** The owner has selected the production stack and confirmed product rules 1–7. Targets: Windows 10/11 x64, users without administrator/installation privileges. This document defines bounded validation inside the selected stack; it does not authorize further probes or production implementation. Timeboxes are effort caps, not delivery promises, with approximately eight hours/week available.

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

### Task 2 remediation — ingestion/coverage evidence (2026-09-18)

Executed as a bounded remediation of the Task 2 slice on the same macOS
development environment (python-docx 1.2.0, lxml 6.1.3, PySide6 6.11.2,
Python 3.13.7). All observations below are covered by hand-labelled
regression fixtures in `tests/fixture_factory.py` and tests in
`tests/test_docx_adapter.py`, `tests/test_application.py`,
`tests/test_ui.py`.

- **Hyperlink-wrapped runs are extracted.** Observed: `paragraph.runs` omits
  runs inside `w:hyperlink` (python-docx 1.2.0's `paragraph.text` includes
  them, but the Task 2 adapter reconstructed block text from `paragraph.runs`,
  so "Prefix [hyperlink text] suffix" lost its middle run and its strike).
  `Paragraph.iter_inner_content()` yields Run|Hyperlink in document order and
  `Hyperlink.runs` preserves text and direct strike, so the adapter now
  extracts hyperlink runs with contiguous offsets and resolved strike; the
  link URL itself is never document text. A hyperlink nested inside another
  hyperlink (invalid OOXML) stays invisible to every run accessor and produces
  `nested-hyperlink-content-excluded` instead of silent loss.
- **Header/footer variants are detected.** Observed: first-page and even-page
  headers/footers (`w:titlePg`, odd-and-even settings) and table-only
  header/footer content were previously missed. All six variants are now
  checked for paragraph and table content; each side keeps one stable token
  (`header-content-not-checked` / `footer-content-not-checked`) across all
  variants, and the content never enters body blocks. Reading `.paragraphs`
  of a linked-to-previous container creates a header part in the in-memory
  package, so the adapter checks `is_linked_to_previous` before any content
  access.
- **Known unsupported structures force LIMITED.** Observed silent losses in
  `paragraph.runs`: `w:fldSimple` cached-result runs and `w:smartTag`-wrapped
  runs. Complex-field runs (`w:fldChar`/`w:instrText`) produce empty-text runs
  whose field result (a direct paragraph child) stays extracted. The adapter
  now detects `w:instrText`, `w:fldSimple`, `w:footnoteReference`,
  `w:endnoteReference`, `w:smartTag` and body-level `w:altChunk` with stable
  tokens (`field-code-content-excluded`, `footnote-or-endnote-content-excluded`,
  `smart-tag-content-excluded`, `alt-chunk-content-excluded`); none of them
  can yield a silent COMPLETE result. No field evaluation, footnote or
  altChunk extraction is attempted.
- **Default paragraph style resolved from the marker, not the id.** The
  default paragraph style is the `w:style` with `w:type="paragraph"` and
  `w:default="1"` (the shipped template marks "Normal"; a fixture with
  `CorpBody` as the default id resolves inherited strike correctly). If the
  marker is absent or ambiguous, no default style is fabricated and the chain
  falls back to docDefaults.
- **Read-failure categories.** `file-access-error` (OSError while reading),
  `invalid-or-unreadable-document` (BadZipFile, missing package parts,
  invalid XML — including the OLE compound-file container Word produces for
  password-protected documents, exercised by the deterministic
  `build_ole_container` fixture), and `unexpected-parser-error` (an injected
  collection bug is reported under its own category and never mislabelled as
  an invalid document). The broad `except Exception` around strike parsing was
  removed: `w:strike`/`w:dstrike` are read element-level, classifying invalid
  ST_OnOff values as unknown-with-reason without catching programmer errors.
- **Preview whitespace.** Qt's rich-text engine collapses runs of spaces in
  plain `<p>` elements ("A  B\tC" renders as "A B C"); run paragraphs now use
  `white-space: pre-wrap`, verified by a QTextDocument round-trip test. The
  domain text is unchanged.
- **Windows build.** Source-level CI (macOS + Windows, Python 3.13) covers the
  remediation commit; the manually triggered PyInstaller workflow
  (`build-windows.yml`) was **not run** for this slice and remains pending
  (see the implementation plan). This is not S3 evidence.

### Not probed / remaining limitations

- Table-style character formatting, linked styles, `w:rPrChange` tracked
  formatting, hidden text (`w:vanish`), comments, block-level `w:customXml`,
  oversized documents.
- Encrypted/password-protected DOCX: only the OLE container-format failure
  path is exercised (explicit import failure). No decryption exists and no
  real Office-produced encrypted files were validated.
- Only synthetic fixtures on macOS; no sanitized real customer documents, no
  Windows execution beyond CI. CI runs the same tests on windows-latest,
  which is still not S3 deployment evidence.
- The normalization allowlist is deliberately minimal (whitespace collapse);
  punctuation/width mappings remain an S6 output.
- Effort: S1/S2 executed within a single bounded session, inside the combined
  S1+S2 timebox guidance; the remediation was a second bounded session.

### Unresolved questions

- Product meaning of `w:dstrike`: should double strike count as deletion
  formatting (struck) or remain a distinct unknown? The probe reports unknown.
- Should text inside `w:ins` (tracked insertion) be included in extracted
  block text? Currently excluded with a LIMITED reason.

**Task 2 status: unblocked.** The document access strategy is established with
evidence; Task 2 (first DOCX vertical slice) can be implemented on this basis,
pending explicit authorization.

## Executed evidence — S6 deterministic rules and scale (2026-09-19)

Executed as one bounded slice on the macOS development machine, on top of the
remediated Task 2 ingestion layer. No production matching code was written;
`src/design_requirement_checker/matching.py` remains a placeholder. All
evidence comes from the isolated spike probe `tests/s6_probe.py` validated
against hand-written independent labels in `tests/test_spike_s6_rules.py` and
`tests/test_spike_s6_scale.py`, plus one synthetic DOCX composition fixture
(`build_requirement_strike` in `tests/fixture_factory.py`) that runs the rules
over real ingestion output. Expected labels were written before the probe logic
(red state confirmed: both test modules failed on collection before
`s6_probe.py` existed).

### Environment

- OS: macOS 26.7 (x86_64); development platform only, not the production target.
- Python 3.13.7; python-docx 1.2.0 (+ lxml 6.1.3); pytest 9.1.1.
- Windows: GitHub CI (windows-latest) runs the same tests, which is not S3
  deployment evidence.

### Exact normalization allowlist (validated)

Applied per block; blocks are never joined. Approved transformations:

| ID | Transformation | Exact mapping |
|---|---|---|
| N1 | whitespace-run collapse | any run of ASCII space, tab and U+3000 ideographic space → one ASCII space |
| N2 | within-block line breaks | any run of `\n` `\r` `\v` `\f` → one ASCII space |
| N3 | fullwidth ASCII punctuation → ASCII | `（→(` `）→)` `：→:` `；→;` `，→,` `？→?` `！→!` `．→.` |

Everything else is preserved verbatim: digits, units, letter case, negation
words, comparison operators, ideographic punctuation. Rejected transformations
(each covered by an explicit negative test):

| ID | Tempting transformation | Rejected because |
|---|---|---|
| R1 | `。` → `.` | ideographic full stop is never rewritten; it is only recognized as a span boundary |
| R2 | fullwidth digits/letters → ASCII (`２s`→`2s`, `ＣＡＮ１`→`CAN1`) | width conversion would silently equate distinct engineering text |
| R3 | case-insensitive matching (`CAN` ≡ `can`) | no evidence that case differences are insignificant |
| R4 | NFKC-style Unicode normalization | folds width/compatibility distinctions wholesale |
| R5 | numeric/unit equivalence (`2s`≡`3s`, `24V`≡`12V`, decimal rounding) | engineering values must stay distinguishable |
| R6 | negation/antonym/operator folding (`开启`≡`不开启`, `允许`≡`禁止`, `>5km/h`≡`<5km/h`) | polarity and comparison direction are engineering meaning |
| R7 | general punctuation stripping | destroys the structure needed for span association |

Meaning-preservation assertions: none of `2s`/`3s`, `24V`/`12V`, `开启`/`不开启`,
`允许`/`禁止`, `>5km/h`/`<5km/h`, `CAN1`/`CAN2`, `２s`/`2s`, `CAN`/`can` become
equal under the allowlist.

### Raw ↔ normalized offset mapping

Every normalized character carries its raw source span
(`NormalizedText.char_sources`). Validated invariants: spans are monotonic,
non-overlapping and cover every raw code point exactly once; a normalized match
maps to the exact raw span; a collapsed whitespace run maps to the whole raw
run (`"A  B"` → `"A B"`, normalized [0,3) → raw (0,4)). Combinations tested:
multiple spaces, tabs, ideographic spaces, line breaks within a block,
fullwidth punctuation, Chinese and ASCII text. Normalization never destroys
traceability and the stored source text itself stays raw.

### Requirement-span association rule (the rule Task 3 must implement)

For each qualifying occurrence (normalized match span [s, e) inside one block):

1. The requirement span starts at `s` and extends **forward only**.
2. It ends at the earliest of: the next boundary delimiter — one of
   `;.!? ,、。` in normalized text, where `.`/`,` between digits are not
   boundaries (`2.5s`, `1,000ms` stay intact) — or the start of the next
   qualifying match in the same block, or the end of the block.
3. No backward extension: text before the match (e.g. a preceding value) is
   never associated.

Observed on the confirmed example
`2门控制增加开关门延时3s功能；1门控制增加开关门延时5s功能`: the first item
associates raw span (0,15) with value `3s`, the second (16,31) with `5s`; the
`5s` never leaks into the first item's evidence.

Unsafe associations are never guessed. The occurrence keeps its span but is
blocked from comparison with an explicit reason:

- `requirement-span-association-uncertain` — the span carries no value token
  while the expected description does, and the remainder of the enclosing
  sentence contains a value (e.g. `…，延时时间为3s。`, `…，周期10ms，延时3s。`).
  The value may or may not belong to this function, so neither seizing it nor
  comparing is safe. Observed outcome: CONFIGURED + NOT_COMPARED.
- `no-associated-requirement-content` — the span never extended past the
  matched phrase while the expected description differs from the bare phrase
  (phrase at paragraph end, or value preceding the phrase). Observed outcome:
  CONFIGURED + NOT_COMPARED.

Value tokens (number + unit from a fixed unit list, tolerating one collapsed
space between number and unit) are used **only** to detect conflicting key
parameters between occurrences of the same item; they never replace text in
comparisons.

### Strike evaluation (over the requirement span)

Strike coverage is computed over the raw requirement span by intersecting it
with run formatting supplied by ingestion (`TextRun.effective_strike`): NONE
(all active), FULL (all struck), PARTIAL (mixed true/false), UNKNOWN (any
unknown). Struck text elsewhere in the paragraph is irrelevant (validated).
"Does any run in the paragraph have strike" is explicitly insufficient.

### Truth table (observed)

| Evidence | Resolution | Status | Comparison |
|---|---|---|---|
| consistent qualifying active evidence | RESOLVED | CONFIGURED | SAME / DIFFERENT / NOT_COMPARED |
| all qualifying evidence fully struck | RESOLVED | STRUCK_OUT | NOT_COMPARED (`evidence-struck`) |
| no qualifying evidence in checked scope | RESOLVED | MISSING | NOT_COMPARED (`nothing-to-compare`) |
| partial strike | UNRESOLVED | unset | NOT_COMPARED |
| unknown formatting | UNRESOLVED | unset | NOT_COMPARED |
| active + struck coexist | UNRESOLVED | unset | NOT_COMPARED |
| conflicting active key values (`2s` vs `3s`) | UNRESOLVED | unset | NOT_COMPARED |
| ambiguous function identity | UNRESOLVED | unset | NOT_COMPARED |

No fourth CheckStatus exists; UNRESOLVED is a resolution state with status
unset. All occurrences are retained and inspectable in every case — no
"last occurrence wins", no "active always wins".

### Description comparison (independent dimension)

- SAME: every comparable active occurrence's normalized requirement text
  equals the normalized expected description.
- DIFFERENT: no comparable active occurrence equals it. The confirmed example
  (expected `…2s功能`, actual `…3s功能`) is CONFIGURED + DIFFERENT, never
  MISSING, because function identity is safely established by the exact
  detection phrase.
- NOT_COMPARED with an explicit reason: expected description empty
  (`expected-description-empty`); alias-only hit — an alias establishes
  function identity only and never implies description equality, comparison
  still requires text equality; uncertain association (the two reasons above);
  mixed comparable occurrences (`mixed-comparison-occurrences`); MISSING
  (`nothing-to-compare`); STRUCK_OUT (`evidence-struck`); UNRESOLVED
  (`result-unresolved`).

Detection, resolution and description comparison are independent dimensions:
one block with one occurrence produced CONFIGURED + NOT_COMPARED / SAME /
DIFFERENT for three items differing only in `expectedDescription`. The spike
result model has no score/confidence/similarity field (asserted by test).

### Ambiguous function identity

- Overlapping match spans claimed by **different term texts** across items
  (broad `门控制延时` vs specific `2门控制延时`): both occurrences are flagged
  ambiguous → UNRESOLVED unless clean evidence exists elsewhere (validated:
  an item with one ambiguous and one clean occurrence resolves CONFIGURED and
  keeps both occurrences with their flags).
- **Identical term text** configured on multiple items: the text genuinely
  contains the phrase for each item — no textual interpretation ambiguity — so
  verification resolves each item normally; the duplicate configuration itself
  is a baseline-validation (Task 5) defect to flag at checklist load/edit time.
  This distinction (verification-level vs configuration-level ambiguity) is a
  recorded S6 decision.

### Repeated evidence

- The same qualifying active requirement twice with equal value tokens and
  equal text → CONFIGURED + SAME; both occurrences retained and inspectable.
- A bare mention (no requirement content) plus a valued occurrence →
  CONFIGURED, comparison decided by the comparable occurrence; the blocked
  occurrence stays inspectable with its reason.
- A `2s` occurrence plus a `3s` occurrence for the same function →
  conflicting active key values → UNRESOLVED; neither is dropped or chosen.

### Scale results (measured on the development machine)

Synthetic documents built by `generate_scale_document` (filler paragraphs
approximating engineering prose plus two embedded requirement clauses per
item, hits and classifications known by construction):

| Size | Blocks | Characters | Items | Occurrences | Wall-clock |
|---|---|---|---|---|---|
| small | 200 | 11,100 | 20 | 40 | 0.019 s |
| medium | 800 | 43,940 | 60 | 120 | 0.185 s |
| large | 3,000 | 161,580 | 100 | 200 | 1.087 s |

- Peak transient allocation during `verify()` on the large fixture
  (tracemalloc; the fixture itself was allocated before tracing started):
  133,630 bytes ≈ 0.13 MB.
- These are viability observations with sanity bounds, not performance
  requirements; no production benchmark framework was built and none is implied
  by the spec.
- Conclusion: the simple deterministic approach (per-block normalization +
  substring search) is obviously viable at representative scale.

### Cancellation checkpoints

`verify(items, blocks, cancel_check=...)` evaluates the cancellation flag once
per (item, block) pair — `blocks_n × items_n` checkpoints — before collecting
that pair's evidence. A True flag raises `SpikeCancelled` immediately; no
partial result list is returned, so a cancelled run can never masquerade as a
completed one (validated: a flag turning True after five checkpoints stops at
the sixth). Recommended granularity for Task 3/Task 4: **per (CheckItem,
block)** — fine enough for responsive cancellation at the measured speeds,
coarse enough to add no measurable overhead. No threading, HTTP worker,
multiprocessing or service was introduced in this slice.

### Determinism

Repeated identical inputs produce equal results (dataclass equality across two
full medium-size runs). Occurrences are kept in stable source order (block
index, then raw match span); no set/dict iteration order is visible in
candidate, match or evidence ordering.

### Composition with real ingestion

One synthetic DOCX (`build_requirement_strike`: an active requirement with a
changed value, a partial-strike requirement and a fully struck requirement) was
read by the production Task 2 adapter (`read_document`, COMPLETE coverage) and
verified by the spike rules: CONFIGURED + DIFFERENT / UNRESOLVED
(partial-strike) / STRUCK_OUT observed exactly as labelled. The ingestion layer
needed no changes for S6.

### Remaining limitations

- All fixtures are synthetic (Chinese/ASCII mixed); no sanitized real customer
  documents were validated.
- macOS development machine only; Windows evidence is CI-only, which is not S3.
- The value-token unit list is fixed and small; tokens feed conflict detection
  only, never comparison. Extending the list is a Task 3 data decision, not a
  rule change.
- Clause association is forward-only and boundary-based within one block;
  requirements stated in a different block (e.g. a following table cell) are
  never associated (blocks are not joined) — such cases surface as
  `no-associated-requirement-content` / NOT_COMPARED rather than guesses.
- The scale probe uses synthetic prose, not real document corpus sizes; the
  numbers are viability evidence only.
- Ambiguity detection is span-overlap based; semantic near-duplicates that do
  not overlap textually are intentionally out of scope (no fuzzy matching).

**Task 3 status: unblocked by S6 evidence.** Exact detection semantics, the
normalization allowlist, raw-span traceability, the bounded requirement-span
rule, uncertainty reasons, the strike truth table, conflict and ambiguity
behavior, comparison independence, scale viability, cancellation granularity
and determinism are established above. Task 3 remains its own slice, pending
explicit authorization; this spike does not implement it.

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
