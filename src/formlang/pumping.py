from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .grammar import Grammar, GrammarError
from .parsing import accepts
from .words import Word, show_word

_PART = re.compile(r"\s*(\([^()]+\)|[^\s^(){}])(?:\^(\{[^}]*\}|[0-9]*n?|[0-9]+))?")


@dataclass
class Pattern:

    parts: list[tuple[str, int, int]]
    min_n: int = 0
    text: str = ""

    def word(self, n: int) -> Word:
        return tuple(ch for w, a, b in self.parts for ch in w * (a * n + b))

    def length(self, n: int) -> int:
        return sum(len(w) * (a * n + b) for w, a, b in self.parts)

    def contains(self, w: Word) -> bool:
        n = self.min_n
        while self.length(n) <= len(w):
            if self.length(n) == len(w) and self.word(n) == w:
                return True
            if self.length(n + 1) == self.length(n):
                return False
            n += 1
        return False

    def __str__(self) -> str:
        return f"{{{self.text} | n ≥ {self.min_n}}}"


def _linear(expr: str) -> tuple[int, int]:
    expr = expr.strip("{} ").replace(" ", "")
    if not expr:
        return 0, 1
    m = re.fullmatch(r"(?:(\d*)n)?(?:([+-]?)(\d+))?", expr)
    if not m or (m.group(1) is None and not m.group(3)):
        raise GrammarError(f"показник має бути вигляду an+b, отримано '{expr}'")
    a = 0 if "n" not in expr else int(m.group(1) or 1)
    b = int(m.group(3) or 0) * (-1 if m.group(2) == "-" else 1)
    return a, b


def parse_pattern(text: str, min_n: int = 0) -> Pattern:
    parts = []
    pos = 0
    src = text.strip()
    while pos < len(src):
        m = _PART.match(src, pos)
        if not m or m.end() == pos:
            raise GrammarError(f"не вдалося розібрати шаблон біля '{src[pos:]}'")
        base = m.group(1).strip("()")
        a, b = _linear(m.group(2)) if m.group(2) is not None else (0, 1)
        if a < 0 or a * min_n + b < 0:
            raise GrammarError(f"від'ємний показник у частині '{m.group(0).strip()}'")
        parts.append((base, a, b))
        pos = m.end()
        while pos < len(src) and src[pos].isspace():
            pos += 1
    if not parts:
        raise GrammarError("порожній шаблон")
    return Pattern(parts, min_n, src)


@dataclass
class Decomposition:
    u: Word
    t1: Word
    x: Word
    t2: Word
    v: Word
    pumped: list[tuple[int, Word, bool]] = field(default_factory=list)

    @property
    def survives(self) -> bool:
        return all(ok for _, _, ok in self.pumped)

    def show(self) -> str:
        def s(w: Word) -> str:
            return "".join(w)

        return f"{s(self.u)}[{s(self.t1)}]{s(self.x)}[{s(self.t2)}]{s(self.v)}"

    def to_dict(self) -> dict:
        return {
            "u": "".join(self.u),
            "t1": "".join(self.t1),
            "x": "".join(self.x),
            "t2": "".join(self.t2),
            "v": "".join(self.v),
            "survives": self.survives,
            "pumped": [{"i": i, "word": show_word(w), "in_language": ok} for i, w, ok in self.pumped],
        }


def pump(d: Decomposition, member: Callable[[Word], bool], max_i: int) -> Decomposition:
    d.pumped = []
    for i in range(max_i + 1):
        w = d.u + d.t1 * i + d.x + d.t2 * i + d.v
        ok = member(w)
        d.pumped.append((i, w, ok))
        if not ok:
            break
    return d


def decompositions(w: Word, k: int):
    n = len(w)
    for start in range(n):
        for end in range(start + 1, min(start + k, n) + 1):
            for a in range(start, end + 1):
                for b in range(a, end + 1):
                    if a - start + end - b == 0:
                        continue
                    yield Decomposition(w[:start], w[start:a], w[a:b], w[b:end], w[end:])


@dataclass
class KReport:
    k: int
    word: Word
    total: int
    surviving: list[Decomposition]
    killed_examples: list[Decomposition]

    @property
    def witness(self) -> bool:
        return not self.surviving


def explore_word(member, w: Word, k: int, max_i: int = 3, keep: int = 5) -> KReport:
    cache: dict[Word, bool] = {}

    def m(x: Word) -> bool:
        if x not in cache:
            cache[x] = member(x)
        return cache[x]

    surviving, killed, total = [], [], 0
    for d in decompositions(w, k):
        total += 1
        pump(d, m, max_i)
        if d.survives:
            surviving.append(d)
        elif len(killed) < keep:
            killed.append(d)
    return KReport(k, w, total, surviving, killed)


def make_member(lang: Pattern | Grammar) -> Callable[[Word], bool]:
    if isinstance(lang, Pattern):
        return lang.contains
    return lambda w: accepts(lang, w)


def word_for_k(lang: Pattern, k: int) -> Word:
    n = lang.min_n
    while lang.length(n) < k:
        if lang.length(n + 1) == lang.length(n):
            raise GrammarError("шаблон задає скінченну мову - для неї лема виконується тривіально")
        n += 1
    return lang.word(n)


def explore(lang: Pattern, k_max: int, max_i: int = 3) -> list[KReport]:
    member = make_member(lang)
    return [explore_word(member, word_for_k(lang, k), k, max_i) for k in range(1, k_max + 1)]
