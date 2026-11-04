# Class map: values, outcomes and widgets

The inventory below is generated from Python's AST, including base classes and
source docstrings. Docstrings describe intent and can retain historical wording;
the linked implementation remains the evidence.

Follow the value chain: `Document` contains `DocumentBlock` tuples; each block
contains `TextRun` values and a `DocumentLocation`. `CheckItem` contains explicit
aliases. `CheckResult` retains a tuple of `MatchEvidence` values, the item
snapshot, independent status/resolution/comparison and a rule revision.

Application outcome dataclasses wrap success, cancellation and expected failure.
Qt classes handle presentation and scheduling: `MainWindow` is a `QMainWindow`,
workers are `QObject`s, `ChecklistPage` is a `QWidget` and `ItemEditorDialog`
is a `QDialog`. Inheritance identifies UI roles; it does not transfer domain
policy to those classes.

Read [domain values](../04-module-guides/domain.html), then
[application outcomes](../04-module-guides/application.html).
