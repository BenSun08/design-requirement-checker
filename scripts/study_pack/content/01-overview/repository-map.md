# Repository map

Read responsibilities before directories. The source shelf below is an offline,
line-numbered representation of selected text files, each included once. It is
not an executable distribution or a second repository archive.

| Area | What to look for |
|---|---|
| `docs/constitution.md` | Architectural boundaries and invariants; highest authority |
| `docs/spec.md` | Status semantics, supported scope, UX and future features |
| `docs/plan.md` | Decisions, milestones, evidence and deferred validation |
| `docs/tasks.md` | Completed, blocked and deferred work |
| `src/design_requirement_checker/` | The actual desktop implementation |
| `tests/` | Independent expected outcomes and deterministic fixture construction |
| `validation/` | Historical evaluation tooling; no historical metrics are inferred |
| `.github/workflows/` | Source CI, Windows packaging, offline development bundle, study pack |
| `packaging/` | Windows PyInstaller build configuration, separate from this pack |
| `prototype/` | Historical browser UX reference, not production behavior |
| `.ua/` | Existing analysis metadata, not application authority or a runtime dependency |
| `scripts/study_pack/` | Reviewed study prose and build-only graph/render tools |

Authority is constitution → spec → plan → tasks. README is a landing page.
Some historical comments and milestone tables describe earlier slices: inspect
the current function body and tests before treating them as current behavior.
For example, domain's `CheckItem` docstring still mentions persistence as later
work, while the current store and UI already implement it.

[Markdown map](repository-map.md) is also included. The rendered page below
provides direct links suitable for a browser with no Markdown viewer.
