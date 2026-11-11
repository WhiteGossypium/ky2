"""Версии и диапазоны версий npm (семантическое версионирование).

Зависимость в npm задаётся диапазоном: ^1.2.0, ~1.3.8, >=2 <3, 1.x,
1.0.0 - 2.0.0, несколько вариантов через ||. Модуль выбирает самую
новую версию из подходящих, как это делает npm.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.errors import ToolError

VERSION = re.compile(
    r"v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?"
)
PARTIAL = re.compile(
    r"v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?"
)
TOKEN = re.compile(r"(<=|>=|<|>|=|\^|~>|~)?(.*)")
GLUED_OPERATOR = re.compile(r"(<=|>=|<|>|=|\^|~>|~)\s+")
WILDCARDS = ("x", "X", "*")
DEFAULT_TAG = "latest"


@dataclass(frozen=True)
class Version:
    """Версия major.minor.patch с необязательной предварительной частью."""

    major: int
    minor: int
    patch: int
    pre: Tuple[str, ...] = ()

    def release(self) -> Tuple[int, int, int]:
        """Три числа версии без предварительной части."""
        return (self.major, self.minor, self.patch)

    def key(self) -> tuple:
        """Ключ сравнения: 1.0.0-beta меньше 1.0.0."""
        parts = tuple(
            (0, int(part), "") if part.isdigit() else (1, 0, part)
            for part in self.pre
        )
        return self.release() + (0 if self.pre else 1, parts)


@dataclass(frozen=True)
class Partial:
    """Неполная версия из диапазона: пропущенные части равны None."""

    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]
    pre: Tuple[str, ...] = ()

    def filled(self) -> Version:
        """Версия, где пропущенные части заменены нулями."""
        return Version(
            self.major or 0, self.minor or 0, self.patch or 0, self.pre
        )


Comparator = Tuple[str, Version]

CHECKS = {
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "=": lambda left, right: left == right,
}


def split_pre(text: Optional[str]) -> Tuple[str, ...]:
    """Разбивает предварительную часть версии по точкам."""
    return tuple(text.split(".")) if text else ()


def parse_version(text: str) -> Optional[Version]:
    """Разбирает точную версию; для неверной строки возвращает None."""
    found = VERSION.fullmatch(text.strip())
    if not found:
        return None
    major, minor, patch, pre = found.groups()
    return Version(int(major), int(minor), int(patch), split_pre(pre))


def number(text: Optional[str]) -> Optional[int]:
    """Число из части версии; x, * и пропуск дают None."""
    if text is None or text in WILDCARDS:
        return None
    return int(text)


def parse_partial(text: str, spec: str) -> Partial:
    """Разбирает неполную версию вида 1, 1.2, 1.x, *."""
    found = PARTIAL.fullmatch(text)
    if not found:
        raise ToolError(f"invalid version range: {spec}")
    major, minor, patch, pre = found.groups()
    major_number, minor_number = number(major), number(minor)
    minor_number = None if major_number is None else minor_number
    patch_number = None if minor_number is None else number(patch)
    return Partial(major_number, minor_number, patch_number, split_pre(pre))


def next_up(part: Partial) -> Version:
    """Первая версия после последней указанной части."""
    if part.minor is None:
        return Version(part.major + 1, 0, 0)
    return Version(part.major, part.minor + 1, 0)


def equal_range(part: Partial) -> List[Comparator]:
    """Диапазон для 1.2.3, =1.2.3, 1.2, 1.x и *."""
    if part.major is None:
        return []
    if part.patch is None:
        return [(">=", part.filled()), ("<", next_up(part))]
    return [("=", part.filled())]


def tilde_range(part: Partial) -> List[Comparator]:
    """Диапазон ~: меняется только последняя часть версии."""
    if part.major is None:
        return []
    upper = next_up(Partial(part.major, part.minor, None))
    return [(">=", part.filled()), ("<", upper)]


def caret_range(part: Partial) -> List[Comparator]:
    """Диапазон ^: не меняется первая ненулевая часть версии."""
    if part.major is None:
        return []
    if part.major or part.minor is None:
        upper = Version(part.major + 1, 0, 0)
    elif part.minor or part.patch is None:
        upper = Version(0, part.minor + 1, 0)
    else:
        upper = Version(0, 0, part.patch + 1)
    return [(">=", part.filled()), ("<", upper)]


def bound_range(operator: str, part: Partial) -> List[Comparator]:
    """Диапазон для операторов <, <=, >, >=."""
    if part.major is None:
        nothing = [("<", Version(0, 0, 0, ("0",)))]
        return nothing if operator in ("<", ">") else []
    if part.patch is not None or operator in ("<", ">="):
        return [(operator, part.filled())]
    if operator == ">":
        return [(">=", next_up(part))]
    return [("<", next_up(part))]


def expand_token(token: str, spec: str) -> List[Comparator]:
    """Превращает одно условие диапазона в простые сравнения."""
    operator, rest = TOKEN.fullmatch(token).groups()
    part = parse_partial(rest, spec)
    if operator == "^":
        return caret_range(part)
    if operator in ("~", "~>"):
        return tilde_range(part)
    if operator in (None, "="):
        return equal_range(part)
    return bound_range(operator, part)


def hyphen_range(text: str, spec: str) -> List[Comparator]:
    """Диапазон через дефис: 1.2.3 - 2.3.4."""
    low_text, high_text = (piece.strip() for piece in text.split(" - ", 1))
    low, high = parse_partial(low_text, spec), parse_partial(high_text, spec)
    result: List[Comparator] = []
    if low.major is not None:
        result.append((">=", low.filled()))
    if high.patch is not None:
        result.append(("<=", high.filled()))
    elif high.major is not None:
        result.append(("<", next_up(high)))
    return result


def parse_set(text: str, spec: str) -> List[Comparator]:
    """Разбирает условия, которые должны выполняться одновременно."""
    if " - " in text:
        return hyphen_range(text, spec)
    result: List[Comparator] = []
    for token in GLUED_OPERATOR.sub(r"\1", text).split():
        result.extend(expand_token(token, spec))
    return result


def parse_range(spec: str) -> List[List[Comparator]]:
    """Разбирает диапазон: варианты через || из наборов условий."""
    return [parse_set(part.strip(), spec) for part in spec.split("||")]


def pre_allowed(version: Version, comparators: List[Comparator]) -> bool:
    """Предварительная версия подходит, только если она названа явно."""
    if not version.pre:
        return True
    return any(
        bound.pre and bound.release() == version.release()
        for _, bound in comparators
    )


def matches(version: Version, comparators: List[Comparator]) -> bool:
    """Проверяет версию на все условия одного набора."""
    if not pre_allowed(version, comparators):
        return False
    return all(
        CHECKS[operator](version.key(), bound.key())
        for operator, bound in comparators
    )


def satisfies(version: Version, spec: str) -> bool:
    """Проверяет, подходит ли версия под диапазон."""
    return any(matches(version, group) for group in parse_range(spec))


def choose_version(
    available: List[str], spec: str, tags: Dict[str, str]
) -> Optional[str]:
    """Выбирает версию как npm: метку latest, если подходит, иначе новейшую.

    Вместо диапазона можно указать метку, например latest или next.
    """
    if spec.strip() in tags:
        return tags[spec.strip()]
    parse_range(spec)
    latest = parse_version(tags.get(DEFAULT_TAG, ""))
    if latest and not latest.pre and satisfies(latest, spec):
        return tags[DEFAULT_TAG]
    suitable = [
        (version.key(), text)
        for text, version in ((text, parse_version(text)) for text in available)
        if version and satisfies(version, spec)
    ]
    return max(suitable)[1] if suitable else None