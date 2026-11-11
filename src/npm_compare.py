"""Сравнение графа программы со штатным инструментом npm.

Запуск: python -m src.npm_compare [файл_настроек.csv]

Во временной папке выполняется настоящий npm install пакета, затем
npm ls --all показывает дерево установленных пакетов. Дерево npm
и граф программы сравниваются по вершинам и рёбрам.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from typing import List, Set, Tuple

from src.errors import ToolError
from src.graph import Graph
from src.main import DEFAULT_CONFIG, graph_for
from src.settings import Settings, load_settings

Edges = Set[Tuple[str, str]]
FAILURE = 1
INSTALL_OPTIONS = ["--ignore-scripts", "--no-audit", "--no-fund"]
PROJECT = '{"name": "npm-compare", "version": "1.0.0", "private": true}'


def npm_run(folder: str, arguments: List[str]) -> str:
    """Выполняет команду npm в папке и возвращает её вывод."""
    npm = shutil.which("npm")
    if npm is None:
        raise ToolError("npm is not installed (https://nodejs.org)")
    result = subprocess.run(
        [npm] + arguments, cwd=folder, capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 and not result.stdout.strip():
        raise ToolError(f"npm {arguments[0]} failed: {result.stderr}")
    return result.stdout


def npm_tree(settings: Settings, folder: str) -> Tuple[dict, str]:
    """Устанавливает пакет и возвращает дерево npm ls (JSON и текст)."""
    with open(f"{folder}/package.json", "w", encoding="utf-8") as target:
        target.write(PROJECT)
    wanted = f"{settings.package}@{settings.version}"
    registry = f"--registry={settings.repository}"
    npm_run(folder, ["install", wanted, registry] + INSTALL_OPTIONS)
    data = json.loads(npm_run(folder, ["ls", "--all", "--json"]))
    return data, npm_run(folder, ["ls", "--all"])


def tree_edges(node: dict, parent: str, edges: Edges) -> None:
    """Собирает рёбра родитель -> зависимость из дерева npm ls."""
    for name, child in (node.get("dependencies") or {}).items():
        key = f"{name}@{child.get('version', '?')}"
        if (parent, key) in edges:
            continue
        edges.add((parent, key))
        tree_edges(child, key, edges)


def npm_edges(data: dict, package: str, version: str) -> Edges:
    """Рёбра дерева npm, начиная с установленного пакета."""
    top = (data.get("dependencies") or {}).get(package)
    if top is None:
        raise ToolError(f"npm did not install {package}")
    edges: Edges = set()
    tree_edges(top, f"{package}@{top.get('version', version)}", edges)
    return edges


def graph_edges(graph: Graph) -> Edges:
    """Рёбра графа программы."""
    return {
        (parent, child)
        for parent, children in graph.edges.items()
        for child in children
    }


def nodes_of(edges: Edges, root: str) -> Set[str]:
    """Все вершины, встречающиеся в рёбрах, и корень."""
    return {root} | {node for edge in edges for node in edge}


def difference_lines(ours: Edges, theirs: Edges, root: str) -> List[str]:
    """Строки сравнения вершин и рёбер."""
    our_nodes, npm_nodes = nodes_of(ours, root), nodes_of(theirs, root)
    lines = [
        f"tool: packages {len(our_nodes)}, edges {len(ours)}",
        f"npm:  packages {len(npm_nodes)}, edges {len(theirs)}",
        "only in tool: " + (", ".join(sorted(our_nodes - npm_nodes)) or "-"),
        "only in npm: " + (", ".join(sorted(npm_nodes - our_nodes)) or "-"),
    ]
    lines.extend(f"edge only in tool: {a} -> {b}" for a, b in
                 sorted(ours - theirs))
    lines.extend(f"edge only in npm: {a} -> {b}" for a, b in
                 sorted(theirs - ours))
    return lines


def compare(settings: Settings) -> List[str]:
    """Строит оба результата и возвращает отчёт о сравнении."""
    if settings.test_mode:
        raise ToolError("npm cannot install packages of a test repository")
    graph = graph_for(settings)
    folder = tempfile.mkdtemp(prefix="npm-compare-")
    try:
        data, text = npm_tree(settings, folder)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    theirs = npm_edges(data, settings.package, settings.version)
    lines = ["npm ls --all:", text.rstrip(), ""]
    return lines + difference_lines(graph_edges(graph), theirs, graph.root)


def main() -> None:
    """Запускает сравнение с параметрами командной строки."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    try:
        lines = compare(load_settings(path))
    except (ToolError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(FAILURE)
    print("\n".join(lines))


if __name__ == "__main__":
    main()