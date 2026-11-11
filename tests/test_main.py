"""Тесты запуска программы целиком."""

import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from src.main import run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch(*arguments: str):
    """Запускает программу и возвращает код, вывод и ошибки."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = run([os.path.join(ROOT, name) for name in arguments])
    return code, out.getvalue(), err.getvalue()


class MainTest(unittest.TestCase):
    """Проверяет вывод параметров и коды завершения."""

    def test_test_mode_not_ready(self) -> None:
        """Тестовый репозиторий на этом этапе ещё не поддержан."""
        code, _, err = launch("configs/test_simple.csv")
        self.assertEqual(code, 1)
        self.assertIn("not supported yet", err)

    def test_error(self) -> None:
        """Ошибка настроек даёт код 1 и сообщение в потоке ошибок."""
        code, out, err = launch("configs/errors/version_invalid.csv")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("error: version", err)

    def test_too_many_arguments(self) -> None:
        """Больше одного аргумента - подсказка по запуску."""
        code, _, err = launch("config.csv", "config.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("usage", err)
