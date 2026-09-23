# Task 6 — Release-Readiness Proposal

**Status: PROPOSAL ONLY — not an approval, not a release gate.**
Nothing in this file has been accepted. Every threshold below requires an
explicit owner decision. The product is **not** declared ready by this
document.

## 1. Measured values (facts)

**No historical validation measurement has been performed.** The
independently labelled real/sanitized corpus required by Task 6 has not been
supplied (see `validation/README.md` — T6.4 BLOCKED). Therefore every metric
is currently NOT MEASURED, with denominator 0:

| Metric | Measured value |
|---|---|
| Precision | NOT MEASURED — N/A (0/0) |
| Recall | NOT MEASURED — N/A (0/0) |
| Status accuracy | NOT MEASURED — N/A (0/0) |
| Strike accuracy | NOT MEASURED — N/A (0/0) |
| Description-comparison accuracy | NOT MEASURED — N/A (0/0) |
| Unresolved rate | NOT MEASURED — N/A (0/0) |
| LIMITED-coverage document rate | NOT MEASURED — N/A (0/0) |
| Unsupported-warning document rate | NOT MEASURED — N/A (0/0) |
| Review-time change | NOT MEASURED — no timing study recorded |

Synthetic unit/integration tests (528+ passing) prove implementation
consistency with the validated S6/domain contract only. They are **not**
historical evidence and contribute no numbers above.

## 2. Proposed thresholds (clearly labelled as proposal)

These are suggested **starting points for discussion**, not gates derived
from measurements (none exist yet) and not product-document requirements.
Project docs (product-spec.md acceptance item 8) require agreeing release
thresholds before pilot but do not define numeric values, so none are
inherited here.

- Precision (presence): PENDING OWNER APPROVAL — suggested ≥ 95% once a
  corpus of ≥ 100 labelled cases exists
- Recall (presence): PENDING OWNER APPROVAL — suggested ≥ 90%
- Strike accuracy: PENDING OWNER APPROVAL — suggested ≥ 90% on labelled
  strike cases
- Description-comparison accuracy: PENDING OWNER APPROVAL — suggested ≥ 90%
- Allowed unresolved rate: PENDING OWNER APPROVAL — suggested ≤ 10% of
  labelled cases, each with inspectable reasons
- Zero fabricated-evidence cases: PENDING OWNER APPROVAL (hard requirement
  candidate — MISSING must never carry invented evidence)

Do not treat any of these as accepted. Re-evaluate after real measurements
exist.

## 3. Pilot scope proposal (based on documented supported scope, not metrics)

Evidence available today is the declared supported scope (domain-model.md,
technical-spikes.md), not historical measurements:

- Document types: `.docx` OOXML packages whose relevant content lives in
  body paragraphs and table-cell paragraphs.
- Known unsupported structures that force LIMITED coverage (must be visible
  to reviewers): tracked revisions, text boxes, content controls, field
  codes, footnote/endnote references, smart tags, altChunk, nested/invalid
  hyperlinks, excluded header/footer content.
- LIMITED-coverage documents entering the pilot: PENDING OWNER APPROVAL —
  proposal: allowed only when reviewers are trained that MISSING claims are
  scoped to the checked range.
- Manual review: PENDING OWNER APPROVAL — proposal: every UNRESOLVED case
  requires engineer review before acceptance decisions; the tool never
  auto-accepts.
- Pilot corpus/scope: PENDING OWNER APPROVAL — proposal: 2–3 engineers,
  10–20 order documents, one frozen baseline, with the Task 6 evaluator run
  over independently labelled copies in parallel for the first month.

## 4. Prerequisites before any release decision

1. Supply a sanitized/real historical corpus and complete T6.4–T6.8
   (measure, classify discrepancies, fix agreed defects, re-run).
2. Owner approves numeric thresholds against the measured values.
3. Task 7 no-admin Windows deployment evidence (separate gate; green CI is
   not deployment evidence).
