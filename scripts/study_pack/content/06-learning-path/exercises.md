# Exercises: predict before expanding the answer

All exercises are reasoning tasks. You need no interpreter to complete them.
Use [the reading order](reading-order.html) to inspect the relevant source.

<details><summary>Why is UNRESOLVED separate from CheckStatus?</summary><p>It describes whether evidence permits assigning a status. CONFIGURED, MISSING and STRUCK_OUT are the three resolved statuses. UNRESOLVED requires status=None, avoiding a fabricated absence or presence decision. Comparison and coverage remain separate dimensions too.</p></details>

<details><summary>Why must unknown strike not become False?</summary><p>False means known active formatting. A broken style chain or unsupported double-strike meaning does not establish that fact. Keeping None and a reason leads to explicit review instead of a potentially wrong CONFIGURED result.</p></details>

<details><summary>Why is matching independent of Qt?</summary><p>The engine should return the same evidence and classification for the same domain inputs regardless of widgets, event ordering or operating system presentation. Tests can construct values directly. UI filters and labels cannot silently redefine domain rules.</p></details>

<details><summary>Why avoid QThread.terminate()?</summary><p>Forced termination can interrupt arbitrary code and resource cleanup. Verification polls an Event at defined checkpoints and returns a cancelled outcome with no partial results. Import cannot be cooperatively stopped, so window close defers until it finishes.</p></details>

<details><summary>A starts, B starts and completes, then A completes. Which result is shown?</summary><p>B remains current. Its operation generation superseded A. A's callback still cleans up A's thread by captured identity, but its stale generation prevents UI publication. Verification also checks document identity.</p></details>

<details><summary>Why is primary never moved away before new-primary installation?</summary><p>If final replacement failed after moving primary away, the normal primary path would disappear. Copying old primary to a separate temporary backup keeps it available throughout preparation. A failed final install can leave the backup refreshed, while primary and in-memory snapshot remain old.</p></details>

<details><summary>What happens when a table cell contains a function requirement?</summary><p>Each cell paragraph is a block with table/row/column coordinates and nested ancestor path. Matching examines that block normally, including its run strike. It does not join the cell with neighbouring cells. Merged masters are extracted once.</p></details>

<details><summary>Raw text is A, two tabs, B. What raw span corresponds to the normalized space?</summary><p>The normalized text is A B. The space maps to half-open raw span [1,3), covering both tabs. Normalization never replaces stored raw text, so evidence highlighting can still point to the exact input.</p></details>

<details><summary>Active evidence says 延时3s; expected description is 延时2s. Is the item MISSING?</summary><p>No. Assuming unambiguous, comparable evidence, it is CONFIGURED + DIFFERENT. Presence and description equality are independent. Conflicting active occurrences with different key values would be a separate reason for UNRESOLVED.</p></details>

<details><summary>Does clearing the current worker pointer mean the worker is safe to destroy?</summary><p>No. A retiring thread can still need that QObject. The thread-to-worker map retains it until the finished callback joins final termination and releases ownership. Generation checks alone cannot prevent a native lifetime crash.</p></details>

<details><summary>Primary has an unsupported schema but backup is readable. Should load silently use backup?</summary><p>No. An incompatible schema indicates a version/downgrade situation, not ordinary corruption. The dedicated error stops fallback so newer data is not silently hidden or overwritten.</p></details>

<details><summary>A document is LIMITED and an item is MISSING. What can you conclude?</summary><p>No qualifying evidence was found in the successfully checked supported scope. You cannot conclude that the function is physically absent from all Word structures. Coverage warnings must remain visible.</p></details>

Verify answers against [[src/design_requirement_checker/matching.py]],
[[src/design_requirement_checker/ui/main_window.py]],
[[src/design_requirement_checker/baseline_store.py]], and [[tests/test_matching.py]].
