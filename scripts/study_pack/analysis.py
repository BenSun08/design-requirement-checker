"""Static inventory and isolated analysis subprocesses; never imports the application."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGE = "design_requirement_checker"


def run(args: list[str], root: Path) -> str:
    result = subprocess.run(
        args, cwd=root, text=True, capture_output=True, timeout=180, check=False
    )
    if result.returncode:
        raise RuntimeError(f"Build tool failed: {args[0]}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def inspect_sources(root: Path) -> dict:
    inventory = {}
    source = root / "src" / PACKAGE
    for path in sorted(source.rglob("*.py")):
        module = path.relative_to(source).with_suffix("").as_posix().replace("/", ".")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        symbols = {}

        def visit(node, prefix=""):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = prefix + child.name
                    symbols[name] = {
                        "line": child.lineno,
                        "end": child.end_lineno,
                        "kind": "class" if isinstance(child, ast.ClassDef) else "function",
                        "doc": ast.get_docstring(child) or "",
                        "bases": [ast.unparse(b) for b in child.bases]
                        if isinstance(child, ast.ClassDef)
                        else [],
                    }
                    visit(child, name + ".")
                else:
                    visit(child, prefix)

        visit(tree)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                name = node.module or ""
                if node.level:
                    parts = (PACKAGE + "." + module).split(".")[: -node.level]
                    name = ".".join([*parts, name]).rstrip(".")
                imports.add(name)
                for alias in node.names:
                    candidate = name + "." + alias.name
                    if (root / "src" / (candidate.replace(".", "/") + ".py")).exists():
                        imports.add(candidate)
        inventory[module] = {
            "path": path.relative_to(root).as_posix(),
            "symbols": symbols,
            "imports": sorted(imports),
            "doc": ast.get_docstring(tree) or "",
        }
    return inventory


def boundary_findings(inventory: dict) -> list[str]:
    """Conservative import checks, with documented exceptions reported explicitly."""
    findings = []
    allowed = {
        "domain": set(),
        "matching": {"domain"},
        "docx_adapter": {"domain"},
        "baseline_store": {"domain"},
        "application": {"domain", "matching", "docx_adapter", "baseline_store"},
    }
    for module, info in inventory.items():
        for dependency in info["imports"]:
            short = dependency.removeprefix(PACKAGE + ".")
            if dependency.startswith(PACKAGE + "."):
                if module in allowed and short not in allowed[module]:
                    findings.append(f"{module} → {short}: outside documented internal boundary")
                if module.startswith("ui.") and short in {"matching", "docx_adapter"}:
                    findings.append(f"{module} → {short}: UI bypasses application orchestration")
            if module.startswith("ui.") and dependency == PACKAGE + ".baseline_store":
                findings.append(
                    f"{module} → baseline_store: direct storage path/error coupling; "
                    "review against UI → Application layering (no direct JSON I/O inferred)"
                )
            if dependency.split(".")[0] in {"docx", "lxml"} and module != "docx_adapter":
                findings.append(f"{module} → {dependency}: Word internals outside adapter")
            if module in {"domain", "matching"} and dependency.split(".")[0] in {
                "PySide6",
                "pathlib",
                "os",
                "io",
                "json",
                "sqlite3",
                "socket",
                "requests",
                "urllib",
                "http",
                "shutil",
                "tempfile",
            }:
                findings.append(f"{module} → {dependency}: I/O or UI import in pure layer")
            if module == "application" and dependency.startswith("PySide6"):
                findings.append(f"{module} → {dependency}: Qt dependency in application")
    return findings


def render_dot(dot: str, output: Path, scratch: Path, node_tools: Path, root: Path) -> None:
    source = scratch / (output.stem + ".dot")
    source.write_text(dot, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "node",
            str(Path(__file__).with_name("render_dot.mjs")),
            str(node_tools / "node_modules/@viz-js/viz/dist/viz.js"),
            str(source),
            str(output),
        ],
        root,
    )
    # Graphviz's DTD URL is metadata, but remove it to keep the shipped SVG self-contained.
    svg = output.read_text(encoding="utf-8")
    svg = re.sub(r"<!DOCTYPE.*?>", "", svg, flags=re.S)
    output.write_text(svg, encoding="utf-8")


def dot_graph(edges: set[tuple[str, str]], nodes: set[str]) -> str:
    lines = [
        'digraph G { rankdir=LR; bgcolor="transparent"; pad="0.3";',
        'node [shape=box, style="rounded,filled", fillcolor="#eaf2f5", '
        'color="#28758a", fontname="Arial", fontsize=12];',
        'edge [color="#537789", arrowsize=0.7];',
    ]
    lines.extend(f"{json.dumps(n)};" for n in sorted(nodes))
    lines.extend(f"{json.dumps(a)} -> {json.dumps(b)};" for a, b in sorted(edges))
    return "\n".join([*lines, "}"])


def generate_graphs(root: Path, pack: Path, scratch: Path, node_tools: Path, inventory: dict):
    deps = json.loads(
        run(
            [
                sys.executable,
                "-m",
                "pydeps",
                "src/" + PACKAGE,
                "--no-config",
                "--noshow",
                "--no-output",
                "--show-deps",
                "--only",
                PACKAGE,
            ],
            root,
        )
    )
    nodes = {m for m in inventory if not m.endswith("__init__")}
    edges = set()
    for name, info in deps.items():
        short = name.removeprefix(PACKAGE + ".")
        for dependency in info.get("imports", []):
            target = dependency.removeprefix(PACKAGE + ".")
            if short in nodes and target in nodes:
                edges.add((short, target))
    if not {("application", "matching"), ("matching", "domain")} <= edges:
        raise ValueError("Pydeps did not resolve expected project imports")
    render_dot(
        dot_graph(edges, nodes),
        pack / "02-code-structure/module-dependencies.svg",
        scratch,
        node_tools,
        root,
    )

    # Pyan's uses edges are an approximation, including type references.
    # Keep only callable symbols, then partition UI by lifecycle concern.
    focuses = {
        "matching": ["matching"],
        "docx-adapter": ["docx_adapter"],
        "application": ["application"],
        "baseline-store": ["baseline_store"],
        "ui-worker": ["ui.main_window", "ui.workers"],
    }
    ui_names = {
        "_start_import",
        "_wire_worker",
        "_on_thread_finished",
        "_finish_operation",
        "_on_import_finished",
        "show_import_outcome",
        "_on_run_clicked",
        "_on_cancel_clicked",
        "_on_verification_finished",
        "_on_worker_failed",
        "closeEvent",
        "start_verification",
        "complete_verification",
        "cancel_verification",
        "fail_verification",
        "set_document",
        "run",
        "ImportWorker",
        "VerificationWorker",
    }
    graph_counts = {}
    for focus, modules in focuses.items():
        output = run(
            [
                sys.executable,
                "-m",
                "pyan",
                *[inventory[m]["path"] for m in modules],
                "--root",
                "src",
                "--no-defines",
                "--uses",
                "--dot",
            ],
            root,
        )
        symbol_ids = {}
        for module in modules:
            for name in inventory[module]["symbols"]:
                if focus == "ui-worker" and name.split(".")[-1] not in ui_names:
                    continue
                identifier = (PACKAGE + "." + module + "." + name).replace(".", "__")
                symbol_ids[identifier] = name
        graph_edges = {
            (symbol_ids[a], symbol_ids[b])
            for a, b in re.findall(r'"([^"]+)" -> "([^"]+)"', output)
            if a in symbol_ids and b in symbol_ids
        }
        if not graph_edges:
            raise ValueError(f"No callable relationships extracted for {focus}")
        graph_nodes = {n for edge in graph_edges for n in edge}
        filename = "call-graph.svg" if focus == "application" else f"calls-{focus}.svg"
        render_dot(
            dot_graph(graph_edges, graph_nodes),
            pack / "02-code-structure" / filename,
            scratch,
            node_tools,
            root,
        )
        graph_counts[focus] = {"nodes": len(graph_nodes), "edges": len(graph_edges)}
    return {"module_edges": sorted(edges), "call_graphs": graph_counts}


def render_mermaid(source: str, output: Path, scratch: Path, node_tools: Path, root: Path):
    mmd = scratch / (output.stem + ".mmd")
    mmd.write_text(source, encoding="utf-8")
    config = scratch / "mermaid.json"
    config.write_text(
        json.dumps(
            {
                "theme": "neutral",
                "htmlLabels": False,
                "fontFamily": "Arial, sans-serif",
                "flowchart": {"htmlLabels": False},
                "securityLevel": "strict",
            }
        ),
        encoding="utf-8",
    )
    puppeteer = scratch / "puppeteer.json"
    settings = {"args": ["--no-sandbox"]}
    if os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
        settings["executablePath"] = os.environ["PUPPETEER_EXECUTABLE_PATH"]
    puppeteer.write_text(json.dumps(settings), encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "node",
            str(node_tools / "node_modules/@mermaid-js/mermaid-cli/src/cli.js"),
            "-i",
            str(mmd),
            "-o",
            str(output),
            "-c",
            str(config),
            "-p",
            str(puppeteer),
            "-b",
            "transparent",
        ],
        root,
    )
