"""Точка входа: python -m src.main [файл_настроек.csv]."""

import sys
from typing import List

from src.errors import ToolError
from src.settings import DEFAULT_CONFIG, load_settings

USAGE = "usage: python -m src.main [config.csv]"
FAILURE = 1
USAGE_FAILURE = 2
MAX_ARGUMENTS = 1


def run(arguments: List[str]) -> int:
    """Читает настройки и печатает их в формате ключ=значение."""
    if len(arguments) > MAX_ARGUMENTS:
        print(USAGE, file=sys.stderr)
        return USAGE_FAILURE
    path = arguments[0] if arguments else DEFAULT_CONFIG
    try:
        settings = load_settings(path)
    except ToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return FAILURE
    for key, value in settings.as_pairs():
        print(f"{key}={value}")
    return 0


def main() -> None:
    """Запускает программу с параметрами командной строки."""
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()