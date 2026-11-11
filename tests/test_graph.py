"""Тесты построения графа на тестовых репозиториях."""

import os
import unittest

from src.errors import ToolError
from src.file_repository import load_repository, parse_repository
from src.graph import build_graph
from src.sources import FileSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG_CHAIN = 5000


def graph_of(name: str, name_filter: str = ""):
    """Строит граф от пакета A по файлу из test_repos."""
    path = os.path.join(ROOT, "test_repos", name + ".txt")
    return build_graph(FileSource(load_repository(path)), "A", name_filter)


class RepositoryFileTest(unittest.TestCase):
    """Проверяет разбор файла тестового репозитория."""

    def test_parse(self) -> None:
        """Комментарии и пустые строки пропускаются."""
        text = "# note\n\nA: B, C  # tail\nB:\n"
        self.assertEqual(parse_repository(text), {"A": ["B", "C"], "B": []})

    def test_errors(self) -> None:
        """Ошибки формата называют номер строки."""
        cases = {
            "A B\n": "line 1: missing ':'",
            "a: B\n": "line 1: bad package name 'a'",
            "A: B, c\n": "bad package name 'c'",
            "A: B\nA: C\n": "line 2: package A is repeated",
            "# only comment\n": "no packages",
        }
        for text, message in cases.items():
            with self.assertRaises(ToolError) as caught:
                parse_repository(text)
            self.assertIn(message, str(caught.exception))


class GraphTest(unittest.TestCase):
    """Проверяет обход на разных случаях."""

    def test_diamond(self) -> None:
        """Общая зависимость раскрывается один раз."""
        graph = graph_of("diamond")
        self.assertEqual(graph.nodes(), ["A", "B", "D", "C"])
        self.assertEqual(graph.edge_count(), 4)
        self.assertEqual(graph.cycles, [])

    def test_transitive_chain(self) -> None:
        """Транзитивные зависимости попадают в граф."""
        self.assertEqual(graph_of("chain").nodes(), list("ABCDEFGH"))

    def test_cycles(self) -> None:
        """Циклы находятся, обход не зацикливается."""
        graph = graph_of("cycle")
        self.assertEqual(
            graph.cycles, [["A", "B", "C", "A"], ["C", "D", "C"]]
        )
        self.assertEqual(graph.edges["C"], ["A", "D"])

    def test_self_loop(self) -> None:
        """Пакет, зависящий от себя, - цикл из одной вершины."""
        self.assertEqual(graph_of("self_loop").cycles, [["A", "A"]])

    def test_filter(self) -> None:
        """Пакеты с подстрокой в имени не учитываются вместе с ветками."""
        graph = graph_of("filter", "XY")
        self.assertEqual(graph.nodes(), ["A", "B", "C"])
        self.assertEqual(graph.excluded, ["XY", "XYZ"])

    def test_undescribed(self) -> None:
        """Неописанный пакет остаётся в графе с пометкой."""
        graph = graph_of("undescribed")
        self.assertIn("C", graph.nodes())
        self.assertIn("not described", graph.problems["C"])

    def test_missing_root(self) -> None:
        """Начального пакета нет в файле - ошибка."""
        with self.assertRaises(ToolError):
            FileSource({"A": []}).root("Z", "")

    def test_too_long_chain(self) -> None:
        """Очень длинная цепочка не роняет программу."""
        packages = {f"P{index}": [f"P{index + 1}"]
                    for index in range(LONG_CHAIN)}
        with self.assertRaises(ToolError):
            build_graph(FileSource(packages), "P0")