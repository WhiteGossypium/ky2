"""Точка входа: python -m src.main [файл_настроек.csv]."""

import sys
from typing import List

from src.errors import ToolError
from src.npm_registry import NpmRegistry
from src.settings import DEFAULT_CONFIG, Settings, load_settings

USAGE = "usage: python -m src.main [config.csv]"
FAILURE = 1
USAGE_FAILURE = 2
MAX_ARGUMENTS = 1

def direct_report(settings: Settings, registry: NpmRegistry) -> List[str]:
    """Возвращает строки с прямыми зависимостями пакета."""
    if settings.test_mode:
        raise ToolError("test_mode: test repository is not supported yet")
    pairs = registry.direct_dependencies(settings.package, settings.version)
    lines = [
        f"package: {settings.package}@{settings.version}",
        f"direct dependencies: {len(pairs)}",
    ]
    lines.extend(f"  {name} {wanted}" for name, wanted in pairs)
    return lines


def run(arguments: List[str]) -> int:
    """Читает настройки и печатает прямые зависимости пакета."""
    if len(arguments) > MAX_ARGUMENTS:
        print(USAGE, file=sys.stderr)
        return USAGE_FAILURE
    path = arguments[0] if arguments else DEFAULT_CONFIG
    try:
        settings = load_settings(path)
        registry = NpmRegistry(settings.repository)
        lines = direct_report(settings, registry)
    except ToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return FAILURE
    print("\n".join(lines))
    return 0

def main() -> None:
    """Запускает программу с параметрами командной строки."""
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()