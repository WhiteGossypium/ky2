"""Описание графа на языке диаграмм Mermaid.

Пример результата:
    flowchart LR
        n0["A"]
        n1["B"]
        n0 --> n1
Вершина получает короткий номер n0, n1, ...; имя пакета - подпись.
Ребро, замыкающее цикл, рисуется пунктиром.
"""

import html
import os
from typing import Dict, List, Set, Tuple

from src.graph import Graph

MERMAID_SCRIPT = (
    "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
)
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>body {{ font-family: sans-serif; margin: 16px; }}</style>
</head>
<body>
<h1>{title}</h1>
<pre class="mermaid">
{diagram}
</pre>
<script src="{script}"></script>
<script>
mermaid.initialize({{startOnLoad: true, maxTextSize: 1000000,
                    maxEdges: 10000}});
</script>
</body>
</html>
"""


def label(text: str) -> str:
    """Подпись вершины в кавычках; кавычки внутри заменяются."""
    return '"' + text.replace('"', "#quot;") + '"'


def closing_edges(graph: Graph) -> Set[Tuple[str, str]]:
    """Рёбра, которые замыкают найденные циклы."""
    return {(cycle[-2], cycle[-1]) for cycle in graph.cycles}


def node_lines(graph: Graph, ids: Dict[str, str]) -> List[str]:
    """Строки с вершинами графа."""
    lines = []
    for node, name in ids.items():
        text = node + " (not loaded)" if node in graph.problems else node
        lines.append(f"    {name}[{label(text)}]")
    return lines


def edge_lines(graph: Graph, ids: Dict[str, str]) -> List[str]:
    """Строки с рёбрами; ребро цикла - пунктир с подписью."""
    cycle_edges = closing_edges(graph)
    lines = []
    for parent, children in graph.edges.items():
        for child in children:
            arrow = "-. cycle .->" if (parent, child) in cycle_edges else "-->"
            lines.append(f"    {ids[parent]} {arrow} {ids[child]}")
    return lines


def style_lines(graph: Graph, ids: Dict[str, str]) -> List[str]:
    """Оформление: корень выделен, незагруженные пакеты серые."""
    lines = [
        "    classDef root fill:#cfe8ff,stroke:#1f6feb,stroke-width:2px",
        "    classDef problem fill:#eeeeee,stroke:#999999,"
        "stroke-dasharray:4 3",
        f"    class {ids[graph.root]} root",
    ]
    failed = [ids[node] for node in graph.problems if node in ids]
    if failed:
        lines.append(f"    class {','.join(failed)} problem")
    return lines


def comment_lines(graph: Graph) -> List[str]:
    """Комментарии Mermaid (%%): итоги, циклы, ошибки, фильтр."""
    lines = [
        f"%% root: {graph.root}",
        f"%% packages: {len(graph.nodes())}, edges: {graph.edge_count()}",
    ]
    lines.extend("%% cycle: " + " -> ".join(cycle) for cycle in graph.cycles)
    lines.extend(
        f"%% not loaded: {node}: {reason}"
        for node, reason in graph.problems.items()
    )
    if graph.excluded:
        lines.append("%% excluded by filter: " + ", ".join(graph.excluded))
    return lines


def to_mermaid(graph: Graph) -> str:
    """Возвращает полное описание графа на языке Mermaid."""
    ids = {node: f"n{index}" for index, node in enumerate(graph.nodes())}
    lines = ["flowchart LR"] + comment_lines(graph)
    lines += node_lines(graph, ids) + edge_lines(graph, ids)
    lines += style_lines(graph, ids)
    return "\n".join(lines) + "\n"


def html_page(diagram: str, title: str) -> str:
    """Страница, которая рисует диаграмму в браузере."""
    return PAGE.format(
        title=html.escape(title),
        diagram=html.escape(diagram),
        script=MERMAID_SCRIPT,
    )


def save_diagram(path: str, diagram: str, title: str) -> None:
    """Сохраняет диаграмму в .mmd или в страницу .html."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    text = html_page(diagram, title) if path.endswith(".html") else diagram
    with open(path, "w", encoding="utf-8") as target:
        target.write(text)