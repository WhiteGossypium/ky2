"""Тесты описания графа на языке Mermaid и сравнения с npm."""

import unittest

from src.errors import ToolError
from src.graph import Graph, build_graph
from src.mermaid import html_page, label, to_mermaid
from src.npm_compare import difference_lines, npm_edges
from src.sources import FileSource


def cycle_graph() -> Graph:
    """Граф A -> B -> A, B -> C, C не описан."""
    return build_graph(FileSource({"A": ["B"], "B": ["A", "C"]}), "A")


class MermaidTest(unittest.TestCase):
    """Проверяет текст диаграммы."""

    def test_structure(self) -> None:
        """Заголовок, вершины, рёбра и выделение корня."""
        lines = to_mermaid(cycle_graph()).splitlines()
        self.assertEqual(lines[0], "flowchart LR")
        self.assertIn('    n0["A"]', lines)
        self.assertIn("    n0 --> n1", lines)
        self.assertIn("    class n0 root", lines)

    def test_cycle_and_problem(self) -> None:
        """Ребро цикла - пунктир, незагруженный пакет - серый."""
        text = to_mermaid(cycle_graph())
        self.assertIn("    n1 -. cycle .-> n0\n", text)
        self.assertIn('n2["C (not loaded)"]', text)
        self.assertIn("    class n2 problem\n", text)
        self.assertIn("%% cycle: A -> B -> A\n", text)

    def test_label_and_page(self) -> None:
        """Кавычки в подписи заменяются, страница экранирует текст."""
        self.assertEqual(label('a"b'), '"a#quot;b"')
        page = html_page("flowchart LR\n    n0 --> n1\n", "x<y")
        self.assertIn("n0 --&gt; n1", page)
        self.assertIn("<title>x&lt;y</title>", page)
        self.assertIn("mermaid.min.js", page)


class CompareTest(unittest.TestCase):
    """Проверяет разбор дерева npm ls и отчёт о различиях."""

    def test_npm_edges(self) -> None:
        """Рёбра собираются по всему дереву."""
        data = {"dependencies": {"web": {"version": "1.0.0", "dependencies": {
            "low": {"version": "2.0.0", "dependencies": {
                "tiny": {"version": "0.1.0"}}}}}}}
        self.assertEqual(
            npm_edges(data, "web", "1.0.0"),
            {("web@1.0.0", "low@2.0.0"), ("low@2.0.0", "tiny@0.1.0")},
        )
        with self.assertRaises(ToolError):
            npm_edges({}, "web", "1.0.0")

    def test_difference(self) -> None:
        """Отчёт называет лишние вершины и рёбра с каждой стороны."""
        ours = {("r", "a"), ("r", "b")}
        theirs = {("r", "a"), ("r", "peer")}
        lines = difference_lines(ours, theirs, "r")
        self.assertIn("only in tool: b", lines)
        self.assertIn("only in npm: peer", lines)
        self.assertIn("edge only in npm: r -> peer", lines)