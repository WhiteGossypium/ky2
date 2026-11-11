"""Тестовый репозиторий: граф пакетов, описанный в текстовом файле.

Формат строки: "A: B, C" - пакет A зависит от B и C. Пакет без
зависимостей: "D:". Пакеты называются большими латинскими буквами.
Текст после # - комментарий.
"""

import re
from typing import Dict, List, Tuple

from src.errors import ToolError

NAME = re.compile(r"[A-Z]+")


def parse_names(text: str, number: int) -> List[str]:
    """Разбирает список зависимостей через запятую."""
    names = [name.strip() for name in text.split(",")]
    if names == [""]:
        return []
    for name in names:
        if not NAME.fullmatch(name):
            raise ToolError(f"line {number}: bad package name '{name}'")
    return names


def parse_line(line: str, number: int) -> Tuple[str, List[str]]:
    """Разбирает одну строку описания пакета."""
    if ":" not in line:
        raise ToolError(f"line {number}: missing ':' after package name")
    name, _, rest = line.partition(":")
    name = name.strip()
    if not NAME.fullmatch(name):
        raise ToolError(f"line {number}: bad package name '{name}'")
    return name, parse_names(rest, number)


def parse_repository(text: str) -> Dict[str, List[str]]:
    """Разбирает весь файл: имя пакета -> список зависимостей."""
    packages: Dict[str, List[str]] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, children = parse_line(line, number)
        if name in packages:
            raise ToolError(f"line {number}: package {name} is repeated")
        packages[name] = children
    if not packages:
        raise ToolError("test repository has no packages")
    return packages


def load_repository(path: str) -> Dict[str, List[str]]:
    """Читает файл тестового репозитория."""
    try:
        with open(path, encoding="utf-8-sig") as source:
            text = source.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ToolError(f"cannot read test repository: {error}") from error
    try:
        return parse_repository(text)
    except ToolError as error:
        raise ToolError(f"{path}: {error}") from error