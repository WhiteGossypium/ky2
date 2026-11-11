"""Чтение настроек из конфигурационного файла формата CSV.

Файл состоит из строк "параметр,значение". Первая строка - заголовок
"parameter,value". Разделитель - запятая или точка с запятой (так
сохраняет Excel с русскими настройками).
"""

import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from src.errors import ToolError

DEFAULT_CONFIG = "config.csv"
HEADER = ["parameter", "value"]
PARAMETERS = ("package", "repository", "test_mode", "version", "filter")
OPTIONAL = {"reverse": "false"}
KNOWN = PARAMETERS + tuple(OPTIONAL)
MAX_NAME_LENGTH = 214
NPM_NAME = re.compile(
    r"(?:@[a-z0-9~-][a-z0-9._~-]*/)?[a-z0-9~-][a-z0-9._~-]*"
)
TEST_NAME = re.compile(r"[A-Z]+")
VERSION = re.compile(
    r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
)
SWITCH = {"true": True, "false": False}


@dataclass
class Settings:
    """Проверенные значения всех параметров."""

    package: str
    repository: str
    test_mode: bool
    version: str
    name_filter: str
    reverse: bool = False

    def as_pairs(self) -> List[Tuple[str, str]]:
        """Возвращает параметры в виде пар ключ-значение."""
        return [
            ("package", self.package),
            ("repository", self.repository),
            ("test_mode", str(self.test_mode).lower()),
            ("version", self.version),
            ("filter", self.name_filter),
            ("reverse", str(self.reverse).lower()),
        ]


def read_rows(path: str) -> List[List[str]]:
    """Читает строки CSV-файла, определяя разделитель по заголовку."""
    if not os.path.isfile(path):
        raise ToolError(f"config file not found: {path}")
    try:
        with open(path, encoding="utf-8-sig", newline="") as source:
            lines = source.read().splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ToolError(f"cannot read config file {path}: {error}") from error
    if not any(line.strip() for line in lines):
        raise ToolError(f"config file is empty: {path}")
    delimiter = ";" if ";" in lines[0] else ","
    return list(csv.reader(lines, delimiter=delimiter))


def check_header(row: List[str]) -> None:
    """Проверяет первую строку файла."""
    if [cell.strip().lower() for cell in row] != HEADER:
        raise ToolError("config line 1: header must be 'parameter,value'")


def check_complete(values: Dict[str, str]) -> None:
    """Проверяет, что в файле указаны все параметры."""
    missing = [key for key in PARAMETERS if key not in values]
    if missing:
        raise ToolError("config: missing parameters: " + ", ".join(missing))


def collect_values(rows: List[List[str]]) -> Dict[str, str]:
    """Превращает строки файла в словарь параметр -> значение."""
    check_header(rows[0])
    values: Dict[str, str] = {}
    for number, row in enumerate(rows[1:], start=2):
        if not "".join(row).strip():
            continue
        if len(row) != len(HEADER):
            raise ToolError(
                f"config line {number}: expected 2 columns, got {len(row)}"
            )
        key = row[0].strip().lower()
        if key not in KNOWN:
            raise ToolError(f"config line {number}: unknown parameter {key}")
        if key in values:
            raise ToolError(f"config line {number}: {key} is repeated")
        values[key] = row[1].strip()
    check_complete(values)
    return {**OPTIONAL, **values}


def check_switch(key: str, value: str) -> bool:
    """Проверяет параметр-переключатель: true или false."""
    if value.lower() not in SWITCH:
        raise ToolError(f"{key}: expected true or false, got '{value}'")
    return SWITCH[value.lower()]


def check_reverse(value: str, test_mode: bool) -> bool:
    """Проверяет режим обратных зависимостей."""
    reverse = check_switch("reverse", value)
    if reverse and not test_mode:
        raise ToolError(
            "reverse: needs test_mode,true - npm registry has no list "
            "of dependent packages"
        )
    return reverse


def check_package(value: str, test_mode: bool) -> str:
    """Проверяет имя пакета по правилам npm или тестового режима."""
    if not value:
        raise ToolError("package: name is empty")
    if test_mode:
        if not TEST_NAME.fullmatch(value):
            raise ToolError(
                f"package: '{value}' must be capital latin letters "
                "in test mode"
            )
        return value
    if len(value) > MAX_NAME_LENGTH:
        raise ToolError(f"package: name is longer than {MAX_NAME_LENGTH}")
    if not NPM_NAME.fullmatch(value):
        raise ToolError(f"package: '{value}' is not a valid npm name")
    return value


def check_repository(value: str, test_mode: bool) -> str:
    """Проверяет URL реестра или путь к файлу тестового репозитория."""
    if not value:
        raise ToolError("repository: value is empty")
    if test_mode:
        if not os.path.isfile(value):
            raise ToolError(f"repository: test file not found: {value}")
        return value
    parts = urlparse(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ToolError(f"repository: '{value}' is not an http(s) URL")
    return value.rstrip("/")


def check_version(value: str, test_mode: bool) -> str:
    """Проверяет точную версию пакета вида 1.2.3."""
    if test_mode and not value:
        return value
    if not value:
        raise ToolError("version: value is empty")
    if not VERSION.fullmatch(value):
        raise ToolError(f"version: '{value}' is not a version like 1.2.3")
    return value


def check_filter(value: str, package: str) -> str:
    """Проверяет подстроку, по которой пакеты исключаются из анализа."""
    if any(char.isspace() for char in value):
        raise ToolError("filter: substring must not contain spaces")
    if value and value in package:
        raise ToolError(f"filter: '{value}' excludes package {package}")
    return value


def load_settings(path: str) -> Settings:
    """Читает и проверяет все параметры из CSV-файла."""
    values = collect_values(read_rows(path))
    test_mode = check_switch("test_mode", values["test_mode"])
    package = check_package(values["package"], test_mode)
    return Settings(
        package=package,
        repository=check_repository(values["repository"], test_mode),
        test_mode=test_mode,
        version=check_version(values["version"], test_mode),
        name_filter=check_filter(values["filter"], package),
        reverse=check_reverse(values["reverse"], test_mode),
    )