"""Fail closed on active content, broken links, escaped paths and external resources."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SECTIONS = {
    "01-overview": ("architecture", "repository-map"),
    "02-code-structure": ("module-dependencies", "call-graph", "class-map"),
    "03-runtime-flows": (
        "startup",
        "docx-import",
        "verification",
        "baseline-persistence",
        "qt-threading",
        "shutdown",
    ),
    "04-module-guides": (
        "domain",
        "matching",
        "docx-adapter",
        "application",
        "baseline-store",
        "main-window",
        "ui-components",
    ),
    "05-concepts": (
        "architecture-principles",
        "deterministic-matching",
        "docx-ooxml",
        "qt-threading",
        "persistence",
        "testing-strategy",
    ),
    "06-learning-path": ("start-here", "reading-order", "exercises", "interview-questions"),
}
REQUIRED = {
    "index.html",
    "README.txt",
    "repository-info.json",
    "assets/styles.css",
    "01-overview/architecture.svg",
    "01-overview/repository-map.md",
    "02-code-structure/module-dependencies.svg",
    "02-code-structure/call-graph.svg",
    *(f"{section}/{page}.html" for section, pages in SECTIONS.items() for page in pages),
    *(
        f"02-code-structure/calls-{name}.svg"
        for name in ("matching", "docx-adapter", "baseline-store", "ui-worker")
    ),
    *(f"assets/{name}.svg" for name in SECTIONS["03-runtime-flows"]),
}


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.styles = []
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "iframe", "object", "embed", "base", "form", "foreignobject"}:
            raise ValueError(f"Active/unsupported element: {tag}")
        self.in_style = tag == "style"
        for key, value in attrs:
            if key.lower().startswith("on") or key.lower() in {"srcdoc", "srcset", "http-equiv"}:
                raise ValueError(f"Active/unsupported attribute: {key}")
            if key == "id":
                if value in self.ids:
                    raise ValueError(f"Duplicate anchor: {value}")
                self.ids.add(value)
            if key in {"href", "src", "xlink:href", "poster", "data", "action"}:
                self.links.append(value or "")
            if key == "style":
                self.styles.append(value or "")

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.styles.append(data)


def css_links(css: str) -> list[str]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if re.search(r"@import|expression\s*\(|javascript:|\\", css, re.I):
        raise ValueError("External/active or escaped CSS is not supported")
    return [v.strip().strip("\"'") for v in re.findall(r"url\s*\((.*?)\)", css, re.I)]


def validate_pack(pack: Path, required: set[str] | None = None) -> dict:
    pack = pack.resolve()
    missing = [p for p in (REQUIRED if required is None else required) if not (pack / p).is_file()]
    if missing:
        raise ValueError(f"Missing required files: {sorted(missing)}")
    references = {}
    ids = {}
    count = 0
    for path in sorted(pack.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink not allowed: {path}")
        if not path.is_file():
            continue
        count += 1
        if path.suffix not in {".html", ".svg", ".css", ".md", ".txt", ".json"}:
            raise ValueError(f"Unexpected pack file: {path}")
        data = path.read_text(encoding="utf-8")
        refs = []
        anchors = set()
        if path.suffix == ".html":
            parser = References()
            parser.feed(data)
            refs.extend(parser.links)
            anchors = parser.ids
            for style in parser.styles:
                refs.extend(css_links(style))
        elif path.suffix == ".css":
            refs.extend(css_links(data))
        elif path.suffix == ".svg":
            if "<!DOCTYPE" in data or "<!ENTITY" in data:
                raise ValueError("SVG must not declare external entities or DTDs")
            tree = ET.fromstring(data)
            if tree.tag != "{http://www.w3.org/2000/svg}svg":
                raise ValueError("Invalid SVG root")
            for element in tree.iter():
                tag = element.tag.rsplit("}", 1)[-1].lower()
                if tag in {"script", "foreignobject", "animate", "set"}:
                    raise ValueError(f"Active SVG element: {tag}")
                for key, value in element.attrib.items():
                    key = key.rsplit("}", 1)[-1]
                    if key.lower().startswith("on"):
                        raise ValueError(f"Active SVG attribute: {key}")
                    if key == "id":
                        anchors.add(value)
                    if key in {"href", "src"}:
                        refs.append(value)
                    if "url(" in value or key == "style":
                        refs.extend(css_links(value))
                if tag == "style":
                    refs.extend(css_links(element.text or ""))
        references[path] = refs
        ids[path] = anchors
    for source, refs in references.items():
        for ref in refs:
            parsed = urlsplit(ref.strip())
            if (
                parsed.scheme
                or parsed.netloc
                or parsed.query
                or "\\" in ref
                or parsed.path.startswith("/")
                or "localhost" in ref.lower()
            ):
                raise ValueError(f"Non-local reference in {source.name}: {ref}")
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not target.is_relative_to(pack) or not target.is_file():
                raise ValueError(f"Broken/escaping link in {source.name}: {ref}")
            if parsed.fragment and unquote(parsed.fragment) not in ids.get(target, set()):
                raise ValueError(f"Broken anchor in {source.name}: {ref}")
    return {
        "files": count,
        "local_links": sum(map(len, references.values())),
        "link_validation": "PASS",
        "offline_dependency_scan": "PASS",
    }
