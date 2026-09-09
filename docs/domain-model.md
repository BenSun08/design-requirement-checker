# Technology-neutral domain model

Status: DRAFT FOR REVIEW. See product-spec.md for policy questions. These are business concepts, not database tables or framework classes.

## Concepts

| Concept | Fields / meaning |
|---|---|
| CheckItem | id (stable identity), code (unique), name (canonical function name), category, expectedDescription (optional), aliases[], enabled, notes |
| CheckItemAlias | id, text, notes; belongs to one CheckItem; preserves the specific term used as evidence |
| Document | id, filename, contentFingerprint, blocks[], ingestionState, supportedScope, warnings; represents an immutable input snapshot |
| DocumentBlock | id, type (paragraph/table-cell paragraph), text (raw reconstructed text), runs[], location; no cross-cell concatenation |
| TextRun | text, startOffset, endOffset, effectiveStrike (true/false/unknown), optional formatting metadata and formatting origin; OOXML direct/style values can be retained by adapter |
| DocumentLocation | documentId, blockId, blockType, part, paragraphIndex, optional tableIndex/rowIndex/cellIndex, optional ancestor table path |
| CheckResult | checkItem snapshot, documentId, resolution (RESOLVED/UNRESOLVED), status (CheckStatus or unset), evidence[], primaryEvidenceId, comparisonState, reviewReasons[], ruleRevision |
| CheckStatus | CONFIGURED, MISSING, STRUCK_OUT; describes document evidence, never confidence or approval |
| MatchType | EXACT, NORMALIZED, ALIAS initially; FUZZY, MANUAL, SEMANTIC reserved for separately approved features |
| MatchEvidence | id, document/block identity, locations[], rawText, matchedSpan(s), matchedTerm, aliasId if used, matchType, transformations[], optional score, strikeCoverage, explanation |

A verification run groups document identity, enabled baseline snapshot, rule revision, lifecycle (ready/running/completed/failed/cancelled) and results. A failed/cancelled run is not a completed missing report. This grouping does not require saved run history in the MVP.

## Invariants and semantics

- Document text is never replaced by normalized text. A match span refers to original block offsets through a normalization mapping.
- Conceptual offsets count Unicode code points with a half-open [start,end) range. Adapters explicitly convert UTF-16/code-unit offsets; never assume all runtimes count alike.
- Internal coordinates are zero-based; visible coordinates are one-based. Paragraph index is local to its containing body/cell. Locations are stable only for the identified document snapshot, not after editing.
- A cell can contain several paragraph blocks. Nested tables require ancestor coordinates, not a flat table index alone. Merged cells need a tested origin convention before production.
- Every evidence object has a non-empty span and a resolvable location. Multiple candidates are retained. MISSING has no accepted evidence, but may expose rejected candidates separately in a future review experience.
- effectiveStrike is resolved from actual formatting, including inheritance/overrides; unknown formatting is never silently false. Tracked deletion is a separate document feature.
- strikeCoverage is NONE/FULL/PARTIAL/UNKNOWN over the matched requirement span, not over the whole paragraph. Classification of PARTIAL and conflicting candidates is an owner decision.
- A RESOLVED result has exactly one CheckStatus; UNRESOLVED has no CheckStatus. This proposal is a review gate, not a new silently approved fourth status.
- Expected-description comparison is independent of function detection. CONFIGURED + DIFFERENT is valid. Empty expectedDescription gives NOT_COMPARED.
- Optional score = {kind, value, scale, algorithm}; absent is not zero. Exact/alias method does not imply calibrated confidence.
- The sum of resolved status counts plus unresolved count equals enabled items for a completed run. Disabled items are excluded. Filters only change visible rows.
- Baseline changes invalidate displayed results; old evidence must not be attached to changed expected text.

## Example

Check item DR-006: name `2门控制延时`, expectedDescription `2门控制增加开关门延时2s功能`.

Result: resolution RESOLVED, status CONFIGURED, comparisonState DIFFERENT.
Evidence: EXACT match on fixture-only illustrative function term `2门控制`, rawText `2门控制增加开关门延时3s功能`, strikeCoverage NONE, score absent. Location: tableIndex 2, rowIndex 6, cellIndex 1, paragraphIndex 0; UI: 表3 / 行7 / 单元格2 / 段1. Comparison makes `2s → 3s` visible. EXACT concerns the function term, not equality of the descriptions. This term is currently fixture-only: CheckItem does not yet define its storage or derivation. Owner question Q9: should detection use canonical name/aliases, an explicit detection phrase, or a separately defined rule? Do not infer an automatic term extractor or introduce one during this phase.

## Conceptual boundaries

Presentation renders input and evidence. Application/use cases coordinate import, verify and baseline edits. Domain owns matching/classification policies and data invariants. Document/persistence adapters read OOXML and store baseline data. Domain has no UI, Office, network or filesystem dependency. These boundaries can be modules in one process; they do not justify services, generic repositories, plugins or IPC.
