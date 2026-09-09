# Design Requirement Checker — product specification

Status: **DRAFT FOR REVIEW**, 2026-09-10. Production technology is undecided. This phase delivers product definition and a disposable mock prototype only. Decisions marked **proposed** require owner review.

## Problem, users and workflow

Commercial-vehicle electrical/software engineers prepare an order-specific 《设计开发要求》 for the previous-generation 驱动模块 (Drive Module). It combines requirements, functional design and some architecture input for downstream software engineers. Today engineers repeatedly search a Word document for each expected function and manually interpret wording and deletion formatting.

The tool changes the work to: select a local DOCX → check the enabled baseline → review missing, struck-out and changed evidence → inspect expected/actual text and source context → make an engineering judgement. Primary users are the engineers checking an order; baseline maintainers are the same users in the MVP, without roles or collaboration infrastructure.

## Goals and non-goals

Prioritize correctness, explainability, traceability, local/offline operation and faster exception review. Every positive finding must have inspectable evidence. A detection is not engineering acceptance. Missing means not found by the supported checks, not proof that the vehicle lacks the function.

No production implementation, real parser, cloud upload, AI dependency, server, microservices, plugin system, document rewriting, Word automation, team sync, automatic acceptance or technology-specific implementation plan in this phase. The prototype's browser technology does not select the desktop stack.

## Functional requirements

| ID | Requirement | Acceptance evidence in a future MVP |
|---|---|---|
| F01 | Select a local `.docx`, show its name; support drag/drop where practical | Selection and cancellation preserve consistent state; unsupported files produce actionable errors |
| F02 | Explicitly run verification against enabled items | One result per enabled item after a successful complete run; no stale results presented as current |
| F03 | Show CONFIGURED, MISSING or STRUCK_OUT for resolved results | Status is independent of match method and score |
| F04 | Show total/configured/missing/struck-out counts, filters and search | Counts derive from the complete enabled result set; filtering does not change totals |
| F05 | Dense list/detail workspace | Selecting a result shows baseline, evidence, comparison and source context |
| F06 | Maintain checklist data | Add/edit/disable/delete, category, canonical name, description, aliases and notes; stable identifiers |
| F07 | Preserve document structure and formatting | Paragraph/table/run evidence and source coordinates survive ingestion |
| F08 | Deterministic checks | Same document, baseline and rule revision yield equivalent results; no network needed |
| F09 | Explain evidence | Raw text, matching term, transformations and all relevant candidates are inspectable |
| F10 | Keep failures distinct from absence | Failed/incomplete parsing never generates a successful all-missing report |

Checklist edits invalidate current results. Proposed MVP persistence is local baseline data; storage technology is undecided. Keep the baseline snapshot used by a run so later edits do not change the meaning of its results. This is provenance, not a rule-version management product.

## Status and matching models

- **CONFIGURED / ☑ 已配置**: accepted evidence contains an active mention of the function. It does not imply the whole expected description is satisfied.
- **MISSING / ✕ 未配置**: no qualifying evidence found within the successfully checked supported scope.
- **STRUCK_OUT / 已划线（删除线）**: qualifying evidence is fully struck out, under a deletion policy still to be approved.

MatchType: EXACT, NORMALIZED, ALIAS for the initial deterministic engine. FUZZY and similarity belong to V0.2; MANUAL requires a later human-review feature; SEMANTIC is future only. EXACT compares a configured term literally; NORMALIZED compares after a named, conservative normalization; ALIAS records the alias and any normalization used. Prefer exact → normalized → alias for reporting method, but retain other evidence. Ranking must never discard contradictory occurrences.

Do not display a confidence percentage merely because a match is exact. A text match is not a calibrated probability of correctness. If a later algorithm supplies a score, record its kind, scale and algorithm; label textual similarity as similarity. Prototype scores are omitted deliberately.

A description difference is a separate indicator (SAME / DIFFERENT / NOT_COMPARED), not another document status. The prototype shows `2s → 3s` on a CONFIGURED item. A basic expected/actual comparison is MVP; automated enhanced diff and fuzzy matching are V0.2. Do not normalize away numbers, units, negation, timing or control conditions.

### Unresolved evidence without a fourth status

**Proposed safety rule:** CheckResult.status may be unset while resolution is UNRESOLVED; this is a processing/review condition, not an additional CheckStatus value. Never force ambiguous evidence into MISSING. An unresolved count sits beside the three counts, with total = configured + missing + struck-out + unresolved. Owner must approve this contract before implementing production aggregation. The 11 prototype fixtures are deliberately resolved, with 8 configured, 2 missing, 1 struck-out; one configured item has a description difference.

## Checklist and original context

CheckItem contains stable id, unique code, canonical name, category, expectedDescription, aliases, enabled and notes. Alias describes a recognized function name/phrase, not blanket equivalence of every numerical or logical condition. Proposed validation: code and name required, duplicate codes rejected, duplicate names/overlapping aliases flagged for review; missing description permitted with NOT_COMPARED. Hard deletion requires confirmation; disable is reversible.

DocumentLocation identifies a block in a specific document snapshot using body/table/row/cell/paragraph coordinates and nested table paths if needed. UI coordinates are one-based; internal convention must be explicit. Page number is not promised. Show matched block and nearby blocks, label table coordinates and preserve runs so partial strike remains visible. No Word installation or exact-page jump required.

## Edge cases and owner questions

| Case | Proposed handling / decision still needed |
|---|---|
| Repeated function | Retain all evidence; choose a primary display occurrence deterministically, never erase others. Which occurrence has authority? **Q1** |
| Active and struck versions coexist | UNRESOLVED pending precedence policy. Does active always win, or does section/order matter? **Q1** |
| Partial strike | Preserve character/run spans; do not classify by “any strike”. Is deletion of a qualifier enough to remove the function? **Q2** |
| Requirement across paragraphs | Preserve boundaries; proposed V0.1 no automatic joining across blocks. Must this be supported immediately? **Q3** |
| Split runs | Reconstruct within a block while retaining an offset-to-run map |
| Tables / nested tables / merged cells | Preserve physical origin; establish logical versus physical cell coordinates in spike |
| Alias, punctuation, whitespace | Conservative transformations with original text retained; approve exact normalization rules against fixtures **Q4** |
| Numbers/units, 2s vs 3s | Preserve and expose differences; never treat value changes as whitespace equivalence |
| Duplicate items / similar names / ambiguous matches | Validate codes; flag overlapping terms, require match-boundary policy; unresolved candidates are not positive confirmations **Q4** |
| Missing expected description | Proposed permit name-only checking; visibly say description not compared **Q5** |
| Malformed/protected/unsupported Word | Reject or report unsupported scope; no misleading result counts |
| Very large document | Progress/cancel and bounded resources; limits derived by spike, not an invented threshold **Q6** |
| Tracked deletions, headers, footers, text boxes, content controls | Separate from strikethrough. Proposed initial scope: main body paragraphs/tables. Confirm actual document usage; excluded content must be disclosed **Q7** |
| Detection term versus display name | DR-006 illustrates exact detection of `2门控制`, although the display name is `2门控制延时`. The detection term is fixture-only. Should production use name/aliases or a separately editable detection phrase? No implicit extractor is approved. **Q9** |
| Baseline selection for an order | MVP one editable baseline; who owns it and which items apply to each order? **Q8** |

## UX principles

Exception review first; compact desktop controls; persistent selected-document identity; status text plus symbols/color; list and detail visible together; source trace within one selection. Never suggest a mock result was extracted from a selected file. Keyboard access and readable Chinese engineering text take precedence over decoration.

## Production MVP acceptance and validation

1. A supported local DOCX can be checked offline without modifying its bytes.
2. Enabled baseline items produce complete, reproducible results or explicit unresolved conditions under approved policies.
3. Every positive/struck-out classification has raw evidence, formatting, method and retrievable source location.
4. Summary/filter/search agree; selecting an item exposes expected and actual content; missing items have no fabricated evidence.
5. Baseline edits persist locally and require rerunning; invalid input has actionable feedback.
6. Normal/run-split/table/strike fixtures pass approved ground truth, including errors and contradictory evidence.
7. Windows pilot users can install, launch, open and check documents on the agreed managed Windows versions with the agreed privilege level.
8. Historical-document validation compares with engineer-labelled truth. Agree release thresholds before pilot; do not claim precision/recall from mock data.

Future fixture set: normal.docx, table.docx, strikethrough.docx, partial-strikethrough.docx, mixed-runs.docx, alias-match.docx, missing-function.docx, description-difference.docx; add repeated/conflicting matches, inherited-strike with explicit false overrides, nested tables, split paragraphs, tracked revisions, unsupported and oversized documents. Measure feature precision/recall, false positives/negatives, strike accuracy and review-time reduction; report denominators, unsupported scope and unresolved rate separately.

## V0.2 and future

V0.2 candidates: enhanced textual diff, fuzzy candidates with labelled similarity, better internal preview, manual confirmation and report export. Future, only with demonstrated need: semantic/LLM fallback, generated corrections, DOCX editing, Word integration, comments, team sync and rule-version workflows. None determine the MVP architecture today.
