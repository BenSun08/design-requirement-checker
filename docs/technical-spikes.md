# Technical spikes proposed before stack selection

Status: **PROPOSED ONLY — none executed in this phase.** Each probe is disposable, bounded and requires approval before code. No production parser or desktop application is authorized by this document. Suggested timeboxes are effort caps, not delivery promises; eight hours of effort consumes roughly a week of the owner's available time.

## Inputs and order

First obtain sanitized representative DOCX samples, expected engineer labels, supported Windows versions/architectures, standard-user/installer constraints and maintainer language familiarity. Shortlist A and E provisionally; substitute B if existing TS expertise clearly dominates. Share fixtures and output shape so comparisons test the same problem. Stop at the timebox and record unknowns rather than building an engine.

| Spike | Question and minimal experiment | Pass / evidence | Budget and decision impact |
|---|---|---|---|
| S1 OOXML formatting fidelity | Read a tiny set of normal/table/full-strike/partial-strike/mixed-run/style-inherited fixtures in each shortlisted library. Include explicit strike=false, basedOn styles, document defaults, double strike and tracked deletion as distinct cases. Print raw run text, effective strike and origin only. No UI or matcher. | Every fixture span equals reviewed ground truth; unknown/unsupported features explicit; direct property not mistaken for effective style. Save library versions, extraction output and gaps. | 4–8 h per candidate. Gate parser feasibility and custom resolver effort. |
| S2 Source locations and normalization mapping | Traverse body paragraphs, table/cell paragraphs, nested and merged cells; reconstruct a run-split requirement; map normalized hits back to raw character spans and original locations. | Each extracted block/hit reopens the same origin in a second traversal; no cross-cell text leakage; stable snapshot-local IDs; Unicode offsets and one-based display verified. | 3–5 h for lead, targeted comparison if needed. Gate traceability. |
| S3 Windows installer reality | Package only a window, file picker and a tiny extraction fixture. Install/launch/uninstall on a clean managed Windows VM without development runtimes or Internet. | Document standard-user behavior, runtime dependencies, installer/installed size, startup, endpoint-protection findings, Chinese paths/IME, DPI 100/150/200%, baseline data retention on upgrade/uninstall. No promised AV outcome. | 4–8 h per finalist, needs Windows/IT access. Can veto otherwise good stack. |
| S4 Process communication — conditional | Only if C or D-with-sidecar remains competitive: one request/response, progress, cancellation, invalid message, core crash, restart, large result and app shutdown. | Correlation and errors correct, UI responsive, no orphan core process, schema mismatch rejected, file paths passed safely, no network port required. | 3–5 h. Skip entirely for single-core-process design; compare burden with A/E. |
| S5 Structure preservation — limited future risk | Open/save a copied fixture without semantic edits; optionally modify one run. Compare OOXML parts/relationships and review in Word; keep original bytes untouched. | Report preserved/lost styles, tables, images, hyperlinks, fields and unsupported parts; no “lossless” claim from text equality. | 2–4 h on preferred library. Advisory unless DOCX editing becomes near-term scope. |
| S6 Matching policy and document scale | Engineer labels repeated/conflicting/alias/similar-name/number-unit/split-paragraph examples. Test a few pure matching functions and representative document sizes, no production pipeline. | Proposed rules do not erase 2s/3s, negation or conditions; false matches visible; memory/time measured; agree limits/cancel behavior. Ambiguous labels remain owner decisions. | 3–5 h. Gate status/normalization policy, not UI framework choice. |

S1 and S3 have highest stack-selection value; S2 is a traceability gate. S6 may start as a paper/fixture review before any matching code. S5 must not pull document editing into the MVP. A timeboxed probe failing does not prove a stack impossible; it establishes the unresolved effort/risk.

## Fixture design

Use the eight named fixtures in product-spec.md plus inherited-strike-override, repeated-conflicting, nested-merged-table, split-paragraph, tracked-revision, malformed and large-document examples. Include Chinese punctuation, spaces, tabs, nonbreaking spaces and units. Engineer labels define function identity, strike spans, location and expected policy independently of parser output. Synthetic fixtures isolate causes; sanitized historical files test representativeness.

Password-protected or unsupported files should fail with an explicit unsupported-format outcome. A ZIP signature alone is not DOCX validation. Bound decompression and XML resource use; do not execute macros or fetch external relationships. These are adapter requirements, not a request for security infrastructure.

## Result template and selection gate

For each executed spike record: hypothesis, exact scope, versions/environment, fixture identities, observed outputs, pass/fail/unknown per case, effort spent, workaround cost, conclusion and remaining limitations. Attach small evidence artifacts, not production scaffolding.

Before selection, compare finalists on fidelity gaps, installer constraints, maintained language count and demonstrated engineering effort. Owner approves classification questions and chooses the stack explicitly. Only then create the detailed production implementation plan in a separate authorized phase.
