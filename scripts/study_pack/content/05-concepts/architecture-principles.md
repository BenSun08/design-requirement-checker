# Architecture principles: make uncertainty representable

## Values at the boundary

An adapter that returned python-docx paragraphs would force the matcher and UI
to understand Word internals. Instead, `read_document` converts them to frozen
`DocumentBlock` and `TextRun` values. The matcher can then run on synthetic
blocks without opening a file or starting Qt. Immutability also makes the
worker's result a snapshot rather than a shared mutable parser state.

## Separate dimensions preserve meaning

Consider an active mention whose description says 3s when the baseline expects
2s. Presence is CONFIGURED, comparison is DIFFERENT. These are not contradictory
answers; they answer different questions. Unknown formatting instead affects
resolution. Coverage asks a third question: how much of the input could be
checked? Conflating these dimensions would produce unjustified certainty.

## Publish only after success

The application translates failures but the UI owns displayed state. A cancelled
run carries no completed results. A baseline candidate is published only after
save returns successfully. Both rules avoid making an incomplete operation look
like accepted current state.

Read [[docs/constitution.md]],
[[src/design_requirement_checker/domain.py::CheckResult]], and
[[src/design_requirement_checker/application.py::VerificationOutcome]].
Then trace [the overall architecture](../01-overview/architecture.html).
