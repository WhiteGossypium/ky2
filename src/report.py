"""Текстовый отчёт о графе зависимостей."""

from typing import List

from src.graph import Graph


def graph_lines(graph: Graph) -> List[str]:
    """Строки отчёта: вершины с зависимостями, циклы, ошибки, фильтр."""
    lines = [
        f"root: {graph.root}",
        f"packages: {len(graph.nodes())}, edges: {graph.edge_count()}",
    ]
    for node, children in graph.edges.items():
        lines.append(f"{node} -> {', '.join(children) or '(none)'}")
    for cycle in graph.cycles:
        lines.append("cycle: " + " -> ".join(cycle))
    for node, reason in graph.problems.items():
        lines.append(f"not loaded: {node}: {reason}")
    if graph.excluded:
        lines.append("excluded by filter: " + ", ".join(graph.excluded))
    return lines