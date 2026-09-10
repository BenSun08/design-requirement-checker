# Technology-neutral domain model

[简体中文版](../docs-zh/domain-model.md)

Status: aligned with owner-confirmed product rules and Python + PySide6 / Qt Widgets. Domain concepts remain UI-independent business concepts; Qt objects belong only in presentation. See product-spec.md for authoritative policies and technical-spikes.md for pending validation.

## Concepts

| Concept | Fields / meaning |
|---|---|
| CheckItem | id (stable identity), code (unique), name (canonical display name), detectionPhrase (required engineer-maintained phrase), category, expectedDescription (optional), aliases[], enabled, notes |
| CheckItemAlias | id, text, notes; belongs to one CheckItem; alternative to detectionPhrase, preserving the exact alias used as evidence; not an automatic assertion of description equivalence |
| Document | id, filename, contentFingerprint, blocks[], ingestionState, supportedScope, coverage (COMPLETE/LIMITED), warnings; represents an immutable input snapshot |
| DocumentBlock | id, type (paragraph/table-cell paragraph), text (raw reconstructed text), runs[], location; no cross-cell concatenation |
| TextRun | text, startOffset, endOffset, effectiveStrike (true/false/unknown), optional formatting metadata and formatting origin; OOXML direct/style values can be retained by adapter |
| DocumentLocation | documentId, blockId, blockType, part, paragraphIndex, optional tableIndex/rowIndex/cellIndex, optional ancestor table path |
| CheckResult | checkItem snapshot, documentId, resolution (RESOLVED/UNRESOLVED), status (CheckStatus or unset), evidence[], primaryEvidenceId, comparisonState, reviewReasons[], ruleRevision |
| CheckStatus | CONFIGURED, MISSING, STRUCK_OUT; describes document evidence, never confidence or approval |
| MatchType | EXACT, NORMALIZED, ALIAS initially; FUZZY, MANUAL, SEMANTIC reserved for separately approved features |
| MatchEvidence | id, document/block identity, locations[], rawText, matchedSpan(s), requirementSpan(s), matchedTerm, aliasId if used, matchType, transformations[], optional score, strikeCoverage, explanation |

A verification run groups document identity, enabled baseline snapshot, rule revision, lifecycle (ready/running/completed/failed/cancelled) and results. A failed/cancelled run is not a completed missing report. This grouping does not require saved run history in the MVP. It includes coverage and coverageReasons independently of completion/failure; COMPLETE is relative to declared MVP scope, not every Word feature. A limited run may have results but must qualify its counts/absence claims with its checked scope.

## Invariants and semantics

- Document text is never replaced by normalized text. A match span refers to original block offsets through a normalization mapping.
- Conceptual offsets count Unicode code points with a half-open [start,end) range. Adapters explicitly convert UTF-16/code-unit offsets; never assume all runtimes count alike.
- Internal coordinates are zero-based; visible coordinates are one-based. Paragraph index is local to its containing body/cell. Locations are stable only for the identified document snapshot, not after editing.
- A cell can contain several paragraph blocks. Nested tables require ancestor coordinates, not a flat table index alone. Merged cells need a tested origin convention before production.
- Every evidence object has a non-empty span and a resolvable location. Multiple candidates are retained. MISSING has no accepted evidence, but may expose rejected candidates separately in a future review experience.
- effectiveStrike is resolved from actual formatting, including inheritance/overrides; unknown formatting is never silently false. Tracked deletion is a separate document feature.
- strikeCoverage is NONE/FULL/PARTIAL/UNKNOWN over the matched requirement span, not over the whole paragraph. FULL over all qualifying occurrences permits STRUCK_OUT; PARTIAL/UNKNOWN, active/deleted coexistence or conflicting key parameters yield UNRESOLVED. Evaluate strike over the associated requirement span too, so a deleted qualifier is not ignored just because the detection phrase is active.
- A RESOLVED result has exactly one CheckStatus; UNRESOLVED has no CheckStatus. This is the confirmed contract, displayed as 待人工核查; it is neither a fourth CheckStatus nor confidence.
- Expected-description comparison is independent of function detection. CONFIGURED + DIFFERENT is valid. Empty expectedDescription gives NOT_COMPARED.
- Optional score = {kind, value, scale, algorithm}; absent is not zero. Exact/alias method does not imply calibrated confidence.
- The sum of resolved status counts plus unresolved count equals enabled items for a completed run. Disabled items are excluded. Filters only change visible rows.
- Baseline changes invalidate displayed results; old evidence must not be attached to changed expected text.

## Detection and evidence boundaries

- name labels the item. detectionPhrase defines the intended detection text, independent of that label; code/name/detectionPhrase are required. No automatic phrase extraction from name.
- EXACT compares detectionPhrase literally; NORMALIZED compares after approved transformations; ALIAS records an explicit alternative phrase and any transformations. A broad related term alone is not evidence of a narrower function.
- matchedSpan(s) identify original detection text. requirementSpan(s) identify the associated requirement used for strike and comparison. For MVP these stay inside one paragraph, including a paragraph inside a cell. S6 must validate association boundaries against fixtures; uncertain association is explicit rather than silently widened to a whole table/paragraph.
- Multiple occurrences are retained in source order. Primary evidence is a display convenience, not authority. Active/deleted coexistence, partial/unknown strike or conflicting key values produce UNRESOLVED before any resolved classification.
- Conservative normalization preserves original offsets, numbers, units, negation and conditions. No cross-paragraph/cross-cell joins. A transformation allowlist is validated, not an implied arbitrary punctuation filter.
- One local baseline, maintained by the engineer; enabled items define the next run. Disabled items remain stored but excluded. No order-template or shared-baseline hierarchy.

## Example

Production illustration (not a change to the historical mock fixture): DR-006 has name `2门控制延时`, detectionPhrase `2门控制增加开关门延时`, expectedDescription `2门控制增加开关门延时2s功能`.

An active paragraph `2门控制增加开关门延时3s功能` contains that detectionPhrase. Result: RESOLVED, CONFIGURED, DIFFERENT, matchType EXACT, no score. Evidence records the detection range and the associated requirement range separately. Location: tableIndex 2, rowIndex 6, cellIndex 1, paragraphIndex 0; UI: 表3 / 行7 / 单元格2 / 段1. Comparison shows `2s → 3s`.

If both active `2s` and `3s` requirements appear, resolution becomes UNRESOLVED with both occurrences. If an active and a fully struck occurrence coexist, the same unresolved rule applies. A single partly struck requirement is also unresolved. A missing expectedDescription gives NOT_COMPARED; an alias hit alone does not claim comparison equality.

The old browser fixture's broader `2门控制` explanation is not an approved production detector and remains documented in prototype-verification.md as a prototype gap.

## Conceptual boundaries

Presentation renders input and evidence. Application/use cases coordinate import, verify and baseline edits. Domain owns matching/classification policies and data invariants. Document/persistence adapters read OOXML and store baseline data. Domain has no UI, Office, network or filesystem dependency. These boundaries can be modules in one process; they do not justify services, generic repositories, plugins or IPC.

## Mapping to the selected stack

Use Python values for domain/application contracts; Qt Widgets and signals adapt these for presentation. DOCX and persistence dependencies stay in adapters. The app is one local desktop process; background work must not update widgets from outside the UI thread. No separate core service, HTTP server, QML or embedded web frontend is planned. Storage format, exact classes and dependency versions remain validation outputs, not new domain entities. All mutable data must be usable by a standard Windows user outside the application installation directory.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
