"""S6 spike evidence: representative scale, cancellation checkpoints, determinism.

Sizes are chosen from the product context (a 《设计开发要求》 is roughly tens to
low hundreds of pages; the baseline holds tens to low hundreds of items). The
assertions below are sanity bounds only — they record measurements and answer
viability, they do not invent performance requirements.
"""

import tracemalloc

import pytest
from s6_probe import (
    SpikeCancelled,
    generate_scale_document,
    verify,
)

SIZES = {"small": (200, 20), "medium": (800, 60), "large": (3000, 100)}


@pytest.mark.parametrize(("name"), sorted(SIZES))
def test_representative_scale_completes_and_is_measured(name: str) -> None:
    import time

    blocks_n, items_n = SIZES[name]
    items, blocks = generate_scale_document(blocks_n, items_n)
    char_count = sum(len(b.text) for b in blocks)

    started = time.perf_counter()
    results = verify(items, blocks)
    elapsed = time.perf_counter() - started

    assert len(results) == items_n
    assert all(r.resolution == "RESOLVED" and r.status == "CONFIGURED" for r in results)
    assert all(r.comparison_state == "DIFFERENT" for r in results)
    total_occurrences = sum(len(r.occurrences) for r in results)
    assert total_occurrences == items_n * 2  # two synthetic hits per item by construction
    assert elapsed < 60.0  # sanity bound only, not a performance requirement
    print(
        f"\n[scale:{name}] blocks={blocks_n} chars={char_count} items={items_n} "
        f"occurrences={total_occurrences} wall={elapsed:.3f}s"
    )


def test_large_run_memory_is_bounded_and_recorded() -> None:
    blocks_n, items_n = SIZES["large"]
    items, blocks = generate_scale_document(blocks_n, items_n)
    tracemalloc.start()
    results = verify(items, blocks)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(results) == items_n
    assert peak < 512 * 1024 * 1024  # generous bound; actual value recorded below
    print(f"\n[scale:large-memory] peak_bytes={peak}")


def test_repeated_runs_are_deterministic_and_source_ordered() -> None:
    blocks_n, items_n = SIZES["medium"]
    items, blocks = generate_scale_document(blocks_n, items_n)
    first = verify(items, blocks)
    second = verify(items, blocks)
    assert first == second  # equivalent normalized output across repeated runs
    for result in first:
        keys = [(o.block_index, o.raw_match_span) for o in result.occurrences]
        assert keys == sorted(keys)  # evidence keeps stable source order


def test_cancellation_checkpoints_are_per_item_and_block() -> None:
    blocks_n, items_n = SIZES["small"]
    items, blocks = generate_scale_document(blocks_n, items_n)
    calls = {"n": 0}

    def never_cancel() -> bool:
        calls["n"] += 1
        return False

    results = verify(items, blocks, cancel_check=never_cancel)
    assert len(results) == items_n
    assert calls["n"] == blocks_n * items_n  # one checkpoint per (item, block)


def test_cancellation_stops_without_a_completed_run() -> None:
    blocks_n, items_n = SIZES["small"]
    items, blocks = generate_scale_document(blocks_n, items_n)
    calls = {"n": 0}

    def cancel_after_five() -> bool:
        calls["n"] += 1
        return calls["n"] > 5

    with pytest.raises(SpikeCancelled):
        verify(items, blocks, cancel_check=cancel_after_five)
    assert calls["n"] == 6  # stopped at the first checkpoint after the request
