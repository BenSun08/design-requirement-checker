# Design Requirement Checker — Product Specification

This is the authoritative product specification: what the product is, what
users can do, functional requirements, UX behavior, domain semantics,
supported scope, current limitations and future features. Engineering
invariants live in [constitution.md](constitution.md); how the product is
built lives in [plan.md](plan.md); work status lives in [tasks.md](tasks.md).

## 1. Product overview

Commercial-vehicle electrical/software engineers prepare order-specific
《设计开发要求》 (design & development requirement) documents for drive
modules. Today they repeatedly search a Word document for each expected
function and manually interpret wording and deletion formatting.

The Design Requirement Checker is a **local desktop application** that checks
a selected `.docx` against an engineer-maintained checklist baseline and
presents explainable, deterministic results for human review. It never
decides engineering acceptance — a human reviewer does.

Key properties: local/offline operation, no account, no network, source
document bytes never modified, every positive finding backed by inspectable
evidence.

## 2. Current milestone

**v0.1 Internal Demo** (2026-09-23). These three states are distinct:

```text
Internal Demo Ready  ≠  Production Ready  ≠  Pilot Approved
```

The product is feature-complete for internal demo use. Formal historical
accuracy measurement (Task 6) and clean-machine/no-admin/offline deployment
validation (Task 7) are deferred by the owner; no production or pilot
readiness claim is made. See [tasks.md](tasks.md) for the deferred backlog.

## 3. Users and workflow

Primary users are the engineers checking an order. Baseline maintainers are
the same users in this milestone — there are no roles, permissions or
collaboration features.

The implemented workflow:

```text
maintain baseline (检查项管理)
→ import DOCX (导入 DOCX, file dialog)
→ explicit verification (开始核查, cancellable)
→ review summary counts
→ filter / search
→ inspect expected vs actual text
→ inspect every evidence occurrence
→ inspect reconstructed source context (prev/current/next block)
→ make a human engineering judgement
```

Interface language: simplified Chinese. Documentation: English.

## 4. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| F01 | Import a local `.docx` via file selection; show its name; unsupported files produce actionable errors | Implemented (drag/drop not implemented — see Future Features) |
| F02 | Explicitly run verification against enabled baseline items; one result per enabled item after a complete run; no stale results presented as current | Implemented |
| F03 | Show CONFIGURED / MISSING / STRUCK_OUT for resolved results, independent of match method; UNRESOLVED (待人工核查) as a separate resolution condition with status unset | Implemented |
| F04 | Summary counts (total = configured + missing + struck_out + unresolved; description difference orthogonal), filters (全部/已配置/未配置/已划除/待人工核查/仅异常) and search; filtering never changes totals or recomputes verification | Implemented |
| F05 | Dense list/detail review workspace: selecting a result shows baseline, evidence, comparison and source context | Implemented |
| F06 | Maintain the checklist: add/edit/disable/confirmed-delete; code, name, detection phrase, category, expected description, aliases, notes; stable identifiers | Implemented |
| F07 | Preserve document structure and formatting: paragraph/table/run evidence and source coordinates survive ingestion | Implemented |
| F08 | Deterministic offline checking: same document, baseline and rule revision yield equivalent results; no network needed | Implemented |
| F09 | Explain evidence: raw text, matched term, transformations and all relevant candidates are inspectable | Implemented |
| F10 | Failures distinct from absence: a failed extraction never produces an all-missing report; partial supported-scope coverage is visibly LIMITED | Implemented |

## 5. Domain model

Semantics of the core concepts (exact fields are visible in
`src/design_requirement_checker/domain.py`):

- **CheckItem** — stable `item_id`, unique `code`, canonical `name`, required
  engineer-maintained `detection_phrase`, `category`, optional
  `expected_description`, `aliases[]`, `enabled`, `notes`. The name labels
  the item; the detection phrase is what the matcher searches for. The
  phrase is never auto-derived from the name.
- **CheckItemAlias** — stable `alias_id`, `text`, `notes`; an explicit
  alternative detection phrase; an alias hit never asserts description
  equality.
- **Document** — immutable input snapshot: filename, content fingerprint,
  blocks, ingestion state, `Coverage` (COMPLETE/LIMITED), warnings.
- **DocumentBlock** — paragraph or table-cell paragraph with raw text,
  `TextRun[]` and location; no cross-cell concatenation.
- **TextRun** — raw text with `[start, end)` offsets and
  `effective_strike` = true / false / **unknown** (never silently false).
- **DocumentLocation** — document/part/block coordinates (body or
  table/row/cell/paragraph, nested-table ancestor paths). Internal offsets
  are zero-based; UI coordinates are one-based. Locations are stable only
  for the identified snapshot.
- **CheckResult** — item snapshot, document id, `Resolution`
  (RESOLVED/UNRESOLVED), `CheckStatus` (set only when RESOLVED), evidence
  list, `primary_evidence_id` (initial UI selection aid only),
  `ComparisonState` (SAME/DIFFERENT/NOT_COMPARED), review reasons, rule
  revision.
- **MatchEvidence** — raw text, matched span(s), requirement span(s),
  matched term, alias id, `MatchType` (EXACT/NORMALIZED/ALIAS),
  transformations, strike coverage (NONE/FULL/PARTIAL/UNKNOWN), explanation.
- **MatchType** — FUZZY, MANUAL and SEMANTIC are reserved names for
  separately approved future features, not implemented behavior.

A verification run groups the document identity, enabled baseline snapshot,
rule revision, lifecycle (completed/cancelled/failed) and results. A
cancelled or failed run is never a completed report. Coverage is run-level
and independent of status/resolution.

Status meanings: **CONFIGURED** — accepted evidence contains an active
mention of the function (not proof the whole expected description is
satisfied). **MISSING** — no qualifying evidence found within the
successfully checked supported scope (UI wording: 在已检查范围内未找到匹配
证据; not proof of physical absence). **STRUCK_OUT** — all qualifying
occurrences are fully struck with no active/partial/unknown qualifying
occurrence. **UNRESOLVED (待人工核查)** — partial/unknown strike,
active+struck coexistence, conflicting key values across active occurrences,
or ambiguous function identity; status unset, reasons shown, all evidence
shown.

A single active occurrence with `3s` against an expected `2s` is
CONFIGURED + DIFFERENT. Conflicting active values are UNRESOLVED. Empty
expected description → NOT_COMPARED with visible explanation. No confidence
percentages exist anywhere; a text match is not a calibrated probability.

## 6. Matching semantics

Deterministic detection only. Conservative normalization allowlist (N1
whitespace runs, N2 within-block line breaks, N3 selected full-width
punctuation), raw↔normalized offset traceability, numbers/units/negation/
operators/case preserved distinctly. Forward-only requirement-span
association within one paragraph/cell; uncertain association is explicit.
Strike evaluated over the requirement span. All qualifying occurrences are
retained in source order. Full rules:
[constitution.md §7](constitution.md).

No fuzzy or semantic matching in v0.1.

## 7. Document ingestion scope

Supported: main-body paragraphs and table/cell paragraphs (including
nested/merged tables with ancestor coordinates), hyperlink-contained runs,
effective strike resolved through the full style chain.

Excluded and surfaced as `Coverage.LIMITED` when detected: tracked
revisions, text boxes, content controls, field codes, footnote/endnote
references, smart tags, `altChunk`, nested/invalid hyperlink structures,
header/footer content. Malformed, protected or unreadable files fail
explicitly with categorized errors — never a fabricated all-missing report.
No automatic joining across paragraphs or cells.

## 8. Review workspace UX

Compact desktop window: title/toolbar (导入 DOCX / 开始核查 / 取消核查 /
检查项管理), summary + search strip, QSplitter with a dense result list
(code/name/status/difference hint, ~40%) and a detail pane, persistent
status/footer.

- Detail shows canonical name/category/code, status, match method, expected
  vs actual text, difference (`2s → 3s` style rendering), review reasons,
  a multi-evidence occurrence selector, and reconstructed prev/current/next
  source context with requirement-span highlighting.
- STRUCK_OUT detail renders actual text with a strike line plus a textual
  label; MISSING detail shows the scope-limited message with no fabricated
  location; NOT_COMPARED shows the human-readable reason.
- A persistent 检查范围受限 notice marks LIMITED runs and survives
  filtering/navigation.
- Selection highlight must never resemble engineering approval; no "passed"
  language.
- Keyboard: Up/Down/Enter row navigation, Ctrl+F search focus, dialog focus
  trap with Escape.
- UI lifecycle: EMPTY / IMPORTING / READY / VERIFYING / COMPLETED /
  CANCELLED / FAILED drive action enablement; import and verification run in
  the background with indeterminate progress and cooperative cancel.

## 9. Baseline management

检查项管理 opens a checklist workspace over one local baseline:

- Add/edit dialog: required code (unique), name, detection phrase; optional
  expected description, category, notes; aliases one per line. Stable
  `item_id`/`alias_id` survive edits and restarts.
- Duplicate code rejected; duplicate name and overlapping detection phrases
  flagged for explicit confirmation; empty expected description allowed.
- Disable is reversible; delete requires confirmation. Disabled items are
  persisted but excluded from the next run.
- Saving invalidates current results; rerun required. Baseline edits never
  silently corrupt or discard the saved data (see §10).
- No multi-baseline, customer/order templates, roles or synchronization in
  this version.

## 10. Persistence behavior

One local baseline as UTF-8 JSON (`schemaVersion = 1`) at
`QStandardPaths.AppDataLocation / baseline.json` (on Windows under the
per-user AppData directory — never beside the executable), with
`baseline.json.bak` backup recovery, two-temp-file atomic save and strict
validation. Full contract:
[constitution.md §9](constitution.md).

The application directory can be replaced by a newer build at any time; the
user baseline directory survives replacement.

## 11. Error / recovery behavior

- Import failure: categorized explicit error (file-access / invalid or
  unreadable document / unexpected parser error); state stays consistent;
  never an all-missing success.
- Cancelled verification: no result set shown; cancelled ≠ completed.
- Stale background outcomes (superseded generation or document) are ignored.
- Startup baseline conditions are distinct, explicit banners: normal /
  no-baseline / backup-recovered / corrupt-load-error / unsupported-schema.
  Unsupported schema is distinguished from corruption on load and save.
- Failed saves keep the editor open with the candidate intact and never
  mutate the stored baseline.

## 12. Non-functional requirements

- Deterministic: identical inputs + rule revision → identical results.
- Offline: no network dependency at runtime; no telemetry.
- Source DOCX bytes unchanged (verified by hashing in tests).
- Responsive: import/verification off the UI thread; cancellation honored
  per (item, block) checkpoint.
- Scale: designed for tens–hundreds of items and hundreds–thousands of
  blocks; demonstrated near 3,000 blocks × 100 items at ~1.1 s in the S6
  spike.
- Chinese text first-class: labels, IME input, long descriptions wrap.
- Runs on Windows 10/11 x64 as an ordinary user without administrator
  privileges or installed Python/Qt/Office (target; formal validation
  deferred — see [tasks.md](tasks.md)). Company Python 3.8 installations
  remain untouched; the packaged app carries its own runtime.

## 13. Current limitations

- No measured historical accuracy — no independently labelled corpus has
  been supplied; all metrics NOT MEASURED.
- Formal clean-machine / no-admin / offline Windows deployment matrix
  deferred (owner demo smoke check exists, which is not validation).
- No drag-and-drop import; file-dialog selection only.
- No report export.
- No fuzzy, semantic or LLM matching (by design in v0.1).
- No automatic joining of requirement text across paragraphs or table cells.
- Unsupported Word structures yield LIMITED coverage rather than results.
- No automatic engineering approval — the tool surfaces evidence and
  uncertainty; a human decides.
- No multi-baseline / templates / sync / roles.
- DPI / Chinese-input / long-description formal validation matrices on
  Windows not executed.

## 14. Future Features

Future features are *defined* here, *phased* in
[plan.md §8](plan.md) and *scheduled* in [tasks.md](tasks.md). None may be
implemented without explicit owner authorization; adding one here is the
first required step of the governance rule in
[constitution.md §11](constitution.md).

### V0.2 candidates

Not scheduled, not committed; each needs a product decision first.

- **Report export** — Status: V0.2 candidate. Goal: export verification
  results for engineering review/archive. Constraint: must retain
  evidence/status semantics and must not imply automatic approval.
- **Enhanced textual diff** — Status: V0.2 candidate. Goal: clearer
  expected-vs-actual difference display. Constraint: must not normalize
  away numbers/units/negation; NOT_COMPARED stays honest.
- **Fuzzy candidate matching** — Status: V0.2 candidate. Goal: surface
  near-miss candidates for human review. Constraint: labelled similarity,
  never silent resolution; must not violate the deterministic contract.
- **Manual confirmation / review workflow** — Status: V0.2 candidate.
  Goal: let reviewers record decisions on UNRESOLVED items. Constraint:
  decisions are human provenance, not automatic acceptance.
- **Improved internal preview** — Status: V0.2 candidate. Goal: richer
  source-context rendering. Constraint: still a reconstructed excerpt,
  never a Word-page fidelity claim.
- **Drag-and-drop DOCX import** — Status: V0.2 candidate. Goal: drop a
  file onto the window. Constraint: same validation as file-dialog import.
- **Multiple baselines / customer templates** — Status: V0.2 candidate
  (already deferred from MVP scope). Goal: per-customer or per-order
  checklists. Constraint: stable identity and invalidation semantics must
  survive the selection model.
- **Baseline version / history support** — Status: V0.2 candidate. Goal:
  inspect what changed between baseline revisions. Constraint: run
  provenance must remain explainable.

### Later / exploratory — NOT COMMITTED

Requires an explicit product decision before any planning or
implementation:

- Semantic / LLM fallback matching
- RAG over requirement corpora
- Generated corrections or suggested wording
- DOCX editing / rewriting (the current tool never modifies source files)
- Word integration / automation
- Reviewer comments and team synchronization
- Cloud / shared baselines
- Rule-version management workflows

## 15. Acceptance criteria (implemented baseline)

1. A supported local DOCX can be checked offline without modifying its bytes.
2. Enabled baseline items produce reproducible results or explicit
   unresolved conditions; coverage limits are visible; totals include
   unresolved.
3. Every positive/struck-out classification has raw evidence, formatting,
   method and retrievable source location.
4. Summary/filter/search agree; missing items have no fabricated evidence.
5. Baseline edits persist locally and require rerunning; invalid input has
   actionable feedback.
6. Historical-document validation against engineer-labelled truth remains a
   deferred prerequisite before any production/pilot readiness claim.
