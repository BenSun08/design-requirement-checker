"""S1 spike evidence: OOXML formatting fidelity.

Expected values below are independent labels written by hand from the fixture
definitions in fixture_factory.py and the OOXML strike-resolution rules
(run rPr -> character style chain -> paragraph style chain -> docDefaults ->
default off). They are not copies of probe output.

Environment under test: python-docx 1.2.0 + lxml on Python 3.13 (macOS).
"""

import hashlib
from pathlib import Path

import fixture_factory as fixtures
import pytest
from docx_probe import probe_docx

RESOLVED_FALSE = (False, "direct", "")
RESOLVED_DEFAULT_OFF = (False, "default-off", "")


def strike_state(block, run_index):  # type: ignore[no-untyped-def]
    run = block.runs[run_index]
    return (run.strike, run.strike_origin, run.strike_reason)


@pytest.fixture(scope="session")
def normal(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_normal(tmp_path_factory.mktemp("s1-normal") / "normal.docx")


@pytest.fixture(scope="session")
def strike_matrix(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_strike_matrix(tmp_path_factory.mktemp("s1-strike") / "strike-matrix.docx")


@pytest.fixture(scope="session")
def docdefaults(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_docdefaults_strike(
        tmp_path_factory.mktemp("s1-docdefaults") / "docdefaults-strike.docx"
    )


@pytest.fixture(scope="session")
def tracked(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_tracked_revisions(
        tmp_path_factory.mktemp("s1-tracked") / "tracked-revisions.docx"
    )


@pytest.fixture(scope="session")
def empty(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_empty(tmp_path_factory.mktemp("s1-empty") / "empty.docx")


@pytest.fixture(scope="session")
def malformed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_malformed(tmp_path_factory.mktemp("s1-malformed") / "malformed.docx")


def test_body_paragraph_text_and_run_offsets(normal: Path) -> None:
    blocks = probe_docx(normal).blocks
    assert [b.raw_text for b in blocks] == [
        "plain body paragraph one",
        "Hello bold world",
        "AlphaBeta",
        "A  B\tC",
        "",
    ]
    # Split runs keep their own half-open code-point ranges.
    hello = [(r.text, r.start, r.end) for r in blocks[1].runs]
    assert hello == [("Hello ", 0, 6), ("bold", 6, 10), (" world", 10, 16)]
    # Adjacent same-format runs remain separate runs (no silent merging).
    assert [(r.text, r.start, r.end) for r in blocks[2].runs] == [
        ("Alpha", 0, 5),
        ("Beta", 5, 9),
    ]
    # An empty paragraph is a block with no runs, not a missing block.
    assert blocks[4].runs == ()


def test_direct_strike_true_false_and_partial(strike_matrix: Path) -> None:
    blocks = probe_docx(strike_matrix).blocks
    assert strike_state(blocks[0], 0) == (True, "direct", "")
    assert strike_state(blocks[1], 0) == RESOLVED_FALSE
    partial = blocks[2]
    assert partial.raw_text == "keep gone tail"
    assert strike_state(partial, 0) == RESOLVED_DEFAULT_OFF
    assert strike_state(partial, 1) == (True, "direct", "")
    assert strike_state(partial, 2) == RESOLVED_DEFAULT_OFF


def test_style_inherited_strike_and_explicit_override(strike_matrix: Path) -> None:
    blocks = probe_docx(strike_matrix).blocks
    # Paragraph style StruckStyle (basedOn Normal, strike on) without direct value.
    assert strike_state(blocks[3], 0) == (True, "paragraph-style", "")
    # Explicit run-level false overrides the inherited style strike.
    assert strike_state(blocks[4], 0) == (False, "direct", "")


def test_docdefaults_strike_resolution(docdefaults: Path) -> None:
    blocks = probe_docx(docdefaults).blocks
    # docDefaults rPrDefault carries <w:strike/>: plain runs inherit True.
    assert strike_state(blocks[0], 0) == (True, "doc-defaults", "")
    assert strike_state(blocks[1], 0) == (False, "direct", "")


def test_double_strike_is_detectable_but_unknown(strike_matrix: Path) -> None:
    run = probe_docx(strike_matrix).blocks[5].runs[0]
    # w:dstroke is readable via python-docx (font.double_strike), but whether
    # double strike counts as deletion formatting is an open product question:
    # the probe keeps effective strike unknown instead of guessing.
    assert run.double_strike is True
    assert run.strike is None
    assert run.strike_reason == "double-strike"


def test_invalid_strike_value_stays_unknown(strike_matrix: Path) -> None:
    run = probe_docx(strike_matrix).blocks[6].runs[0]
    # python-docx raises InvalidXmlError for w:strike w:val="maybe"; the probe
    # classifies it as unknown rather than converting it to False.
    assert run.strike is None
    assert run.strike_reason == "invalid-strike-value"


def test_orphan_style_reference_stays_unknown(strike_matrix: Path) -> None:
    run = probe_docx(strike_matrix).blocks[7].runs[0]
    # python-docx's run.style silently falls back to the default character
    # style for a missing rStyle target; the probe detects the orphan
    # reference itself and reports unknown.
    assert run.strike is None
    assert run.strike_reason == "orphan-style-reference"
    assert run.strike_origin == "character-style"


def test_unknown_strike_always_carries_a_reason(
    normal: Path,
    strike_matrix: Path,
    docdefaults: Path,
    tracked: Path,
) -> None:
    for path in (normal, strike_matrix, docdefaults, tracked):
        for block in probe_docx(path).blocks:
            for run in block.runs:
                if run.strike is None:
                    assert run.strike_reason, (
                        f"unknown strike without reason in {path.name} {block.block_id}"
                    )
                else:
                    assert run.strike in (True, False)


def test_tracked_revisions_are_limited_not_silent(tracked: Path) -> None:
    probed = probe_docx(tracked)
    revision_block, clean_block = probed.blocks
    # Runs inside w:ins / w:del are not part of paragraph.runs; the block is
    # explicitly LIMITED instead of silently losing revision text.
    assert revision_block.raw_text == "kept "
    assert revision_block.limited_reasons == ("tracked-revisions-unsupported",)
    assert "INSERTED" not in revision_block.raw_text
    assert "REMOVED" not in revision_block.raw_text
    assert clean_block.raw_text == "clean paragraph"
    assert clean_block.limited_reasons == ()
    assert probed.coverage == "LIMITED"
    assert probed.coverage_reasons == ("tracked-revisions-unsupported",)


def test_malformed_input_fails_explicitly(malformed: Path) -> None:
    probed = probe_docx(malformed)
    assert probed.coverage == "FAILED"
    assert probed.blocks == ()
    assert probed.error is not None
    assert "PackageNotFoundError" in probed.error


def test_valid_empty_document_is_complete_not_failed(empty: Path) -> None:
    probed = probe_docx(empty)
    assert probed.coverage == "COMPLETE"
    assert probed.coverage_reasons == ()
    assert probed.blocks == ()
    assert probed.error is None


def test_original_input_bytes_are_unchanged(
    normal: Path,
    strike_matrix: Path,
    docdefaults: Path,
    tracked: Path,
    empty: Path,
) -> None:
    for path in (normal, strike_matrix, docdefaults, tracked, empty):
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        probe_docx(path)
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        assert before == after, f"probe modified {path.name}"
