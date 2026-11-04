# Testing strategy: prove the dangerous transition

Expected outcomes must be written independently of the function being tested.
Calling `normalize` to generate the expected value for a normalization test
would reproduce the same bug on both sides of the assertion.

| Suite | What to inspect |
|---|---|
| `test_domain.py` | Construction invariants, identity, offsets and resolution/status |
| `test_matching.py` | Allowlist rejection cases, span boundaries, contradictions, cancellation placement |
| `test_docx_adapter.py` | Synthetic Word files, inherited strike, tables, unsupported structures |
| `test_application.py` | Failure translation, enabled filtering, validation and cancelled outcomes |
| `test_baseline_store.py` | Round trips, schema handling and failure at each replacement phase |
| `test_ui.py` | Stale completion orders, ownership, cancellation and deferred close |
| `test_checklist_ui.py` | Candidate editing, stable identity, failed-save preservation |
| `test_startup.py` | Real composition in subprocesses, load-state mapping, import/verify survival |

`fixture_factory.py` creates deterministic DOCX examples. Small documented OOXML
patches construct cases public python-docx APIs cannot express. These fixtures
are test evidence, not an independently labelled historical customer corpus.

For races, Events and controlled callbacks establish ordering. The stale-import
test releases old A only after B has completed, then waits for A's real terminal
signal and cleanup before asserting the visible document remains B. Merely
waiting until B appears would miss a later stale overwrite. Retirement tests
assert strong ownership, not just the absence of warnings.

The current dependency list uses pytest and direct Qt testing primitives;
`docs/plan.md` retains a historical pytest-qt mention. Consult `pyproject.toml`
and actual tests for the installed setup. This pack does not run historical
Task 6 measurements or formal Task 7 deployment validation.

References: [[tests/test_ui.py]], [[tests/test_startup.py]],
[[tests/fixture_factory.py]], [[pyproject.toml]], [[docs/tasks.md]].
Next: [learning path](../06-learning-path/start-here.html).
