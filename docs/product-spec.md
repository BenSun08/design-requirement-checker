# Design Requirement Checker — product specification

[简体中文版](../docs-zh/product-spec.md)

Status: **TECHNOLOGY AND PRODUCT RULES CONFIRMED BY OWNER**. Production: **Python + PySide6 / Qt Widgets**. Supported deployment target: **Windows 10 and Windows 11, x64, users without administrator/installation privileges**. This revision records the owner confirmation following the 2026-09-10 prototype baseline. Updating these documents does not authorize production code or spike execution. Technical validation remains pending.

## Problem, users and workflow

Commercial-vehicle electrical/software engineers prepare an order-specific 《设计开发要求》 for the previous-generation 驱动模块 (Drive Module). It combines requirements, functional design and some architecture input for downstream software engineers. Today engineers repeatedly search a Word document for each expected function and manually interpret wording and deletion formatting.

The tool changes the work to: select a local DOCX → check the enabled baseline → review missing, struck-out and changed evidence → inspect expected/actual text and source context → make an engineering judgement. Primary users are the engineers checking an order; baseline maintainers are the same users in the MVP, without roles or collaboration infrastructure.

## Goals and non-goals

Prioritize correctness, explainability, traceability, local/offline operation and faster exception review. Every positive finding must have inspectable evidence. A detection is not engineering acceptance. Missing means not found by the supported checks, not proof that the vehicle lacks the function.

This change is documentation-only: no production implementation or real parser is created. The existing implementation plan now follows the selected Python/PySide6 stack and remains subject to execution authorization. MVP excludes cloud upload, AI dependency, server, microservices, plugin system, document rewriting, Word automation, team sync and automatic engineering acceptance. The browser prototype remains a historical interaction reference, not production UI code.

## Functional requirements

| ID | Requirement | Acceptance evidence in a future MVP |
|---|---|---|
| F01 | Select a local `.docx`, show its name; support drag/drop where practical | Selection and cancellation preserve consistent state; unsupported files produce actionable errors |
| F02 | Explicitly run verification against enabled items | One result per enabled item after a successful complete run; no stale results presented as current |
| F03 | Show CONFIGURED, MISSING or STRUCK_OUT for resolved results | Status is independent of match method and score |
| F04 | Show total/configured/missing/struck-out/unresolved counts, filters and search | Counts derive from the complete enabled result set; filtering does not change totals |
| F05 | Dense list/detail workspace | Selecting a result shows baseline, evidence, comparison and source context |
| F06 | Maintain checklist data | Add/edit/disable/delete, category, canonical display name, detection phrase, description, aliases and notes; stable identifiers |
| F07 | Preserve document structure and formatting | Paragraph/table/run evidence and source coordinates survive ingestion |
| F08 | Deterministic checks | Same document, baseline and rule revision yield equivalent results; no network needed |
| F09 | Explain evidence | Raw text, matching term, transformations and all relevant candidates are inspectable |
| F10 | Keep failures distinct from absence | Failed extraction never generates a successful all-missing report; partial supported-scope coverage is visibly LIMITED |

Checklist edits invalidate current results. MVP has one local editable baseline, maintained by the using engineer. Enabled/disabled items define applicability for the current order; multiple baselines, order templates and synchronization are excluded. The persistence adapter/format will be chosen after a small validation; the data is not embedded in production source. Keep the baseline snapshot used by a run so later edits do not change the meaning of its results. This is provenance, not a rule-version management product.

## Status and matching models

- **CONFIGURED / ☑ 已配置**: accepted evidence contains an active mention of the function. It does not imply the whole expected description is satisfied.
- **MISSING / ✕ 未配置**: no qualifying evidence found within the successfully checked supported scope.
- **STRUCK_OUT / 已划线（删除线）**: all qualifying occurrences are fully struck out and there is no active, partially struck or formatting-unknown qualifying occurrence.

MatchType: EXACT, NORMALIZED, ALIAS for the initial deterministic engine. FUZZY and similarity belong to V0.2; MANUAL requires a later human-review feature; SEMANTIC is future only. EXACT compares the explicitly configured detectionPhrase literally; NORMALIZED compares after a named, conservative normalization; ALIAS records the alias and any normalization used. Prefer exact → normalized → alias for reporting method, but retain other evidence. Ranking must never discard contradictory occurrences.

Do not display a confidence percentage merely because a match is exact. A text match is not a calibrated probability of correctness. If a later algorithm supplies a score, record its kind, scale and algorithm; label textual similarity as similarity. Prototype scores are omitted deliberately.

A description difference is a separate indicator (SAME / DIFFERENT / NOT_COMPARED), not another document status. The prototype shows `2s → 3s` on a CONFIGURED item. A basic expected/actual comparison is MVP; automated enhanced diff and fuzzy matching are V0.2. Do not normalize away numbers, units, negation, timing or control conditions.

### Unresolved evidence without a fourth status

**Confirmed safety rule:** CheckResult.status may be unset while resolution is UNRESOLVED; this is a processing/review condition, not an additional CheckStatus value. Never force ambiguous evidence into MISSING. An unresolved count sits beside the three counts, with total = configured + missing + struck-out + unresolved. This contract is approved: show UNRESOLVED as “待人工核查”, separately from confidence and the three document statuses. The 11 prototype fixtures are deliberately resolved, with 8 configured, 2 missing, 1 struck-out; one configured item has a description difference.

## Checklist and original context

CheckItem contains stable id, unique code, canonical display name, detectionPhrase, category, expectedDescription, aliases, enabled and notes. detectionPhrase is required and explicitly maintained by an engineer; aliases are alternative detection phrases. Never derive detectionPhrase automatically from the display name. A broad phrase such as `2门控制` does not by itself establish the narrower delay function. Alias describes a recognized function name/phrase, not blanket equivalence of every numerical or logical condition. Validation: code, name and detectionPhrase required, duplicate codes rejected, duplicate names/overlapping aliases flagged for review; missing description permitted with NOT_COMPARED. Alias detection alone never establishes expected-description equality. Hard deletion requires confirmation; disable is reversible.

DocumentLocation identifies a block in a specific document snapshot using body/table/row/cell/paragraph coordinates and nested table paths if needed. UI coordinates are one-based; internal convention must be explicit. Page number is not promised. Show matched block and nearby blocks, label table coordinates and preserve runs so partial strike remains visible. No Word installation or exact-page jump required.

## Confirmed rules and remaining validation

The owner accepted the proposed product rules (confirmation items 1–7). The following table replaces the earlier Q1–Q9 questions; only empirical/technical details remain open.

| Case / previous question | Confirmed behavior |
|---|---|
| Repeated occurrences / Q1 | Retain every qualifying occurrence. Consistent active occurrences yield CONFIGURED. Conflicting key parameters across active occurrences yield UNRESOLVED. Choose a primary display occurrence by stable document order; it has no greater authority than other evidence. |
| Active and struck occurrences coexist / Q1 | UNRESOLVED; neither last occurrence nor active text silently wins. Show all conflicting evidence. |
| Partial strike / Q2 | When a qualifying occurrence has partial deletion within the matched function or associated requirement content, UNRESOLVED. Preserve exact ranges; never classify a whole block by “any run struck”. Unknown effective formatting is also unresolved. |
| Resolution / former proposed contract | Three CheckStatus values remain unchanged. UNRESOLVED is a separate resolution condition with status unset and its own count/filter. No automatic manual-acceptance workflow in MVP. |
| Across paragraphs / Q3 | No automatic joining across paragraphs or cells in MVP. Join runs only within a paragraph and retain the source map. Explain this scope limit to users. |
| Table and cell paragraphs | Include body/table paragraphs, retaining cell origin. Nested/merged table traversal needs S2 validation. If a structure cannot be covered reliably, disclose a limited run rather than pretending it was checked. |
| Normalization / Q4 | Conservative whitespace, within-block line-break and explicitly equivalent Chinese/English punctuation handling. Retain numbers, units, negation and conditions. A reviewed transformation allowlist and offset mapping are S6 outputs; no general punctuation stripping or numeric/unit equivalence assumed. |
| Similar names, duplicate items, aliases / Q4 | Duplicate codes rejected; duplicate names/overlapping phrases flagged. A candidate that cannot reliably establish the configured function is UNRESOLVED, not a positive finding. No fuzzy matching in MVP. |
| Missing expected description / Q5 | Permitted. Check function presence only; comparisonState=NOT_COMPARED with visible explanation. Alias hit alone is not description equality. |
| Very large document / Q6 | Responsive progress/cancel and bounded resources required. Limits come from measurements of representative inputs. |
| Supported parts / Q7 | Main body paragraphs and tables/cell paragraphs. No automatic cross-paragraph matching. Headers/footers, text boxes, tracked revisions and other unsupported content must produce an explicit scope limitation when present/detected. Tracked deletion is distinct from strike formatting. |
| Detection term / Q9 | Separate required detectionPhrase from display name; aliases support alternative phrases. Engineer-configured, no automatic term extractor. Match establishes only the explicitly defined function identity. |
| Baseline ownership/applicability / Q8 | One local baseline maintained by the using engineer. Enable/disable selects applicability. Multiple baselines, customer/order/vehicle templates and synchronization deferred. |
| Malformed, protected or unsupported files | Explicit failure/unsupported outcome. No fabricated all-missing successful report. |

### Aggregate classification and comparison

First collect all qualifying evidence without discarding contradictory candidates. Partial/unknown strike, active/deleted coexistence, conflicting key parameters, or ambiguous function identity take precedence and yield UNRESOLVED with reasons. Otherwise active qualifying evidence yields CONFIGURED; exclusively fully struck evidence yields STRUCK_OUT; no qualifying evidence in successfully checked scope yields MISSING. All evidence remains inspectable.

A single active occurrence with `3s` against an expected `2s` remains CONFIGURED + DIFFERENT if its function identity is established. Multiple active occurrences with contradictory key values (such as `2s` and `3s`) are UNRESOLVED instead. Automated identification of associated requirement spans and key parameters needs fixture validation under S6; do not claim arbitrary natural-language understanding. Unsupported or uncertain comparison yields NOT_COMPARED, never presumed SAME.

### Coverage and Windows deployment

Run coverage is COMPLETE or LIMITED, separate from run lifecycle, resolution and CheckStatus. COMPLETE means all content within the declared MVP scope was processed; it never claims support for excluded Word features. When excluded/unsupported structures are detected, show LIMITED with reasons. MISSING in a limited run means not found in the checked scope, not absence from the entire file. If safe extraction is impossible, fail the run instead.

The application must run offline on Windows 10/11 x64 as an ordinary user, without Python, Qt, Office or other development tools installed by that user. Users have no administrator/installation privileges. Validate a portable extracted distribution first; a per-user installer is an alternative only if organizational policy permits it without elevation. Do not depend on Program Files, machine-wide registry changes or UAC elevation. Store mutable baseline/settings/logs in a user-writable location, separate from program files. “Portable” does not mean exempt from enterprise execution policy; blocked execution is an explicit IT dependency, not grounds to bypass controls.

Exact Windows builds, Qt/Python versions and IT execution restrictions remain deployment validation inputs. Initial distribution, extraction/installation, first launch and document checking must be completely offline. No-admin use is mandatory regardless of deployment format.

## UX principles

Exception review first; compact desktop controls; persistent selected-document identity; status text plus symbols/color; list and detail visible together; source trace within one selection. Never suggest a mock result was extracted from a selected file. Keyboard access and readable Chinese engineering text take precedence over decoration.

## Production MVP acceptance and validation

1. A supported local DOCX can be checked offline without modifying its bytes.
2. Enabled baseline items produce reproducible results or explicit unresolved conditions under the confirmed rules; coverage limits are visible and summary totals include unresolved items.
3. Every positive/struck-out classification has raw evidence, formatting, method and retrievable source location.
4. Summary/filter/search agree; selecting an item exposes expected and actual content; missing items have no fabricated evidence.
5. Baseline edits persist locally and require rerunning; invalid input has actionable feedback.
6. Normal/run-split/table/strike fixtures pass approved ground truth, including errors and contradictory evidence.
7. Windows pilot users can deploy using the permitted non-elevated format, launch, open and check documents on both Windows 10 and Windows 11 x64 with no administrator/installation privileges; the chosen distribution must bundle its runtime and preserve user baseline data during replacement/update.
8. Historical-document validation compares with engineer-labelled truth. Agree release thresholds before pilot; do not claim precision/recall from mock data.

Future fixture set: normal.docx, table.docx, strikethrough.docx, partial-strikethrough.docx, mixed-runs.docx, alias-match.docx, missing-function.docx, description-difference.docx; add active/deleted coexistence, conflicting active values, unknown formatting, broad detection terms, coverage limitations, no-admin deployment, repeated/conflicting matches, inherited-strike with explicit false overrides, nested tables, split paragraphs, tracked revisions, unsupported and oversized documents. Measure feature precision/recall, false positives/negatives, strike accuracy and review-time reduction; report denominators, unsupported scope and unresolved rate separately.

## V0.2 and future

V0.2 candidates: enhanced textual diff, fuzzy candidates with labelled similarity, better internal preview, manual confirmation and report export. Future, only with demonstrated need: semantic/LLM fallback, generated corrections, DOCX editing, Word integration, comments, team sync and rule-version workflows. None determine the MVP architecture today.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
