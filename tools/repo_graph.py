"""Build and query a deterministic graph of this repository's Python code."""

from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "architecture" / "repo_graph.json"
DEFAULT_REPORT = ROOT / "architecture" / "repo_graph_report.md"
EXCLUDED_DIRS = {
    ".git",
    ".agent",
    ".agents",
    ".codex",
    ".uv-cache",
    ".uv-tools",
    "__pycache__",
    "application_drafts",
    "resumes_vault",
}


def module_name(path: Path) -> str:
    return path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")


def python_sources() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.py")
        if not any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts)
    )


class GraphVisitor(ast.NodeVisitor):
    def __init__(self, module: str, rel_path: str, local_modules: set[str]) -> None:
        self.module = module
        self.rel_path = rel_path
        self.local_modules = local_modules
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.parents = [f"module:{module}"]
        self.calls: list[tuple[str, str, int]] = []
        self.symbol_names: list[tuple[str, str, int, str]] = []
        self.nodes.append(
            {
                "id": f"module:{module}",
                "kind": "module",
                "name": module,
                "path": rel_path,
                "line": 1,
            }
        )

    def _visit_scope(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        parent = self.parents[-1]
        qualified = f"{self.module}.{node.name}"
        if parent.startswith("symbol:"):
            qualified = f"{parent.removeprefix('symbol:')}.{node.name}"
        identifier = f"symbol:{qualified}"
        self.nodes.append(
            {
                "id": identifier,
                "kind": kind,
                "name": node.name,
                "qualified_name": qualified,
                "path": self.rel_path,
                "line": node.lineno,
            }
        )
        self.edges.append(
            {
                "source": parent,
                "target": identifier,
                "relation": "contains",
                "provenance": "EXTRACTED",
                "path": self.rel_path,
                "line": node.lineno,
                "evidence": f"{kind} declaration {node.name}",
            }
        )
        self.symbol_names.append((node.name, identifier, node.lineno, kind))
        self.parents.append(identifier)
        self.generic_visit(node)
        self.parents.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, "function")

    def visit_Import(self, node: ast.Import) -> None:
        source = f"module:{self.module}"
        for alias in node.names:
            imported = alias.name.split(".", 1)[0]
            if imported in self.local_modules:
                target = f"module:{imported}"
                self.edges.append(
                    {
                        "source": source,
                        "target": target,
                        "relation": "imports",
                        "provenance": "EXTRACTED",
                        "path": self.rel_path,
                        "line": node.lineno,
                        "evidence": f"import {alias.name}",
                    }
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.level == 0 and node.module in self.local_modules:
            self.edges.append(
                {
                    "source": f"module:{self.module}",
                    "target": f"module:{node.module}",
                    "relation": "imports",
                    "provenance": "EXTRACTED",
                    "path": self.rel_path,
                    "line": node.lineno,
                    "evidence": f"from {node.module} import names",
                }
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr
        else:
            called_name = ""
        if called_name:
            self.calls.append((self.parents[-1], called_name, node.lineno))
        self.generic_visit(node)


def build_graph() -> dict[str, Any]:
    sources = python_sources()
    modules = {module_name(path) for path in sources}
    visitors: list[GraphVisitor] = []
    parse_errors: list[dict[str, str]] = []

    for path in sources:
        relative = path.relative_to(ROOT).as_posix()
        module = module_name(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            parse_errors.append({"path": relative, "error": str(exc)})
            continue
        visitor = GraphVisitor(module, relative, modules)
        visitor.visit(tree)
        visitors.append(visitor)

    definitions: dict[str, list[tuple[str, str, int, str]]] = defaultdict(list)
    for visitor in visitors:
        for name, identifier, line, kind in visitor.symbol_names:
            definitions[name].append((identifier, visitor.rel_path, line, kind))

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for visitor in visitors:
        nodes.extend(visitor.nodes)
        edges.extend(visitor.edges)
        for caller, called_name, line in visitor.calls:
            candidates = definitions.get(called_name, [])
            if len(candidates) != 1:
                continue
            target, target_path, target_line, target_kind = candidates[0]
            edges.append(
                {
                    "source": caller,
                    "target": target,
                    "relation": "calls",
                    "provenance": "INFERRED",
                    "path": visitor.rel_path,
                    "line": line,
                    "evidence": (
                        f"call expression {called_name} at {visitor.rel_path}:{line}; "
                        f"unique local {target_kind} definition at {target_path}:{target_line}"
                    ),
                }
            )

    nodes.sort(key=lambda item: item["id"])
    edges.sort(key=lambda item: (item["source"], item["relation"], item["target"], item["line"]))
    return {
        "schema_version": 1,
        "builder": "tools/repo_graph.py",
        "scope": "Python source files outside data, generated artifact, and agent skill directories",
        "nodes": nodes,
        "edges": edges,
        "parse_errors": parse_errors,
    }


def render_report(graph: dict[str, Any]) -> str:
    modules = [node for node in graph["nodes"] if node["kind"] == "module"]
    symbols = [node for node in graph["nodes"] if node["kind"] != "module"]
    imports = sum(edge["relation"] == "imports" for edge in graph["edges"])
    calls = sum(edge["relation"] == "calls" for edge in graph["edges"])
    containment = sum(edge["relation"] == "contains" for edge in graph["edges"])
    lines = [
        "# Repository Code Graph",
        "",
        "Generated locally from Python AST using the standard library. No code is uploaded.",
        "Import edges are extracted from syntax. Call edges are inferred only when a call name maps to one unique local definition.",
        "The graph excludes candidate drafts, resume artifacts, and `.agent` skill files.",
        "",
        "## Summary",
        "",
        f"- Python modules: {len(modules)}",
        f"- Classes and functions: {len(symbols)}",
        f"- Import edges: {imports}",
        f"- Resolved call edges: {calls}",
        f"- Containment edges: {containment}",
        f"- Parse errors: {len(graph['parse_errors'])}",
        "",
        "## Modules",
        "",
    ]
    lines.extend(f"- `{node['name']}` (`{node['path']}`)" for node in modules)
    if graph["parse_errors"]:
        lines.extend(["", "## Parse errors", ""])
        lines.extend(f"- `{item['path']}`: {item['error']}" for item in graph["parse_errors"])
    return "\n".join(lines) + "\n"


def read_graph(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_nodes(graph: dict[str, Any], term: str) -> list[dict[str, Any]]:
    needle = term.casefold()
    matches = [
        node
        for node in graph["nodes"]
        if needle in node["name"].casefold()
        or needle in node.get("qualified_name", "").casefold()
        or needle in node["path"].casefold()
        or needle == node["id"].casefold()
    ]
    return sorted(matches, key=lambda node: (node["kind"], node["id"]))


def explain(graph: dict[str, Any], term: str) -> None:
    matches = find_nodes(graph, term)
    if not matches:
        print(f"No graph node matched: {term}")
        return
    for node in matches[:20]:
        print(f"{node['id']} [{node['kind']}] {node['path']}:{node['line']}")
        for edge in graph["edges"]:
            if edge["source"] == node["id"] or edge["target"] == node["id"]:
                arrow = "->" if edge["source"] == node["id"] else "<-"
                other = edge["target"] if arrow == "->" else edge["source"]
                print(f"  {arrow} {other} [{edge['relation']}, {edge['provenance']}] {edge['path']}:{edge['line']}")
                print(f"     {edge['evidence']}")


def shortest_path(graph: dict[str, Any], start_term: str, end_term: str) -> None:
    starts = find_nodes(graph, start_term)
    ends = {node["id"] for node in find_nodes(graph, end_term)}
    if not starts or not ends:
        print("Start or end node was not found")
        return
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for edge in graph["edges"]:
        adjacency[edge["source"]].append((edge["target"], edge))
        adjacency[edge["target"]].append((edge["source"], edge))
    for start in starts:
        pending = deque([start["id"]])
        previous: dict[str, tuple[str, dict[str, Any]] | None] = {start["id"]: None}
        reached = None
        while pending:
            current = pending.popleft()
            if current in ends:
                reached = current
                break
            for neighbor, edge in adjacency[current]:
                if neighbor not in previous:
                    previous[neighbor] = (current, edge)
                    pending.append(neighbor)
        if reached is None:
            continue
        path: list[tuple[str, dict[str, Any]]] = []
        cursor = reached
        while previous[cursor] is not None:
            parent, edge = previous[cursor]  # type: ignore[misc]
            path.append((cursor, edge))
            cursor = parent
        path.reverse()
        print(start["id"])
        for target, edge in path:
            print(f"  --{edge['relation']} [{edge['provenance']}]--> {target}")
        return
    print(f"No path found between {start_term} and {end_term}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and query a local Python code graph")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build JSON graph and Markdown summary")
    build_parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    build_parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    query_parser = subparsers.add_parser("query", help="Find graph nodes by name or path")
    query_parser.add_argument("term")
    query_parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    explain_parser = subparsers.add_parser("explain", help="Show a node and its explained edges")
    explain_parser.add_argument("term")
    explain_parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    path_parser = subparsers.add_parser("path", help="Find a shortest path between matching nodes")
    path_parser.add_argument("start")
    path_parser.add_argument("end")
    path_parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    args = parser.parse_args()

    if args.command == "build":
        graph = build_graph()
        args.graph.parent.mkdir(parents=True, exist_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.graph.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        args.report.write_text(render_report(graph), encoding="utf-8")
        print(f"Wrote {len(graph['nodes'])} nodes and {len(graph['edges'])} edges to {args.graph}")
        print(f"Parse errors: {len(graph['parse_errors'])}")
        return 1 if graph["parse_errors"] else 0

    graph = read_graph(args.graph)
    if args.command == "query":
        matches = find_nodes(graph, args.term)
        for node in matches[:50]:
            print(f"{node['id']} [{node['kind']}] {node['path']}:{node['line']}")
        if not matches:
            print("No graph nodes matched")
    elif args.command == "explain":
        explain(graph, args.term)
    else:
        shortest_path(graph, args.start, args.end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
