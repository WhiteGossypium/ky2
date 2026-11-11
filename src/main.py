"""Точка входа: python -m src.main [файл_настроек.csv]."""

import sys
from typing import List, Union

from src.errors import ToolError
from src.file_repository import load_repository
from src.graph import Graph, build_graph
from src.npm_registry import NpmRegistry
from src.report import graph_lines, reverse_lines
from src.settings import DEFAULT_CONFIG, Settings, load_settings
from src.sources import FileSource, NpmSource, ReverseFileSource

USAGE = "usage: python -m src.main [config.csv]"
FAILURE = 1
USAGE_FAILURE = 2
MAX_ARGUMENTS = 1


def make_source(settings: Settings) -> Union[FileSource, NpmSource]:
    """Выбирает источник: тестовый репозиторий или реестр npm."""
    if settings.reverse:
        return ReverseFileSource(load_repository(settings.repository))
    if settings.test_mode:
        return FileSource(load_repository(settings.repository))
    return NpmSource(NpmRegistry(settings.repository))


def graph_for(settings: Settings) -> Graph:
    """Строит граф зависимостей по настройкам."""
    source = make_source(settings)
    root = source.root(settings.package, settings.version)
    return build_graph(source, root, settings.name_filter)


def run(arguments: List[str]) -> int:
    """Читает настройки, строит граф и печатает его."""
    if len(arguments) > MAX_ARGUMENTS:
        print(USAGE, file=sys.stderr)
        return USAGE_FAILURE
    path = arguments[0] if arguments else DEFAULT_CONFIG
    try:
        settings = load_settings(path)
        graph = graph_for(settings)
    except ToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return FAILURE
    lines = reverse_lines(graph) if settings.reverse else graph_lines(graph)
    print("\n".join(lines))
    return 0


def main() -> None:
    """Запускает программу с параметрами командной строки."""
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()