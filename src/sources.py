"""Источники зависимостей для построения графа.

Источник умеет три вещи: назвать начальную вершину графа, перечислить
зависимости вершины (имя и требуемая версия) и превратить зависимость
в вершину графа. Граф строится одинаково для реестра npm и для
тестового репозитория.
"""

from typing import Dict, List, Tuple

from src.errors import ToolError
from src.npm_registry import NpmRegistry

Dependency = Tuple[str, str]


def split_node(node: str) -> Tuple[str, str]:
    """Делит вершину вида имя@версия; имя может начинаться с @."""
    name, _, version = node.rpartition("@")
    return name, version


class NpmSource:
    """Зависимости из реестра npm; вершина графа - имя@версия."""

    def __init__(self, registry: NpmRegistry) -> None:
        """Запоминает реестр и ошибки подбора версий."""
        self.registry = registry
        self.failures: Dict[str, str] = {}

    def root(self, package: str, version: str) -> str:
        """Проверяет, что заданная версия есть, и возвращает вершину."""
        self.registry.manifest(package, version)
        return f"{package}@{version}"

    def dependencies(self, node: str) -> List[Dependency]:
        """Прямые зависимости вершины: имя и диапазон версий."""
        if node in self.failures:
            raise ToolError(self.failures[node])
        return self.registry.direct_dependencies(*split_node(node))

    def node_for(self, name: str, spec: str) -> str:
        """Подбирает версию зависимости; при ошибке запоминает причину."""
        try:
            real_name, version = self.registry.resolve(name, spec)
        except ToolError as error:
            node = f"{name}@{spec}"
            self.failures[node] = str(error)
            return node
        return f"{real_name}@{version}"


class FileSource:
    """Зависимости из тестового репозитория; вершина графа - имя."""

    def __init__(self, packages: Dict[str, List[str]]) -> None:
        """Запоминает описание пакетов."""
        self.packages = packages

    def root(self, package: str, version: str) -> str:
        """Проверяет, что пакет описан в файле; версия не используется."""
        if package not in self.packages:
            raise ToolError(f"package {package} is not in test repository")
        return package

    def dependencies(self, node: str) -> List[Dependency]:
        """Зависимости пакета из файла."""
        if node not in self.packages:
            raise ToolError(f"{node} is not described in test repository")
        return [(name, name) for name in self.packages[node]]

    def node_for(self, name: str, spec: str) -> str:
        """В тестовом репозитории вершина - просто имя пакета."""
        return name


def reverse_index(packages: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Переворачивает рёбра: пакет -> пакеты, которые от него зависят."""
    index: Dict[str, List[str]] = {}
    for parent, children in packages.items():
        for child in children:
            index.setdefault(child, []).append(parent)
    return index


class ReverseFileSource(FileSource):
    """Обратные зависимости: соседи пакета - те, кто от него зависит."""

    def __init__(self, packages: Dict[str, List[str]]) -> None:
        """Строит перевёрнутый граф тестового репозитория."""
        super().__init__(packages)
        self.dependents = reverse_index(packages)

    def root(self, package: str, version: str) -> str:
        """Пакет должен встречаться в файле хотя бы раз."""
        if package not in self.packages and package not in self.dependents:
            raise ToolError(f"package {package} is not in test repository")
        return package

    def dependencies(self, node: str) -> List[Dependency]:
        """Пакеты, которые напрямую зависят от данного."""
        return [(name, name) for name in self.dependents.get(node, [])]