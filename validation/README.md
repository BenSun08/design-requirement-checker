# Task 6 — Historical Validation

Tooling that measures how the current deterministic checker performs against
**independently labelled historical engineering documents**. This directory is
evaluation tooling, not product runtime code; nothing under `src/` may import
from here.

## The ground-truth separation rule (prominent, non-negotiable)

Required workflow:

```text
historical/sanitized DOCX
    ↓  human reads the document, decides the truth WITHOUT running the checker
independent ground-truth label (validation/labels/<doc-id>.json)
    ↓
run current checker (production application path)
    ↓
prediction
    ↓
compare (scripts/run_historical_validation.py)
```

Forbidden workflow:

```text
run checker → inspect result → copy result into expected label
```

Copying checker output into labels creates circular validation: the checker
would be graded against itself and the measurement would be meaningless.
Every label must be established by a human (or an approved independent
process) reading the source document.

**Synthetic unit-test fixtures are NOT historical validation evidence.** They
prove implementation consistency only. A label file whose document is
synthetic must carry `"sanitizationState": "synthetic"` and
`"includeInMetrics": false` with an exclusion reason, and must never be
presented as a historical measurement.

## Layout

```text
validation/
  README.md                  this file
  schema.py                  versioned ground-truth contract + strict parser
  manifest.example.json      template manifest (safe to commit)
  manifest.json              real manifest — created locally when a corpus exists
  labels/
    <document-id>.json       one independent label file per document
  reports/
    latest-results.json      machine-readable evaluator output (gitignored)
    task6-validation-report.md
  corpus-local/              sanitized DOCX kept outside Git (gitignored)
scripts/
  run_historical_validation.py
tests/
  test_validation_manifest.py
  test_validation_metrics.py
```

## Anonymization / sanitization

- Never commit raw confidential customer/company documents. Only sanitized
  copies explicitly approved for the repository, or documents referenced by
  local paths that stay gitignored (`validation/corpus-local/`).
- Use stable anonymous IDs (`hist-001`, `hist-002`) in manifests and labels.
  Never record customer names, order numbers, VINs or personal information.
- Reports reference cases only by `documentId / itemId`; they must not embed
  confidential source text.

## Schema (schemaVersion 1)

Machine tokens are uppercase and stable; presentation-only Chinese labels
never enter metric logic.

Manifest (`manifest.json` / `manifest.example.json`):

| Field | Meaning |
|---|---|
| `schemaVersion` | must be `1` |
| `baselineFile` | production baseline JSON (same format as `baseline_store.py`), path relative to the manifest |
| `documents[]` | `documentId`, `documentFile`, `labelsFile`, optional `notes` |

Per-document labels (`labels/<document-id>.json`):

| Field | Meaning |
|---|---|
| `schemaVersion` | must be `1` |
| `documentId` | anonymous ID, must match the manifest entry |
| `documentFile` | DOCX path relative to the manifest |
| `labelledBy` | provenance of the independent labels (person/process, never the checker) |
| `sanitizationState` | `sanitized` / `synthetic` / `local-only` |
| `labels[]` | one entry per (document, CheckItem) pair — see below |

Per-item label:

| Field | Tokens / rule |
|---|---|
| `itemId` | stable CheckItem id from the baseline |
| `expectedResolution` | `RESOLVED` / `UNRESOLVED` |
| `expectedStatus` | `CONFIGURED` / `MISSING` / `STRUCK_OUT`; required iff resolution is `RESOLVED`, forbidden iff `UNRESOLVED` |
| `expectedComparison` | optional `SAME` / `DIFFERENT` / `NOT_COMPARED`; omit when not independently labelable |
| `expectedStrike` | optional `NONE` / `FULL` / `PARTIAL` / `UNKNOWN` |
| `expectedCoverage` | optional `COMPLETE` / `LIMITED` |
| `includeInMetrics` | boolean, default `true`; `false` requires `exclusionReason` |
| `exclusionReason` | required when excluded from metrics |
| `notes` | rationale; free text (Unicode allowed) |

`schema.py` rejects: unknown tokens, `UNRESOLVED` + status, `RESOLVED` without
status, missing identities, exclusion without reason, duplicate `itemId`
inside one document, duplicate `(documentId, itemId)` across the manifest,
manifest/labels `documentId` disagreement, and unsupported schema versions.
It validates ground truth independently — production `CheckResult`
constructors are not used as the label validator.

## Preparing a corpus (workflow when real documents become available)

**Current status: BLOCKED — no real/sanitized historical corpus has been
supplied to this repository.** All evidence in `tests/` is synthetic and
proves implementation consistency only; none of it counts as historical
validation. Until sanitized documents and independent labels are supplied,
Task 6 metrics remain NOT MEASURED.

To unblock, follow this workflow:

1. Obtain historical `设计开发要求` DOCX files.
2. **Sanitize** each document (or keep it local-only):
   - remove/replace customer names, order numbers, vehicle VINs, project
     codes and personal information;
   - keep the engineering wording, tables and strike formatting intact —
     that is what is being validated;
   - if the document cannot be safely sanitized, place it in
     `validation/corpus-local/` (gitignored) and set
     `"sanitizationState": "local-only"`; never commit it.
3. Assign stable anonymous IDs (`hist-001`, `hist-002`, …) and copy the
   sanitized files to `validation/corpus-local/` (or an approved location).
4. Freeze the baseline JSON used for the run (export via 检查项管理 or copy
   the production `baseline.json`); record its `baselineId` in the manifest
   notes. Do not edit the baseline while labels are being produced.
5. A human reviewer — who has not looked at checker output — fills
   `labels/<id>.json` per the schema above:
   - label every (document, item) pair that can be judged from the document;
   - include ambiguous and unsupported cases; anything not safely labelable
     gets `includeInMetrics: false` with an explicit `exclusionReason`;
   - record in `labelledBy` who/what produced the labels;
   - aim to cover CONFIGURED / MISSING / STRUCK_OUT / UNRESOLVED, SAME /
     DIFFERENT descriptions, partial/unknown/mixed strike, conflicting
     parameters, alias and NORMALIZED matches, and LIMITED coverage with
     unsupported OOXML structures — but only as actually present in the
     historical documents; never force categories.
6. Create `validation/manifest.json` from `manifest.example.json` listing
   every document and its labels file.
7. Run `python scripts/run_historical_validation.py validation/manifest.json`.
8. Review `validation/reports/` and classify every discrepancy
   (EXTRACTION / MATCHING / NORMALIZATION / CONFIGURATION / POLICY /
   UNSUPPORTED_SCOPE / LABEL_ERROR).
9. Commit only approved, sanitized label JSON (never raw documents) with a
   `data(task6):` commit; report actual achieved coverage.

## Running the evaluator

```sh
.venv/bin/python scripts/run_historical_validation.py validation/manifest.json \
    --out validation/reports/latest-results.json
```

The harness uses only the production path (`import_document` →
`verify_document`); it never re-implements matching. Without a real corpus it
has nothing to measure — see `reports/` for measured results once available.
