"""Получение данных о пакетах из реестра npm.

Реестр отдаёт по адресу <реестр>/<имя> документ JSON со всеми версиями
пакета. В каждой версии есть поле dependencies: имя -> диапазон версий.
Запрашивается сокращённый документ (заголовок Accept), он меньше.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Tuple

from src.errors import ToolError
from src.semver import choose_version

ABBREVIATED = "application/vnd.npm.install-v1+json"
TIMEOUT_SECONDS = 30
NOT_FOUND = 404
ALIAS = "npm:"

Fetch = Callable[[str], dict]


def package_url(repository: str, name: str) -> str:
    """Строит адрес документа пакета; / в имени с областью кодируется."""
    return f"{repository}/{urllib.parse.quote(name, safe='@')}"


def read_url(url: str) -> bytes:
    """Скачивает содержимое адреса стандартной библиотекой."""
    request = urllib.request.Request(
        url, headers={"Accept": ABBREVIATED, "User-Agent": "npm-graph"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS
        ) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == NOT_FOUND:
            raise ToolError(f"package not found: {url}") from error
        raise ToolError(f"registry answered {error.code}: {url}") from error
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise ToolError(f"cannot download {url}: {reason}") from error


def download_document(url: str) -> dict:
    """Скачивает и разбирает документ пакета."""
    data = read_url(url)
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ToolError(f"registry sent invalid JSON: {url}") from error
    if not isinstance(document, dict):
        raise ToolError(f"registry sent invalid JSON: {url}")
    if not isinstance(document.get("versions"), dict):
        raise ToolError(f"no versions in package document: {url}")
    return document


def split_alias(text: str) -> Tuple[str, str]:
    """Разбирает псевдоним имя@диапазон; без диапазона берётся latest."""
    name, _, spec = text.rpartition("@")
    return (name, spec) if name else (text, "latest")


class NpmRegistry:
    """Реестр npm; скачанные документы запоминаются."""

    def __init__(
        self, repository: str, fetch: Fetch = download_document
    ) -> None:
        """Запоминает адрес реестра и способ скачивания."""
        self.repository = repository
        self.fetch = fetch
        self.documents: Dict[str, dict] = {}

    def document(self, name: str) -> dict:
        """Возвращает документ пакета, скачивая его один раз."""
        if name not in self.documents:
            url = package_url(self.repository, name)
            self.documents[name] = self.fetch(url)
        return self.documents[name]

    def manifest(self, name: str, version: str) -> dict:
        """Возвращает описание заданной версии пакета."""
        document = self.document(name)
        if version not in document["versions"]:
            latest = document.get("dist-tags", {}).get("latest", "unknown")
            raise ToolError(
                f"{name} has no version {version} (latest is {latest})"
            )
        return document["versions"][version]

    def direct_dependencies(
        self, name: str, version: str
    ) -> List[Tuple[str, str]]:
        """Возвращает прямые зависимости: пары имя и диапазон версий."""
        dependencies = self.manifest(name, version).get("dependencies")
        if not dependencies:
            return []
        if not isinstance(dependencies, dict):
            raise ToolError(f"{name}@{version}: dependencies is not a map")
        return [(str(key), str(value)) for key, value in dependencies.items()]

    def resolve(self, name: str, spec: str) -> Tuple[str, str]:
        """Находит версию пакета под диапазон; возвращает имя и версию.

        Запись npm:другое-имя@диапазон означает псевдоним пакета.
        """
        if spec.startswith(ALIAS):
            name, spec = split_alias(spec[len(ALIAS):])
        if ":" in spec or "/" in spec:
            raise ToolError(f"{name}: unsupported dependency source {spec}")
        document = self.document(name)
        version = choose_version(
            list(document["versions"]), spec, document.get("dist-tags", {})
        )
        if version is None or version not in document["versions"]:
            raise ToolError(f"{name}: no version matches {spec}")
        return name, version
