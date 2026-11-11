"""Тесты чтения прямых зависимостей из реестра npm."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.errors import ToolError
from src.npm_registry import NpmRegistry, download_document, package_url

DOCUMENT = {
    "name": "web",
    "dist-tags": {"latest": "2.0.0"},
    "versions": {
        "1.0.0": {"dependencies": {"low": "^1.2.0", "@scope/tool": "~2.0.1"}},
        "2.0.0": {},
    },
}


class FakeFetch:
    """Подменяет скачивание: отдаёт документы и считает запросы."""

    def __init__(self, documents: dict) -> None:
        """Запоминает документы по адресам."""
        self.documents = documents
        self.calls = []

    def __call__(self, url: str) -> dict:
        """Возвращает документ по адресу или сообщает, что его нет."""
        self.calls.append(url)
        if url not in self.documents:
            raise ToolError(f"package not found: {url}")
        return self.documents[url]


def registry_with(documents: dict) -> NpmRegistry:
    """Создаёт реестр, который не ходит в сеть."""
    urls = {f"http://r/{name}": value for name, value in documents.items()}
    return NpmRegistry("http://r", FakeFetch(urls))


class RegistryTest(unittest.TestCase):
    """Проверяет адреса, версии и разбор зависимостей."""

    def test_package_url(self) -> None:
        """Косая черта в имени с областью кодируется."""
        self.assertEqual(package_url("http://r", "a"), "http://r/a")
        self.assertEqual(
            package_url("http://r", "@types/node"), "http://r/@types%2Fnode"
        )

    def test_direct_dependencies(self) -> None:
        """Зависимости берутся у заданной версии в исходном порядке."""
        registry = registry_with({"web": DOCUMENT})
        self.assertEqual(
            registry.direct_dependencies("web", "1.0.0"),
            [("low", "^1.2.0"), ("@scope/tool", "~2.0.1")],
        )
        self.assertEqual(registry.direct_dependencies("web", "2.0.0"), [])

    def test_document_cached(self) -> None:
        """Документ пакета скачивается один раз."""
        registry = registry_with({"web": DOCUMENT})
        registry.manifest("web", "1.0.0")
        registry.manifest("web", "2.0.0")
        self.assertEqual(len(registry.fetch.calls), 1)

    def test_errors(self) -> None:
        """Нет версии, нет пакета, неверное поле dependencies."""
        broken = {"versions": {"1.0.0": {"dependencies": ["x"]}}}
        registry = registry_with({"web": DOCUMENT, "bad": broken})
        with self.assertRaisesRegex(ToolError, "latest is 2.0.0"):
            registry.manifest("web", "9.9.9")
        with self.assertRaisesRegex(ToolError, "not found"):
            registry.manifest("nothing", "1.0.0")
        with self.assertRaisesRegex(ToolError, "not a map"):
            registry.direct_dependencies("bad", "1.0.0")


class DownloadTest(unittest.TestCase):
    """Проверяет скачивание через urllib на локальных файлах."""

    def save(self, text: str) -> str:
        """Сохраняет текст в файл и возвращает его адрес file://."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "doc.json")
        with open(path, "w", encoding="utf-8") as target:
            target.write(text)
        return Path(path).as_uri()

    def test_valid(self) -> None:
        """Правильный документ разбирается."""
        url = self.save(json.dumps(DOCUMENT))
        self.assertEqual(download_document(url)["name"], "web")

    def test_invalid(self) -> None:
        """Не JSON, нет версий, нет файла."""
        for text in ("<html>", "[1]", '{"name": "x"}'):
            with self.assertRaises(ToolError):
                download_document(self.save(text))
        with self.assertRaisesRegex(ToolError, "cannot download"):
            download_document(self.save("{}") + "-missing")