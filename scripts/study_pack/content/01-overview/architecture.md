# Architecture: boundaries that preserve evidence

This is one local desktop process. Engineers maintain a checklist, import an
engineering DOCX and review deterministic findings. A match is evidence of a
mention, never engineering acceptance. The production UI is PySide6; the
historical `prototype/` browser mock does not execute the checker.

![Architecture diagram](architecture.svg)

Arrows mean **depends on / calls into**, not movement of document bytes.
The adapter and store produce domain values. The matching engine consumes
those values without knowing where they came from.

| Boundary | Responsibility | Why it exists |
|---|---|---|
| UI | Widgets, Chinese labels, filtering, worker ownership | Presentation must not redefine the truth table |
| Application | Import/verification use cases, validation and failure translation | Callers receive explicit outcomes |
| Domain | Frozen snapshots, enums, construction invariants | Evidence can cross thread boundaries without mutable library objects |
| Matching | Normalization, detection, span association, classification | Identical inputs produce identical results |
| DOCX adapter | Package parsing, OOXML, strike inheritance, locations | Word complexity stays behind one conversion boundary |
| Baseline store | JSON, backup recovery, atomic replacement | Disk failure must not silently publish unsaved state |

The diagram includes an actual UI → store coupling for path lookup and
schema-error handling. The [dependency page](../02-code-structure/module-dependencies.html)
distinguishes this from the simpler intended layering. No production refactor
is part of this study pack.

Start with [[docs/constitution.md]], then
[[src/design_requirement_checker/domain.py::Document]] and
[[src/design_requirement_checker/application.py::verify_document]].
The [startup trace](../03-runtime-flows/startup.html) connects these boundaries.
