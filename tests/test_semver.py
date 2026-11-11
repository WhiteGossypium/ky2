"""Тесты разбора версий и диапазонов npm."""

import unittest

from src.errors import ToolError
from src.semver import choose_version, parse_version, satisfies

VERSIONS = [
    "0.0.3", "0.0.4", "0.2.0", "0.2.5", "0.3.0", "1.0.0", "1.2.0",
    "1.2.7", "1.3.0", "1.9.9", "2.0.0-beta.1", "2.0.0-beta.2", "2.0.0",
    "2.1.0", "3.0.0",
]


def matching(spec: str) -> list:
    """Версии из списка, подходящие под диапазон."""
    return [text for text in VERSIONS if satisfies(parse_version(text), spec)]


class VersionTest(unittest.TestCase):
    """Проверяет разбор и порядок версий."""

    def test_parse(self) -> None:
        """Точная версия разбирается, неполная - нет."""
        self.assertEqual(parse_version("1.2.3").release(), (1, 2, 3))
        self.assertEqual(parse_version("v1.2.3-rc.1").pre, ("rc", "1"))
        self.assertIsNone(parse_version("1.2"))

    def test_order(self) -> None:
        """Предварительные версии меньше выпуска, числа сравниваются числами."""
        order = ["1.0.0-alpha", "1.0.0-alpha.2", "1.0.0-alpha.10",
                 "1.0.0-beta", "1.0.0", "1.0.1", "1.10.0"]
        keys = [parse_version(text).key() for text in order]
        self.assertEqual(keys, sorted(keys))


class RangeTest(unittest.TestCase):
    """Проверяет диапазоны так, как их понимает npm."""

    def test_caret(self) -> None:
        """^ не меняет первую ненулевую часть."""
        self.assertEqual(matching("^1.2.0"), ["1.2.0", "1.2.7", "1.3.0",
                                              "1.9.9"])
        self.assertEqual(matching("^0.2.0"), ["0.2.0", "0.2.5"])
        self.assertEqual(matching("^0.0.3"), ["0.0.3"])

    def test_tilde_and_x(self) -> None:
        """~ меняет только последнюю часть; x и * - любые числа."""
        self.assertEqual(matching("~1.2.1"), ["1.2.7"])
        self.assertEqual(matching("1.x"), matching("^1.0.0"))
        self.assertEqual(len(matching("*")), len(VERSIONS) - 2)
        self.assertEqual(matching(""), matching("*"))

    def test_operators(self) -> None:
        """Сравнения, дефис и варианты через ||."""
        self.assertEqual(matching(">=2.0.0 <3"), ["2.0.0", "2.1.0"])
        self.assertEqual(matching(">1.9 <=2"), ["2.0.0", "2.1.0"])
        self.assertEqual(matching("1.3 - 2.0.0"), ["1.3.0", "1.9.9", "2.0.0"])
        self.assertEqual(matching("^0.3.0 || 3"), ["0.3.0", "3.0.0"])
        self.assertEqual(matching(">= 2.1.0"), ["2.1.0", "3.0.0"])

    def test_prerelease(self) -> None:
        """Предварительная версия подходит, только если названа явно."""
        self.assertNotIn("2.0.0-beta.2", matching(">=1.0.0"))
        self.assertEqual(
            matching("^2.0.0-beta.2"), ["2.0.0-beta.2", "2.0.0", "2.1.0"]
        )

    def test_invalid(self) -> None:
        """Неверный диапазон - ошибка."""
        with self.assertRaises(ToolError):
            satisfies(parse_version("1.0.0"), ">=abc")


class ChooseTest(unittest.TestCase):
    """Проверяет выбор версии как в npm."""

    def test_newest(self) -> None:
        """Берётся новейшая подходящая версия."""
        self.assertEqual(choose_version(VERSIONS, "^1.2.0", {}), "1.9.9")
        self.assertIsNone(choose_version(VERSIONS, "^5.0.0", {}))

    def test_latest_tag(self) -> None:
        """Метка latest важнее новейшей версии, если подходит."""
        tags = {"latest": "1.2.7", "next": "2.0.0-beta.2"}
        self.assertEqual(choose_version(VERSIONS, "^1.0.0", tags), "1.2.7")
        self.assertEqual(choose_version(VERSIONS, "^2.0.0", tags), "2.1.0")
        self.assertEqual(choose_version(VERSIONS, "next", tags),
                         "2.0.0-beta.2")