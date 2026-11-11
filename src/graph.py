"""Построение графа зависимостей алгоритмом DFS с рекурсией.

Обход в глубину: функция visit раскрывает пакет и вызывает сама себя
для каждой его зависимости. Путь от начального пакета до текущего
хранится в списке path: если зависимость уже есть в пути, найден цикл,
и рекурсия по ней не идёт. Уже раскрытый пакет второй раз
не раскрывается.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Protocol, Tuple

from src.errors import ToolError


class Source(Protocol):
    """Источник зависимостей: реестр npm или тестовый репозиторий."""

    def dependencies(self, node: str) -> List[Tuple[str, str]]:
        """Прямые зависимости вершины: имя и требуемая версия."""

    def node_for(self, name: str, spec: str) -> str:
        """Вершина графа для зависимости."""


@dataclass
class Graph:
    """Результат обхода."""

    root: str
    edges: Dict[str, List[str]] = field(default_factory=dict)
    cycles: List[List[str]] = field(default_factory=list)
    problems: Dict[str, str] = field(default_factory=dict)
    excluded: List[str] = field(default_factory=list)

    def nodes(self) -> List[str]:
        """Все вершины в порядке обнаружения."""
        return list(self.edges)

    def edge_count(self) -> int:
        """Число рёбер графа."""
        return sum(len(children) for children in self.edges.values())


class DepthFirstSearch:
    """Рекурсивный обход графа зависимостей с фильтром по имени."""

    def __init__(self, source: Source, name_filter: str) -> None:
        """Запоминает источник и подстроку фильтра."""
        self.source = source
        self.name_filter = name_filter
        self.path: List[str] = []
        self.graph = Graph(root="")

    def excluded(self, name: str) -> bool:
        """Сообщает, исключён ли пакет фильтром."""
        return bool(self.name_filter) and self.name_filter in name

    def run(self, root: str) -> Graph:
        """Обходит граф от начальной вершины."""
        self.graph = Graph(root=root)
        try:
            self.visit(root)
        except RecursionError as error:
            raise ToolError("dependency chain is too long") from error
        return self.graph

    def kept_children(self, node: str) -> List[str]:
        """Зависимости вершины без исключённых фильтром."""
        try:
            found = self.source.dependencies(node)
        except ToolError as error:
            self.graph.problems[node] = str(error)
            return []
        children: List[str] = []
        for name, spec in found:
            if self.excluded(name):
                self.remember_excluded(name)
                continue
            child = self.source.node_for(name, spec)
            if child not in children:
                children.append(child)
        return children

    def visit(self, node: str) -> None:
        """Раскрывает вершину и рекурсивно обходит её зависимости."""
        self.path.append(node)
        self.graph.edges[node] = self.kept_children(node)
        for child in self.graph.edges[node]:
            if child in self.path:
                self.remember_cycle(child)
            elif child not in self.graph.edges:
                self.visit(child)
        self.path.pop()

    def remember_cycle(self, child: str) -> None:
        """Запоминает цикл: часть пути от child до текущей вершины."""
        cycle = self.path[self.path.index(child):] + [child]
        if cycle not in self.graph.cycles:
            self.graph.cycles.append(cycle)

    def remember_excluded(self, name: str) -> None:
        """Запоминает имя пакета, пропущенного фильтром."""
        if name not in self.graph.excluded:
            self.graph.excluded.append(name)


def build_graph(source: Source, root: str, name_filter: str = "") -> Graph:
    """Строит граф зависимостей начальной вершины."""
    return DepthFirstSearch(source, name_filter).run(root)