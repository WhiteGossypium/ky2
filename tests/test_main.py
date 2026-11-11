"""Тесты запуска программы целиком."""

import io
import os
import shutil
import tempfile
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

    def test_mermaid(self) -> None:
        """Граф печатается на языке Mermaid, цикл - пунктиром."""
        code, out, _ = launch("configs/test_cycle.csv")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("flowchart LR\n"))
        self.assertIn("%% cycle: A -> B -> C -> A", out)
        self.assertIn("n2 -. cycle .-> n0", out)

    def test_output_file(self) -> None:
        """Диаграмма сохраняется в файл из параметра output."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        config = os.path.join(folder, "config.csv")
        target = os.path.join(folder, "out", "graph.mmd")
        repo = os.path.join(ROOT, "test_repos", "diamond.txt")
        with open(config, "w", encoding="utf-8") as handle:
            handle.write(
                "parameter,value\npackage,A\n"
                f"repository,{repo}\ntest_mode,true\nversion,\n"
                f"filter,\noutput,{target}\n"
            )
        code, out, err = launch(config)
        self.assertEqual(code, 0)
        self.assertIn("saved:", err)
        with open(target, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), out)

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