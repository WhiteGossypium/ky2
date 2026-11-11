"""Точка входа: python -m src.main [файл_настроек.csv]."""

import sys
from typing import List, Union

from src.errors import ToolError
from src.file_repository import load_repository
from src.graph import Graph, build_graph
from src.mermaid import save_diagram, to_mermaid
from src.npm_registry import NpmRegistry
from src.settings import DEFAULT_CONFIG, Settings, load_settings
from src.sources import FileSource, NpmSource

USAGE = "usage: python -m src.main [config.csv]"
FAILURE = 1
USAGE_FAILURE = 2
MAX_ARGUMENTS = 1


def make_source(settings: Settings) -> Union[FileSource, NpmSource]:
    """Выбирает источник: тестовый репозиторий или реестр npm."""
    if settings.test_mode:
        return FileSource(load_repository(settings.repository))
    return NpmSource(NpmRegistry(settings.repository))


def graph_for(settings: Settings) -> Graph:
    """Строит граф зависимостей по настройкам."""
    source = make_source(settings)
    root = source.root(settings.package, settings.version)
    return build_graph(source, root, settings.name_filter)


def write_output(settings: Settings, diagram: str, graph: Graph) -> None:
    """Сохраняет диаграмму в файл, если он задан в настройках."""
    if not settings.output:
        return
    try:
        save_diagram(settings.output, diagram, graph.root)
    except OSError as error:
        raise ToolError(f"output: cannot write file: {error}") from error
    print(f"saved: {settings.output}", file=sys.stderr)


def run(arguments: List[str]) -> int:
    """Читает настройки, строит граф и печатает его на языке Mermaid."""
    if len(arguments) > MAX_ARGUMENTS:
        print(USAGE, file=sys.stderr)
        return USAGE_FAILURE
    path = arguments[0] if arguments else DEFAULT_CONFIG
    try:
        settings = load_settings(path)
        graph = graph_for(settings)
        diagram = to_mermaid(graph)
        print(diagram, end="")
        write_output(settings, diagram, graph)
    except ToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return FAILURE
    return 0


def main() -> None:
    """Запускает программу с параметрами командной строки."""
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()