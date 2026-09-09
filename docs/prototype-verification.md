# Prototype verification and scope review

Date: 2026-09-10. Environment: macOS host, Codex in-app browser, localhost static server. This is UI/fixture verification, not real DOCX correctness or Windows qualification.

## Observed browser checks

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

Replaced browser-native confirm with an in-page delete dialog after native prompt blocked browser automation. Added editor accessible name and focus restoration after regenerating filters/enable toggles/clear-search controls. Alias hit no longer claims description equality. New/materially edited items explicitly disclose that their missing state is a demonstration without fixture evidence. The function-term example is marked fixture-only with a production question (Q9).

An independent agent reviewed code/spec and confirmed its listed fixes were resolved. This was not an independent screenshot/accessibility audit. Impeccable's optional context engine was unavailable; design guidance was read directly.

## Limits and follow-up

- No real DOCX parsed; no matching precision/recall or formatting accuracy measured.
- Valid DOCX picker and OS file drag/drop handlers are implemented, but an actual DOCX selection/OS drag-drop was not independently exercised. Example import and invalid extension were exercised.
- The optional `file://` launch could not be browser-tool tested because the browser URL policy blocks local-file URLs. It uses relative classic scripts/styles without fetch/modules; direct double-click should be checked by the user in Edge/Chrome. The localhost route was exercised.
- No Windows VM, installer, Chinese Windows IME, screen reader, or packaging test ran. Dialog cancel/Escape and duplicate validation are implemented and code-reviewed; not every branch was browser-exercised.
- No real technical spikes were performed. See technical-spikes.md for proposed experiments.

## Over-design review

Kept: four conceptual boundaries, evidence spans/locations, baseline/run provenance and explicit unresolved policy. These support traceability but do not imply service layers or a saved history product.

Deferred: AI, semantic/fuzzy engines, full document renderer, multi-process core, updater, report export, Word integration, DOCX rewriting, team sync, plugin framework and detailed production scheduling. Conditional IPC spike runs only if a finalist actually needs it. Structure-preservation spike is advisory while editing remains future scope.

Potential complexity needing owner review: nullable status plus resolution, nested-table coordinates and explicit detection phrases. They should remain proportionate to real documents and not become a generalized document platform.
