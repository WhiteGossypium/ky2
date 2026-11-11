"""Тесты чтения прямых зависимостей из реестра npm."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.errors import ToolError
from src.graph import build_graph
from src.npm_registry import NpmRegistry, download_document, package_url
from src.sources import NpmSource, split_node

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


LOW = {
    "dist-tags": {"latest": "1.4.0"},
    "versions": {
        "1.2.0": {}, "1.4.0": {"dependencies": {"web": "1.0.0"}},
        "1.9.0": {}, "2.0.0": {},
    },
}
TOOL = {"versions": {"2.0.5": {}, "2.1.0": {}}}


class ResolveTest(unittest.TestCase):
    """Проверяет подбор версий и граф из реестра."""

    def registry(self) -> NpmRegistry:
        """Реестр из трёх пакетов, где web и low зависят друг от друга."""
        return registry_with(
            {"web": DOCUMENT, "low": LOW, "@scope%2Ftool": TOOL}
        )

    def test_resolve(self) -> None:
        """Метка latest, новейшая версия, псевдоним, ошибки."""
        registry = self.registry()
        self.assertEqual(registry.resolve("low", "^1.2.0"), ("low", "1.4.0"))
        self.assertEqual(registry.resolve("low", "~1.9"), ("low", "1.9.0"))
        self.assertEqual(
            registry.resolve("x", "npm:low@2"), ("low", "2.0.0")
        )
        with self.assertRaisesRegex(ToolError, "no version matches"):
            registry.resolve("low", "^3")
        with self.assertRaisesRegex(ToolError, "unsupported"):
            registry.resolve("low", "github:user/low")

    def test_split_node(self) -> None:
        """Имя с областью отделяется от версии."""
        self.assertEqual(split_node("@a/b@1.0.0"), ("@a/b", "1.0.0"))

    def test_graph(self) -> None:
        """Граф из реестра: цикл web -> low -> web."""
        source = NpmSource(self.registry())
        graph = build_graph(source, source.root("web", "1.0.0"))
        self.assertEqual(
            graph.edges["web@1.0.0"], ["low@1.4.0", "@scope/tool@2.0.5"]
        )
        self.assertEqual(
            graph.cycles, [["web@1.0.0", "low@1.4.0", "web@1.0.0"]]
        )

    def test_failed_dependency(self) -> None:
        """Пакет, для которого нет версии, отмечается и не роняет граф."""
        broken = {"dependencies": {"low": "^7.0.0"}}
        document = {"versions": {"1.0.0": broken}}
        registry = registry_with({"top": document, "low": LOW})
        source = NpmSource(registry)
        graph = build_graph(source, source.root("top", "1.0.0"))
        self.assertIn("no version matches", graph.problems["low@^7.0.0"])


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