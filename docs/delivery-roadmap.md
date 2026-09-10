# Product delivery roadmap

[简体中文版](../docs-zh/delivery-roadmap.md)

Status: updated after owner confirmation. Production: **Python + PySide6 / Qt Widgets**. Deployment: **Windows 10/11 x64, no administrator/installation privileges**. The roadmap remains expressed as user outcomes; detailed tasks are in implementation-plan.md. Approximately eight hours/week is available. No production code or spike is executed by this document update.

| Milestone | User-visible outcome | Acceptance criteria | Remaining validation / gate |
|---|---|---|---|
| 0 Definition, prototype and decisions | Reviewable mock plus agreed product rules and stack | Historical prototype retained; separate detection phrase, three statuses plus unresolved, conflict/partial-strike rules, one baseline and scope documented | Completed decision gate; prototype does not yet demonstrate every newly confirmed rule |
| 1 Real DOCX ingestion | Open a supported local file and inspect text/formatting/source | Body/table/cell paragraphs and run mapping correct; no cross-paragraph/cell join; unknown/unsupported scope visible; original unchanged | S1/S2 fidelity, inherited formatting, merged/nested tables, exact library versions |
| 2 Deterministic checking | Explainable findings against configured phrases/aliases | Confirmed classification precedence, all relevant evidence, conservative normalization, required detectionPhrase; no guessed function identity | S6 requirement-span association, transformation allowlist, ambiguous corpus cases |
| 3 End-to-end review | Import → run → exceptions → expected/actual/context | Three status counts plus unresolved total correctly; limited-coverage notice; all occurrences inspectable; errors/cancel distinct from missing; responsive UI | Windows Qt usability, comparison limits, performance and cancellation |
| 4 Local baseline management | Maintain one baseline and retain it across restarts | Add/edit/disable/delete and detection phrase/aliases; enabled set applies to current order; save/recovery and invalidation work without elevation | Storage format/path and write-failure recovery; no templates or sync |
| 5 Historical validation | Engineer can judge pilot reliability | Labelled corpus; precision/recall, false positives/negatives, strike accuracy, unresolved/unsupported rates and review-time change with denominators | Representative samples and release thresholds agreed before pilot |
| 6 Windows distribution and pilot | Ordinary user can run and update the app | Both Windows 10/11 x64; no admin or separately installed developer runtime; fully offline first distribution/install/launch/checking; replacement preserves baseline; permitted portable/per-user distribution | S3 early feasibility, Python 3.8 coexistence, exact OS builds and IT policy; fully offline first distribution/install is mandatory |

S3 is deliberately early even though the production pilot is Milestone 6. Users cannot elevate: an administrator-required installer is not an acceptable default. Validate a portable directory first; retain per-user installer as an option only if policy allows it. A policy preventing all user-level execution is an IT dependency to resolve, not a reason to bypass restrictions.

Milestone 2 consumes baseline data; Milestone 4 adds full editing/persistence UX. Expected/actual comparison is MVP; enhanced diff/fuzzy matching, manual confirmation, export and improved preview remain candidates after pilot feedback. AI, editing, Word integration, multiple baselines and team synchronization require separate scope decisions.

Implementation remains gated by explicit execution authorization and relevant validation evidence. Validation failure triggers a bounded reassessment inside the selected stack; replacing the stack requires the owner to decide again. Schedule targets are reviewed after probes, not derived from the mock's completion.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
