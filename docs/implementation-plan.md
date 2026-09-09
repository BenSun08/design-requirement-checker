# Design Requirement Checker — Implementation Plan

**Status:** Draft for execution  
**Project:** `BenSun08/design-requirement-checker`  
**Planning basis:** ~8 hours/week, single-developer workflow  
**Production technology:** **TBD — not selected yet**  
**Target:** Deliver a reliable Windows MVP for local `.docx` requirement checking, then validate it on sanitized historical documents.

> This plan starts from the repository's current state: product specification, domain model, UX specification, technology comparison, technical-spike proposals, delivery roadmap, prototype verification, and a clickable mock prototype already exist.

---

## 1. Current state

The project has completed the **product-definition / prototype phase**.

Current assets:

- `docs/product-spec.md`
- `docs/domain-model.md`
- `docs/ux-spec.md`
- `docs/technology-options.md`
- `docs/technical-spikes.md`
- `docs/delivery-roadmap.md`
- `docs/prototype-verification.md`
- `prototype/`

The prototype is intentionally disposable and currently uses mock data only.

The following production capabilities do **not** exist yet:

- real DOCX ingestion;
- deterministic matcher;
- persistent checklist storage;
- production desktop UI;
- Windows installer;
- historical-document validation.

---

## 2. MVP objective

The MVP should allow an engineer to:

1. open a local `.docx` Design & Development Requirements document;
2. run verification against an enabled checklist baseline;
3. classify each item as:
   - `CONFIGURED`
   - `MISSING`
   - `STRUCK_OUT`
   - or an explicit unresolved processing/review condition when evidence is ambiguous;
4. inspect:
   - expected description;
   - actual matched text;
   - match method;
   - source location/context;
   - description differences;
5. manage checklist items locally;
6. run completely offline;
7. install and run as a normal Windows desktop application without development tools.

The MVP must prioritize **correctness, explainability, traceability, and review efficiency** over advanced matching sophistication.

---

## 3. Explicit non-goals for MVP

Do **not** include the following unless a new decision is made:

- LLM / AI semantic checking;
- RAG;
- vector databases;
- cloud services;
- multi-user collaboration;
- automatic DOCX rewriting;
- Microsoft Word COM automation;
- fuzzy matching as a required correctness path;
- plugin systems;
- microservices;
- auto-update infrastructure.

Possible V0.2/Future items are listed later.

---

# 4. Execution gates

Production implementation should not start blindly. The project has three mandatory gates.

## Gate A — Product rule decisions

Before deterministic matching is finalized, resolve the highest-impact product questions in `product-spec.md`, especially:

- repeated occurrences of the same function;
- active and struck-out occurrences coexisting;
- partial strikethrough;
- whether requirements may span multiple paragraphs;
- exact normalization rules;
- missing expected descriptions;
- initial supported Word content scope;
- baseline ownership/applicability;
- whether production needs an explicit detection phrase separate from the display name.

Decisions should be recorded in the product spec or a small ADR.

## Gate B — Technology selection

Before production scaffolding, execute only the minimum technical spikes needed to choose the stack.

At minimum validate:

1. DOCX/OOXML fidelity;
2. source-location traceability;
3. Windows packaging/install reality.

The chosen stack should be recorded explicitly in an ADR, for example:

```text
docs/adr/0001-production-stack.md
```

The ADR should contain:

- decision;
- alternatives considered;
- evidence from spikes;
- main tradeoffs;
- known limitations.

## Gate C — Pilot release

Do not label the application production-ready until:

- fixture tests pass;
- historical-document validation is complete;
- agreed release thresholds are met;
- Windows installation is validated on representative machines.

---

# 5. Development strategy

Use **vertical slices** rather than building all layers separately.

Preferred slice:

```text
Open one real DOCX
→ extract one real block
→ show it in the application
→ test the result
```

Avoid:

```text
Build every repository interface
→ every service abstraction
→ every persistence abstraction
→ UI much later
```

Each week should end with a demonstrable, testable outcome.

---

# 6. Proposed 8-week plan

The schedule assumes approximately **8 focused hours per week**.

This is a target, not a contractual deadline.  
Keep a **1–2 week contingency buffer** if DOCX style inheritance, enterprise Windows packaging, or historical-document ambiguity requires more work.

---

## Week 1 — Decision fixtures + technology evidence

### Goal

Create the minimum evidence required to choose the production stack and lock the MVP checking rules.

### Time budget

| Task | Hours |
|---|---:|
| Prepare synthetic DOCX fixtures | 2 h |
| Prepare 1–3 sanitized representative historical documents | 1 h |
| Execute bounded DOCX fidelity/source-location spike | 3 h |
| Review product-rule questions and record decisions | 1 h |
| Update docs / decision notes | 1 h |

### Deliverables

- synthetic fixtures for:
  - paragraphs;
  - tables;
  - mixed runs;
  - full strikethrough;
  - partial strikethrough;
- sanitized representative sample(s);
- spike notes with actual observed outputs;
- updated unresolved product rules;
- shortlist of production technologies.

### Acceptance criteria

- extracted text is compared against manually labelled ground truth;
- strikethrough is not reduced to a naïve `any run struck => whole item struck`;
- table/paragraph origin can be represented;
- unsupported behavior is documented rather than hidden.

### Stop condition

Do not turn the spike into the production parser.

---

## Week 2 — Select stack + production skeleton + packaging probe

### Goal

Explicitly select the production stack and prove that a minimal Windows application can be packaged.

### Time budget

| Task | Hours |
|---|---:|
| Minimal packaging/install spike for finalist | 3 h |
| Technology decision review | 1 h |
| Create stack ADR | 1 h |
| Create production project skeleton | 2 h |
| CI/lint/test smoke setup | 1 h |

### Deliverables

- `docs/adr/0001-production-stack.md`
- production source directory structure;
- one launchable desktop shell/window;
- one automated smoke test;
- early Windows package/install artifact or documented blocker.

### Acceptance criteria

- stack is explicitly selected;
- no hidden second architecture is introduced;
- project launches locally;
- clean install feasibility is demonstrated or a blocking issue is documented;
- source tree respects:
  - presentation;
  - application/use-case;
  - domain;
  - adapters/infrastructure.

---

## Week 3 — Vertical Slice 1: real DOCX ingestion

### User-visible outcome

Engineer can select one real supported `.docx` and inspect extracted document blocks.

### Scope

Implement:

- local file selection;
- DOCX validation;
- main-body paragraph extraction;
- table-cell extraction;
- run-level text retention;
- strikethrough representation;
- `DocumentLocation`;
- explicit unsupported/error result.

Do not implement matching yet.

### Time budget

| Task | Hours |
|---|---:|
| DOCX adapter implementation | 4 h |
| Internal document model/source map | 1.5 h |
| Minimal UI inspection view | 1 h |
| Fixture tests | 1.5 h |

### Acceptance criteria

For labelled fixtures:

- paragraph text matches expected text;
- table text stays inside the correct cell;
- split runs reconstruct visible block text;
- run formatting remains inspectable;
- source locations are stable within the document snapshot;
- original document is never modified;
- parse failure cannot look like a valid empty document.

### Tests

At minimum:

- `normal.docx`
- `table.docx`
- `mixed-runs.docx`
- `strikethrough.docx`
- `partial-strikethrough.docx`

---

## Week 4 — Vertical Slice 2: deterministic matching engine

### User-visible outcome

A parsed document can be checked against a small baseline and produce explainable results.

### Scope

Implement pure/testable matching functions:

1. exact matching;
2. conservative normalization;
3. alias matching;
4. strike classification under approved policy;
5. evidence retention.

Do not add fuzzy/AI matching.

### Core rule

Never normalize away:

- numbers;
- units;
- negation;
- timing;
- control conditions.

Examples such as `2s` vs `3s` must remain visible differences.

### Deliverables

A `CheckResult` should retain enough evidence to explain:

- what term matched;
- where it matched;
- which transformation was used;
- which source text produced the result;
- whether contradictory candidates also existed.

### Acceptance criteria

- same document + same baseline + same rule revision gives the same result;
- exact / normalized / alias remain separate match types;
- missing means no qualifying evidence was found in successfully processed supported scope;
- ambiguous/conflicting evidence is never silently converted to `MISSING`;
- multiple occurrences are retained according to the approved policy.

### Tests

Add fixtures for:

- alias match;
- missing function;
- repeated occurrences;
- active + struck conflict;
- number/unit difference;
- similar function names.

---

## Week 5 — Vertical Slice 3: end-to-end verification workspace

### User-visible outcome

The core workflow works:

```text
Open document
→ Run check
→ See summary
→ Select exception
→ Inspect expected / actual / source evidence
```

### Scope

Build the production version of:

- document header;
- explicit Run Check action;
- summary counts;
- filters;
- search;
- dense check-result list;
- detail panel;
- expected vs actual view;
- simple text difference view;
- source-context view;
- processing/error states.

### Acceptance criteria

- counts always reflect the complete current result set;
- filters/search do not alter totals;
- checklist/document changes invalidate stale results;
- missing results do not fabricate matched evidence;
- failed parsing is visually distinct from successful `MISSING`;
- UI remains responsive on representative documents.

### UX principle

Optimize for exception review, not dashboard decoration.

---

## Week 6 — Vertical Slice 4: checklist management + persistence

### User-visible outcome

Engineer can maintain the local verification baseline without editing source code.

### Scope

Implement:

- list check items;
- add;
- edit;
- disable;
- delete with confirmation;
- category;
- canonical name;
- expected description;
- aliases;
- notes;
- stable IDs/codes;
- local persistence;
- data reload.

### Data rules

At minimum:

- code required and unique;
- name required;
- overlapping aliases flagged where practical;
- disabled items excluded from new runs;
- edits invalidate current check results.

### Acceptance criteria

- baseline survives application restart;
- production checklist is not embedded as UI fixtures;
- persistence has one clear owner;
- invalid data produces actionable feedback;
- test database/runtime data is separated from source-controlled fixtures.

---

## Week 7 — Historical validation + hardening

### Goal

Determine whether the checker is trustworthy enough for pilot use.

### Dataset

Use a sanitized, engineer-labelled historical corpus.

Prefer representative diversity over a large convenient sample.

Label ground truth before reading checker output where practical.

### Measure

At minimum:

- feature detection precision;
- feature detection recall;
- false positives;
- false negatives;
- strike classification accuracy;
- unresolved rate;
- unsupported-document rate;
- review-time change.

Always report denominators.

### Work

- classify every mismatch;
- determine whether the root cause is:
  - parser;
  - normalization;
  - alias;
  - business rule;
  - bad baseline;
  - unsupported document structure;
  - ambiguous ground truth;
- fix high-impact deterministic issues;
- add every fixed failure as a regression fixture.

### Acceptance criteria

- release thresholds are explicitly agreed;
- no known critical false-positive/false-negative pattern is silently accepted;
- unsupported scopes are visible to the user;
- regression test suite covers discovered failure modes.

---

## Week 8 — Windows packaging + pilot release candidate

### User-visible outcome

A pilot engineer can install the application and check local documents without a development environment.

### Scope

Validate:

- Windows installer;
- standard-user behavior;
- application launch;
- Chinese paths;
- long filenames where relevant;
- DPI scaling;
- clean uninstall;
- upgrade behavior;
- baseline-data preservation;
- endpoint-protection behavior;
- crash/error logging location.

### Deliverables

- release candidate installer;
- release notes;
- known limitations;
- pilot checklist;
- rollback/uninstall instructions;
- MVP version tag, e.g. `v0.1.0-rc.1`.

### Acceptance criteria

- install/launch/check/uninstall works on agreed Windows environment;
- no Python/Node/.NET/etc. development environment is required on the end-user machine unless explicitly part of the chosen deployment model;
- local baseline data has a documented storage location and preservation policy;
- known limitations are published;
- pilot feedback path is defined.

---

# 7. Weekly workflow

For an ~8 h/week solo project, keep process lightweight.

Recommended weekly cycle:

```text
1. Pick one vertical slice
2. Confirm acceptance criteria
3. Implement
4. Add/adjust tests
5. Run full checks
6. Update relevant docs
7. Open PR
8. Review and merge
```

Avoid parallel feature branches unless necessary.

---

# 8. Branch and PR convention

Suggested branch naming:

```text
feat/docx-ingestion
feat/deterministic-matching
feat/check-workspace
feat/checklist-persistence
test/historical-validation
build/windows-packaging
```

Keep each PR centered on one user-visible slice.

Each PR description should contain:

```markdown
## Goal

## User-visible outcome

## Key implementation decisions

## Tests

## Known limitations

## Follow-up
```

Large architecture changes should include/update an ADR.

---

# 9. Definition of Done for an implementation slice

A slice is not complete because code exists.

It is complete when:

- acceptance criteria are met;
- automated tests cover the main behavior;
- failures return explicit errors;
- no known mock behavior is presented as real analysis;
- docs are updated when behavior changed;
- full project checks pass;
- the slice can be demonstrated from the user workflow.

---

# 10. Testing strategy

## Unit tests

Focus heavily on:

- normalization;
- exact matching;
- alias matching;
- strike policy;
- evidence ranking;
- source-span mapping.

## Fixture-based DOCX tests

Maintain small synthetic documents that isolate one behavior.

Recommended fixture set:

```text
normal.docx
table.docx
strikethrough.docx
partial-strikethrough.docx
mixed-runs.docx
alias-match.docx
missing-function.docx
description-difference.docx
repeated-conflicting.docx
nested-table.docx
tracked-revision.docx
malformed.docx
```

Synthetic fixtures may be version-controlled.

Real company/order documents should only be added if they are explicitly approved and sanitized.

## End-to-end tests

Keep E2E scope small:

1. launch app;
2. select fixture;
3. run check;
4. verify summary;
5. open one result;
6. edit one checklist item;
7. restart and confirm persistence.

---

# 11. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Word formatting inheritance is more complex than direct run formatting | High | Prove with S1; preserve unknown states; add style fixtures |
| Partial strikethrough has ambiguous business meaning | High | Owner-defined rule; keep spans/evidence; support unresolved outcome |
| Function phrases produce false positives | High | Conservative matching; explicit aliases; boundary policy; historical validation |
| Real documents use unsupported structures | High | Inspect representative corpus early; disclose supported scope |
| Technology choice packages poorly on managed Windows | High | Packaging spike before full implementation |
| Checklist baseline is incorrect/outdated | High | Baseline is editable data; distinguish checker correctness from baseline correctness |
| UI reports stale results after baseline edits | Medium | Invalidate runs when document/baseline changes |
| Large documents freeze UI | Medium | Measure representative sizes; background/cancellable work if required |
| Real work documents leak into GitHub | High | Use sanitized/synthetic fixtures; `.gitignore`; repository/process review |
| Scope expands into AI/document editing too early | Medium | Keep MVP non-goals explicit; new decision required for V0.2/Future |

---

# 12. MVP release criteria

Do not release `v0.1.0` as a normal pilot build until all of the following are true:

- [ ] production stack explicitly selected and documented;
- [ ] supported DOCX scope documented;
- [ ] fixture suite passes;
- [ ] deterministic status/matching policies approved;
- [ ] source evidence is inspectable for positive/struck results;
- [ ] parse failures cannot appear as all-missing results;
- [ ] checklist persistence works;
- [ ] historical validation completed;
- [ ] release thresholds agreed;
- [ ] Windows installer tested;
- [ ] known limitations documented;
- [ ] private/company documents are not unintentionally included in the public repository.

---

# 13. V0.2 candidate backlog

Only prioritize these after MVP pilot feedback.

Possible V0.2 features:

- enhanced textual diff;
- fuzzy candidate matching;
- labelled similarity score;
- better internal document preview;
- manual result confirmation;
- verification report export;
- additional DOCX structures;
- better baseline import/export.

Each candidate should answer:

> Does this reduce engineering review effort or a measured failure mode?

---

# 14. Future — separate product decisions required

Do not treat these as scheduled work yet:

- semantic/LLM-assisted review;
- RAG;
- corrected DOCX generation;
- direct DOCX editing;
- Microsoft Word integration;
- comments/annotations;
- shared/team baseline;
- baseline version workflows;
- cloud synchronization;
- auto-update infrastructure.

---

# 15. Suggested milestone mapping

| Milestone | Target week |
|---|---:|
| Technology/product gates resolved | Week 2 |
| Real DOCX ingestion | Week 3 |
| Deterministic verification | Week 4 |
| End-to-end checker | Week 5 |
| Checklist persistence | Week 6 |
| Historical validation | Week 7 |
| Windows release candidate | Week 8 |

If Week 1–2 spikes expose substantial DOCX or packaging complexity, re-plan immediately rather than compressing validation and testing.

---

# 16. First next action

Before implementing production code:

1. review and answer the unresolved product questions in `docs/product-spec.md`;
2. create synthetic DOCX fixtures;
3. obtain sanitized representative documents;
4. run the highest-value technology spikes;
5. explicitly select the production stack.

Only after that should Week 2 production scaffolding begin.
