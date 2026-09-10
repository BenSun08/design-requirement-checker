# Prototype verification and scope review

[简体中文版](../docs-zh/prototype-verification.md)

Date: 2026-09-10. Environment: macOS host, Codex in-app browser, localhost static server. This is UI/fixture verification, not real DOCX correctness or Windows qualification.

## Historical observed browser checks (unchanged evidence)

| Check | Observed result |
|---|---|
| Empty import and selected example | File name shown; explicit run action; mock-only disclosure visible |
| Loading | Simulated progress; choose/run/management disabled during generation |
| Complete summary | 11 total / 8 configured / 2 missing / 1 struck-out / 1 independent difference |
| Filters | Configured 8, missing 2; struck-out detail; exception shortcut 4; totals remain 11 |
| Search | `2门` produces 2 items; nonexistent term produces 0 and clears detail |
| Comparison | DR-006 CONFIGURED + EXACT with separate description difference and explicit 2s → 3s |
| Evidence | NORMALIZED and ALIAS explanations; missing has no fabricated location; deleted text retained |
| Checklist CRUD | Added a temporary item, edited name, disabled it; baseline change invalidated results; revised deletion dialog confirmed removal; refresh restored fixtures |
| Keyboard | Arrow Down changed selected evidence; filter focus retained after final fix |
| Unsupported file selection | README.md rejected with `.docx` guidance; run remained disabled |
| Layout | Desktop split workspace inspected; 1024-width DOM scrollWidth=1024; 390-width fallback scrollWidth=390. Screenshots inspected inline, not saved. |

Node syntax checks passed for app.js and mock-data.js. Structural/content checks are recorded by the final task output. No package build is necessary.

## Fixes during review

Replaced browser-native confirm with an in-page delete dialog after native prompt blocked browser automation. Added editor accessible name and focus restoration after regenerating filters/enable toggles/clear-search controls. Alias hit no longer claims description equality. New/materially edited items explicitly disclose that their missing state is a demonstration without fixture evidence. The function-term example was marked fixture-only with a production question (Q9); the owner has now resolved that question by approving a separate detectionPhrase. The historical fixture was not rewritten in this documentation update.

An independent agent reviewed code/spec and confirmed its listed fixes were resolved. This was not an independent screenshot/accessibility audit. Impeccable's optional context engine was unavailable; design guidance was read directly.

## Limits and follow-up

- No real DOCX parsed; no matching precision/recall or formatting accuracy measured.
- Valid DOCX picker and OS file drag/drop handlers are implemented, but an actual DOCX selection/OS drag-drop was not independently exercised. Example import and invalid extension were exercised.
- The optional `file://` launch could not be browser-tool tested because the browser URL policy blocks local-file URLs. It uses relative classic scripts/styles without fetch/modules; direct double-click should be checked by the user in Edge/Chrome. The localhost route was exercised.
- No Windows VM, installer, Chinese Windows IME, screen reader, or packaging test ran. Dialog cancel/Escape and duplicate validation are implemented and code-reviewed; not every branch was browser-exercised.
- No real technical spikes were performed. See technical-spikes.md for proposed experiments.

## Over-design review

Kept: four conceptual boundaries, evidence spans/locations, baseline/run provenance and explicit unresolved policy. These support traceability but do not imply service layers or a saved history product.

Deferred: AI, semantic/fuzzy engines, full document renderer, multi-process core, updater, report export, Word integration, DOCX rewriting, team sync, plugin framework and detailed production scheduling. The former conditional IPC spike is now retired because Python/PySide6 Qt Widgets is selected without a sidecar. Structure-preservation spike is advisory while editing remains future scope.

The owner has approved nullable status plus resolution and explicit detection phrases. Nested/merged table handling remains an extraction-validation detail. These concepts must remain proportionate to the supported documents.

## Addendum after owner confirmation

Production is Python + PySide6 / Qt Widgets on Windows 10/11 x64 for users without administrator/installation privileges. Product confirmation items 1–7 are now recorded in product-spec.md; this addendum is a document review, not a new execution record.

The browser prototype was not modified or rerun by this update. Its verification results above remain historical. It does not yet demonstrate the newly confirmed separate detectionPhrase field, UNRESOLVED result/count/filter, multiple/conflicting evidence, partial-strike policy, coverage warnings or persistent baseline. Its DR-006 fixture explanation uses the broad term `2门控制`; production must use a sufficiently specific engineer-maintained detection phrase. Its session-only management and local-browser launch do not prove Windows/no-admin readiness.

Next evidence comes from the approved-to-plan S1/S2/S3/S6 validations and later Qt UI/Windows tests. No fixture accuracy, no-admin packaging success, current runtime compatibility or production quality has been established by accepting the technology choice.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.

The latest environment confirmation and the Chinese translations are documentation updates only. They do not add Python 3.8 compatibility, offline deployment or first-launch test results to the historical prototype record.
