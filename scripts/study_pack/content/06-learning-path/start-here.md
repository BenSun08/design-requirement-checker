# Start Here

You can study this pack with only a browser. Begin with the diagram, read the
explanation, then follow a source reference. The source shelf is included as
ordinary HTML with line anchors; no GitHub connection or editor is required.
Use browser Find to locate names and browser Back to return to the guide.

## Level 1 — architecture

Read [the architecture](../01-overview/architecture.html),
[[docs/constitution.md]], [domain](../04-module-guides/domain.html), and
[application](../04-module-guides/application.html).
Checkpoint: explain why status, resolution, comparison and coverage are distinct.

## Level 2 — core checking

Read [matching](../04-module-guides/matching.html),
[DOCX adapter](../04-module-guides/docx-adapter.html), and
[deterministic matching](../05-concepts/deterministic-matching.html).
Checkpoint: trace one phrase from raw run offsets to retained MatchEvidence.

## Level 3 — desktop engineering

Read [MainWindow](../04-module-guides/main-window.html),
[workers](../04-module-guides/ui-components.html),
[Qt threading](../05-concepts/qt-threading.html), and
[shutdown](../03-runtime-flows/shutdown.html).
Checkpoint: distinguish stale-result rejection from worker lifetime protection.

## Level 4 — persistence

Read [store](../04-module-guides/baseline-store.html),
[save flow](../03-runtime-flows/baseline-persistence.html), and
[persistence concepts](../05-concepts/persistence.html).
Checkpoint: predict primary, backup and in-memory state after final replacement fails.

## Level 5 — tests

Read [testing strategy](../05-concepts/testing-strategy.html), then the domain,
DOCX, matching, UI/thread and startup suites in the
[source shelf](../01-overview/repository-map.html).
Checkpoint: name a test that would detect each failure you predicted.

Continue with the [symbol reading order](reading-order.html),
[exercises with answers](exercises.html), and [interview practice](interview-questions.html).
