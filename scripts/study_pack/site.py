"""HTML rendering and one-root ZIP packaging; no client-side code."""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.study_pack.validate import SECTIONS

SECTION_NAMES = {
    "01-overview": "Architecture",
    "02-code-structure": "Code structure",
    "03-runtime-flows": "Runtime flows",
    "04-module-guides": "Module guides",
    "05-concepts": "Technical concepts",
    "06-learning-path": "Learning path",
}


def listing_path(path: str) -> str:
    return "sources/" + path.replace("/", "--") + ".html"


def source_link(reference: str, inventory: dict, root: Path) -> str:
    path, _, symbol = reference.partition("::")
    file = (root / path).resolve()
    if not file.is_relative_to(root.resolve()) or not file.is_file():
        raise ValueError(f"Missing source reference: {reference}")
    line = 1
    if symbol:
        module = next((v for v in inventory.values() if v["path"] == path), None)
        if module is None or symbol not in module["symbols"]:
            raise ValueError(f"Missing source symbol: {reference}")
        line = module["symbols"][symbol]["line"]
    label = path + (f" · {symbol}" if symbol else "")
    return f'<a href="../{listing_path(path)}#L{line}"><code>{html.escape(label)}</code></a>'


def page(pack: Path, relative: str, title: str, body: str, sha: str) -> None:
    target = pack / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    prefix = os.path.relpath(pack, target.parent).replace(os.sep, "/")
    nav = "".join(
        f'<a href="{prefix}/{section}/{pages[0]}.html">{SECTION_NAMES[section]}</a>'
        for section, pages in SECTIONS.items()
    )
    target.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)} · Repository Study Pack</title>"
        f'<link rel="stylesheet" href="{prefix}/assets/styles.css"></head><body>'
        f'<header><a class="brand" href="{prefix}/index.html">DRC / Repository Study Pack</a>'
        '<a href="#main">Skip to content</a></header>'
        f'<nav aria-label="Study sections">{nav}</nav><main id="main">{body}</main>'
        f"<footer>Offline edition · Git {html.escape(sha[:12])} · "
        f'<a href="{prefix}/index.html">Home</a></footer></body></html>',
        encoding="utf-8",
    )


def render_content(content: str, inventory: dict, root: Path) -> str:
    import markdown

    content = re.sub(r"\[\[([^\]]+)\]\]", lambda m: source_link(m[1], inventory, root), content)
    rendered = markdown.markdown(content, extensions=["tables", "fenced_code", "toc"])
    # Plain links let phone readers open and zoom each SVG without client-side code.
    return re.sub(
        r'<img ([^>]*?)src="([^"]+\.svg)"([^>]*?)>',
        lambda m: f'<a href="{m[2]}" aria-label="Open diagram at full size">{m[0]}</a>',
        rendered,
    )


def source_listings(root: Path, pack: Path, inventory: dict, sha: str) -> list[str]:
    # One HTML representation per file. No second raw source archive, fixtures or caches.
    paths = {v["path"] for v in inventory.values()}
    paths.update(p.relative_to(root).as_posix() for p in (root / "tests").glob("*.py"))
    paths.update(f"docs/{name}.md" for name in ("constitution", "spec", "plan", "tasks"))
    paths.update({"AGENTS.md", "README.md", "pyproject.toml", "LICENSE"})
    paths.update(p.relative_to(root).as_posix() for p in (root / ".github/workflows").glob("*.yml"))
    for path in sorted(paths):
        lines = (root / path).read_text(encoding="utf-8").splitlines()
        listing = "\n".join(
            f'<span class="line" id="L{i}"><a href="#L{i}">{i:4}</a> {html.escape(line)}</span>'
            for i, line in enumerate(lines, 1)
        )
        page(
            pack,
            listing_path(path),
            path,
            f"<h1>{html.escape(path)}</h1><p>Snapshot at {sha}. "
            "Use your browser Find command to locate a symbol. "
            "This is escaped source text, not executable page content.</p>"
            f'<pre class="source"><code>{listing}</code></pre>',
            sha,
        )
    return sorted(paths)


def class_map(inventory: dict, root: Path) -> str:
    parts = ["<h2>Classes and value types (generated from AST)</h2>"]
    for module, info in inventory.items():
        classes = [(n, s) for n, s in info["symbols"].items() if s["kind"] == "class"]
        if not classes:
            continue
        parts.append(f"<h3>{html.escape(module)}</h3><dl>")
        for name, symbol in classes:
            bases = ", ".join(symbol["bases"]) or "object"
            doc = symbol["doc"].split("\n\n")[0] or "See source for construction and methods."
            parts.append(
                f"<dt>{source_link(info['path'] + '::' + name, inventory, root)} "
                f"({html.escape(bases)})</dt><dd>{html.escape(doc)}</dd>"
            )
        parts.append("</dl>")
    return "".join(parts)


def symbol_index(info: dict, inventory: dict, root: Path) -> str:
    links = [source_link(info["path"] + "::" + name, inventory, root) for name in info["symbols"]]
    return (
        "<details><summary>All classes, functions and methods in this module</summary><ul>"
        + ("".join(f"<li>{link}</li>" for link in links))
        + "</ul></details>"
    )


def write_archive(pack: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(pack.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Symlink not allowed: {path}")
            if path.is_file():
                archive.write(path, pack.name + "/" + path.relative_to(pack).as_posix())
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
    return destination
