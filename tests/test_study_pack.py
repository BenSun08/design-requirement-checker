"""Offline pack contracts: reject broken/active resources and preserve provenance."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.study_pack.analysis import inspect_sources
from scripts.study_pack.site import source_link, write_archive
from scripts.study_pack.validate import validate_pack


def mini_pack(tmp_path: Path) -> Path:
    pack = tmp_path / "repository-study-pack"
    pack.mkdir()
    (pack / "index.html").write_text(
        '<html><a href="guide.html#ok">Read</a><img src="graph.svg"></html>', encoding="utf-8"
    )
    (pack / "guide.html").write_text('<h1 id="ok">Guide</h1>', encoding="utf-8")
    (pack / "graph.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Local</text></svg>', encoding="utf-8"
    )
    return pack


def test_offline_links_and_svg_namespace_are_allowed(tmp_path):
    validate_pack(mini_pack(tmp_path), required={"index.html", "graph.svg"})


@pytest.mark.parametrize(
    "markup",
    [
        '<img src="https://example.com/a.svg">',
        '<link rel="stylesheet" href="//cdn.example.com/a.css">',
        '<script>fetch("data.json")</script>',
        '<iframe src="guide.html"></iframe>',
        '<a href="http://localhost:8000">server</a>',
        '<a href="guide.html#missing">broken anchor</a>',
        '<img src="missing.svg">',
        '<a href="../outside.html">escape</a>',
        '<base href="https://example.com/">',
        '<img srcset="https://example.com/a.png 2x">',
        '<p onclick="alert(1)">active</p>',
        '<meta http-equiv="refresh" content="0;url=https://example.com">',
    ],
)
def test_rejects_runtime_dependencies_and_broken_links(tmp_path, markup):
    pack = mini_pack(tmp_path)
    (pack / "index.html").write_text(markup, encoding="utf-8")
    with pytest.raises(ValueError):
        validate_pack(pack, required={"index.html"})


@pytest.mark.parametrize(
    "css",
    ['@import "https://example.com/x.css";', "a{background:url(//cdn.test/x)}"],
)
def test_rejects_remote_css(tmp_path, css):
    pack = mini_pack(tmp_path)
    (pack / "styles.css").write_text(css, encoding="utf-8")
    with pytest.raises(ValueError):
        validate_pack(pack, required={"index.html"})


def test_rejects_external_svg_resource(tmp_path):
    pack = mini_pack(tmp_path)
    (pack / "graph.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/x"/></svg>',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        validate_pack(pack, required={"index.html"})


def test_rejects_missing_required_page(tmp_path):
    with pytest.raises(ValueError, match="required"):
        validate_pack(mini_pack(tmp_path), required={"absent.html"})


def test_source_analysis_captures_nested_imports_and_class_methods(tmp_path):
    src = tmp_path / "src/design_requirement_checker"
    src.mkdir(parents=True)
    (src / "domain.py").write_text('class Item:\n    """Value."""\n    pass\n')
    (src / "application.py").write_text(
        "class App:\n    def load(self):\n        from .domain import Item\n        return Item()\n"
    )
    inventory = inspect_sources(tmp_path)
    assert inventory["application"]["imports"] == ["design_requirement_checker.domain"]
    assert inventory["application"]["symbols"]["App.load"]["line"] == 2


def test_source_reference_resolves_symbol_and_rejects_stale_names(tmp_path):
    src = tmp_path / "src/design_requirement_checker"
    src.mkdir(parents=True)
    (src / "matching.py").write_text("def verify():\n    return ()\n")
    inventory = inspect_sources(tmp_path)
    link = source_link("src/design_requirement_checker/matching.py::verify", inventory, tmp_path)
    assert "#L1" in link
    assert "verify" in link
    with pytest.raises(ValueError, match="symbol"):
        source_link("src/design_requirement_checker/matching.py::verify_item", inventory, tmp_path)


def test_archive_has_one_root_and_crc_and_excludes_no_pack_files(tmp_path):
    pack = mini_pack(tmp_path)
    archive = write_archive(pack, tmp_path / "pack.study-pack.zip")
    with ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert set(zipped.namelist()) == {
            "repository-study-pack/index.html",
            "repository-study-pack/guide.html",
            "repository-study-pack/graph.svg",
        }


def test_boundary_scan_reports_ui_store_coupling_and_pure_layer_violation():
    from scripts.study_pack.analysis import boundary_findings

    findings = boundary_findings(
        {
            "ui.main_window": {"imports": ["design_requirement_checker.baseline_store"]},
            "matching": {"imports": ["pathlib"]},
            "baseline_store": {"imports": ["PySide6.QtCore"]},
        }
    )
    assert any("ui.main_window" in finding and "baseline_store" in finding for finding in findings)
    assert any("matching" in finding and "pathlib" in finding for finding in findings)
    assert not any(finding.startswith("baseline_store") for finding in findings)


def test_does_not_overwrite_existing_output(tmp_path):
    from scripts.build_study_pack import build

    pack = mini_pack(tmp_path)
    before = (pack / "index.html").read_bytes()
    with pytest.raises(ValueError, match="empty or absent"):
        build(pack, tmp_path / "no-tools")
    assert (pack / "index.html").read_bytes() == before
