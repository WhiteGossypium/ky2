"""Тесты чтения и проверки настроек из CSV-файла."""

import os
import shutil
import tempfile
import unittest

from src.errors import ToolError
from src.settings import load_settings

REGISTRY = "https://registry.npmjs.org"


def config_text(**changes: str) -> str:
    """Возвращает текст правильного файла с заменёнными значениями."""
    values = {
        "package": "express",
        "repository": REGISTRY,
        "test_mode": "false",
        "version": "4.18.2",
        "filter": "",
    }
    values.update(changes)
    rows = [f"{key},{value}" for key, value in values.items()]
    return "parameter,value\n" + "\n".join(rows) + "\n"


class SettingsTest(unittest.TestCase):
    """Проверяет правильные файлы и ошибки каждого параметра."""

    def write(self, text: str) -> str:
        """Сохраняет текст во временный файл и возвращает путь."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "config.csv")
        with open(path, "w", encoding="utf-8") as target:
            target.write(text)
        return path

    def assert_error(self, text: str, message: str) -> None:
        """Проверяет, что файл отклонён с данным сообщением."""
        with self.assertRaises(ToolError) as caught:
            load_settings(self.write(text))
        self.assertIn(message, str(caught.exception))

    def test_valid_remote(self) -> None:
        """Правильный файл для реестра npm читается полностью."""
        settings = load_settings(self.write(config_text(filter="mime")))
        self.assertEqual(settings.package, "express")
        self.assertEqual(settings.repository, REGISTRY)
        self.assertFalse(settings.test_mode)
        self.assertEqual(settings.version, "4.18.2")
        self.assertEqual(settings.name_filter, "mime")

    def test_pairs(self) -> None:
        """Пары ключ-значение идут в порядке параметров."""
        settings = load_settings(self.write(config_text()))
        keys = [key for key, _ in settings.as_pairs()]
        self.assertEqual(
            keys,
            ["package", "repository", "test_mode", "version", "filter",
             "reverse"],
        )

    def test_scoped_name_and_slash(self) -> None:
        """Имя с областью принимается, лишний / у URL убирается."""
        text = config_text(package="@types/node", repository=REGISTRY + "/")
        settings = load_settings(self.write(text))
        self.assertEqual(settings.package, "@types/node")
        self.assertEqual(settings.repository, REGISTRY)

    def test_semicolon_and_bom(self) -> None:
        """Файл Excel: точка с запятой и метка BOM."""
        text = "﻿" + config_text().replace(",", ";")
        self.assertEqual(load_settings(self.write(text)).package, "express")

    def test_test_mode(self) -> None:
        """В тестовом режиме нужен файл и имя из больших букв."""
        repo = self.write("A: B\n")
        text = config_text(
            package="A", repository=repo, test_mode="TRUE", version=""
        )
        settings = load_settings(self.write(text))
        self.assertTrue(settings.test_mode)
        self.assertEqual(settings.version, "")

    def test_file_errors(self) -> None:
        """Ошибки самого файла."""
        with self.assertRaises(ToolError):
            load_settings("no/such/config.csv")
        self.assert_error("", "empty")
        self.assert_error("name,value\n", "header")
        self.assert_error("parameter,value\npackage,a,b\n", "2 columns")
        self.assert_error(config_text() + "color,red\n", "unknown")
        self.assert_error(config_text() + "package,chalk\n", "repeated")
        self.assert_error("parameter,value\npackage,a\n", "missing")

    def test_package_errors(self) -> None:
        """Ошибки имени пакета."""
        self.assert_error(config_text(package=""), "package: name is empty")
        self.assert_error(config_text(package="Express"), "valid npm")
        self.assert_error(config_text(package="a" * 215), "longer")
        repo = self.write("A: B\n")
        text = config_text(package="a", repository=repo, test_mode="true")
        self.assert_error(text, "capital")

    def test_repository_errors(self) -> None:
        """Ошибки адреса репозитория."""
        self.assert_error(config_text(repository=""), "repository: value")
        self.assert_error(config_text(repository="ftp://x"), "http(s)")
        text = config_text(
            package="A", repository="no/file.txt", test_mode="true"
        )
        self.assert_error(text, "test file not found")

    def test_other_errors(self) -> None:
        """Ошибки режима, версии и фильтра."""
        self.assert_error(config_text(test_mode="yes"), "true or false")
        self.assert_error(config_text(version=""), "version: value")
        self.assert_error(config_text(version="4.18"), "like 1.2.3")
        self.assert_error(config_text(filter="a b"), "spaces")
        self.assert_error(config_text(filter="press"), "excludes")

    def test_reverse(self) -> None:
        """reverse по умолчанию выключен, включается с тестовым файлом."""
        self.assertFalse(load_settings(self.write(config_text())).reverse)
        repo = self.write("A: B\n")
        text = config_text(package="A", repository=repo, test_mode="true")
        self.assertTrue(load_settings(self.write(text + "reverse,true\n"))
                        .reverse)

    def test_reverse_errors(self) -> None:
        """Неверное значение reverse и реестр npm вместо файла."""
        self.assert_error(config_text() + "reverse,maybe\n", "true or false")
        self.assert_error(config_text() + "reverse,true\n", "needs test_mode")