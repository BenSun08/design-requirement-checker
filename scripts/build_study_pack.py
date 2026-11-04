#!/usr/bin/env python3
"""Build a static repository study pack. Run on the build machine, never on the reader's PC."""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Support both `python scripts/build_study_pack.py` and module execution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.study_pack.analysis import (  # noqa: E402
    boundary_findings,
    generate_graphs,
    inspect_sources,
    render_mermaid,
    run,
)
from scripts.study_pack.diagrams import DIAGRAMS  # noqa: E402
from scripts.study_pack.site import (  # noqa: E402
    SECTION_NAMES,
    class_map,
    listing_path,
    page,
    render_content,
    source_listings,
    symbol_index,
    write_archive,
)
from scripts.study_pack.validate import REQUIRED, SECTIONS, validate_pack  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "scripts/study_pack"


def build(destination: Path, node_tools: Path) -> dict:
    destination = destination.resolve()
    # Avoid deleting or mixing arbitrary caller-owned directories on repeat builds.
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Output must be empty or absent: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    sha = run(["git", "rev-parse", "HEAD"], ROOT).strip()
    dirty = bool(run(["git", "status", "--porcelain", "--untracked-files=normal"], ROOT).strip())
    inventory = inspect_sources(ROOT)
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    info = {
        "repository": "https://github.com/BenSun08/design-requirement-checker",
        "git_sha": sha,
        "generated_at": generated,
        "working_tree_dirty": dirty,
        "content_policy": "Reviewed explanations plus build-time source inventory; no LLM calls.",
        "analysis_limits": "Static imports and inferred uses; not exhaustive runtime dispatch.",
        "tools": {
            name: importlib.metadata.version(name) for name in ("pydeps", "pyan3", "Markdown")
        },
        "node_tools": {
            name: json.loads((node_tools / "node_modules" / name / "package.json").read_text())[
                "version"
            ]
            for name in ("@mermaid-js/mermaid-cli", "@viz-js/viz")
        },
        "python": sys.version.split()[0],
    }
    with tempfile.TemporaryDirectory(prefix="drc-study-") as temp:
        scratch = Path(temp)
        info["graphs"] = generate_graphs(ROOT, destination, scratch, node_tools, inventory)
        for relative, source in DIAGRAMS.items():
            render_mermaid(source, destination / relative, scratch, node_tools, ROOT)
    (destination / "assets").mkdir(exist_ok=True)
    shutil.copyfile(TOOLING / "styles.css", destination / "assets/styles.css")
    sources = source_listings(ROOT, destination, inventory, sha)
    info["source_sha256"] = {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
    }
    findings = boundary_findings(inventory)
    info["boundary_findings"] = findings
    for section, pages in SECTIONS.items():
        for name in pages:
            path = f"{section}/{name}"
            content = (TOOLING / "content" / (path + ".md")).read_text(encoding="utf-8")
            body = render_content(content, inventory, ROOT)
            if name == "class-map":
                body += class_map(inventory, ROOT)
            if section == "04-module-guides":
                key = {"main-window": "ui.main_window", "ui-components": "ui.workers"}.get(
                    name, name.replace("-", "_")
                )
                body += symbol_index(inventory[key], inventory, ROOT)
            if name == "module-dependencies":
                body += "<h2>Import boundary scan at this commit</h2><ul>"
                body += "".join(f"<li>{html.escape(f)}</li>" for f in findings) or (
                    "<li>No forbidden imports found by the configured static checks.</li>"
                )
                body += "</ul><p>This check does not prove absence of dynamic imports, "
                body += (
                    "filesystem calls or domain policy inside widgets. Review source as well.</p>"
                )
            if name == "repository-map":
                md = "# Repository map\n\nOne offline source listing per selected text file.\n\n"
                md += "\n".join(f"- [{p}](../{listing_path(p)})" for p in sources)
                (destination / "01-overview/repository-map.md").write_text(md, encoding="utf-8")
                body += render_content(
                    md.replace("# Repository map", "## Offline source shelf"), inventory, ROOT
                )
            page(destination, path + ".html", name.replace("-", " ").title(), body, sha)
    cards = []
    for section, pages in SECTIONS.items():
        links = "".join(
            f'<li><a href="{section}/{p}.html">{p.replace("-", " ").title()}</a></li>'
            for p in pages
        )
        cards.append(
            f'<section class="card"><h2>{SECTION_NAMES[section]}</h2><ul>{links}</ul></section>'
        )
    home = (
        '<section class="hero"><p class="eyebrow">Read • trace • explain</p>'
        "<h1>Design Requirement Checker — Repository Study Pack</h1>"
        '<p class="lead">A source-grounded field guide to deterministic checking, '
        "Word ingestion, Qt concurrency and careful persistence.</p>"
        '<p><a href="06-learning-path/start-here.html">Start Here →</a></p></section>'
        f'<p class="meta">Repository: BenSun08/design-requirement-checker<br>Git SHA: {sha}'
        f"<br>Generated: {generated}<br>Working tree: "
        f"{'contains local changes' if dirty else 'clean'}</p>"
        "<p>Open these ordinary files directly in your browser. Everything needed for display "
        "is included. No server, installation, account or Internet connection is needed.</p>"
        '<div class="cards">' + "".join(cards) + "</div>"
        "<p>Diagrams are navigation aids, not execution traces. The source shelf and canonical "
        "documents preserve the evidence behind each explanation. This pack does not establish "
        "historical accuracy or Windows deployment readiness.</p>"
        '<p><a href="README.txt">Transfer instructions</a> · '
        '<a href="repository-info.json">Build provenance and validation</a></p>'
    )
    page(destination, "index.html", "Home", home, sha)
    (destination / "README.txt").write_text(
        "HOW TO USE\n\n1. Copy repository-study-pack.zip to the company computer.\n"
        "   The GitHub download may be named DesignRequirementChecker-repository-study-pack.zip.\n"
        "2. Extract the whole ZIP.\n3. Open repository-study-pack/index.html.\n"
        "4. No Internet connection is required.\n5. No Python/Node.js installation is required.\n\n"
        "Phone: GitHub Actions > Build Repository Study Pack > Run workflow.\n"
        "Download the one artifact ZIP; transfer that ZIP using WeCom / 企业微信.\n"
        "Keep all extracted folders together. Do not open index.html inside the ZIP preview.\n"
        "No LLM, API key, browser extension, or runtime server is used.\n\n"
        f"Generated from Git commit: {sha}\nGenerated UTC: {generated}\n"
        f"Local changes present at build time: {dirty}\n",
        encoding="utf-8",
    )
    metadata = destination / "repository-info.json"
    metadata.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    info["validation"] = validate_pack(destination, REQUIRED)
    metadata.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    validate_pack(destination)
    archive = destination.parent / "DesignRequirementChecker-repository.study-pack.zip"
    write_archive(destination, archive)
    size = archive.stat().st_size
    if size > 10 * 1024 * 1024:
        largest = sorted(destination.rglob("*"), key=lambda p: p.stat().st_size, reverse=True)[:10]
        raise ValueError(f"Pack exceeds 10 MiB transfer budget; largest files: {largest}")
    return {
        "pack": str(destination),
        "zip": str(archive),
        "zip_bytes": size,
        "git_sha": sha,
        **info["validation"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "repository-study-pack")
    parser.add_argument("--node-tools", type=Path, default=TOOLING)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = (
        validate_pack(args.output)
        if args.validate_only
        else build(args.output, args.node_tools.resolve())
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
