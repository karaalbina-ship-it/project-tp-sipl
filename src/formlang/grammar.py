from __future__ import annotations

import re
from dataclasses import dataclass, field

EPS = "ε"
_ARROW = re.compile(r"->|→|::=")
_NT = re.compile(r"[A-Z][′'0-9]*")
_SIMPLE_T = re.compile(r"[^\sA-Z<>\"%|ε]")

Rule = tuple[str, tuple[str, ...]]


class GrammarError(ValueError):

    def __init__(self, message: str, line: int | None = None):
        super().__init__(f"рядок {line}: {message}" if line else message)
        self.line = line


@dataclass
class Grammar:
    start: str
    rules: list[Rule]
    nonterminals: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.rules = list(dict.fromkeys((a, tuple(r)) for a, r in self.rules))
        self.nonterminals = set(self.nonterminals) | {self.start} | {a for a, _ in self.rules}

    @property
    def terminals(self) -> set[str]:
        return {s for _, rhs in self.rules for s in rhs if s not in self.nonterminals}

    def is_nt(self, sym: str) -> bool:
        return sym in self.nonterminals

    def rules_for(self, lhs: str) -> list[tuple[str, ...]]:
        return [rhs for a, rhs in self.rules if a == lhs]

    def ordered_nonterminals(self) -> list[str]:
        order = [self.start]
        for a, rhs in self.rules:
            order += [a, *(s for s in rhs if s in self.nonterminals)]
        order += sorted(self.nonterminals)
        return list(dict.fromkeys(order))

    def compact(self) -> bool:
        return all(_NT.fullmatch(s) for s in self.nonterminals) and all(
            len(s) == 1 and _SIMPLE_T.fullmatch(s) for s in self.terminals
        )

    def show_symbol(self, sym: str) -> str:
        if sym in self.nonterminals:
            return sym if _NT.fullmatch(sym) else f"<{sym}>"
        if sym.startswith("%") or (len(sym) == 1 and _SIMPLE_T.fullmatch(sym)):
            return sym
        return f'"{sym}"'

    def show_rhs(self, rhs: tuple[str, ...]) -> str:
        if not rhs:
            return EPS
        sep = "" if self.compact() else " "
        return sep.join(self.show_symbol(s) for s in rhs)

    def show_form(self, form: tuple[str, ...]) -> str:
        return self.show_rhs(tuple(form))

    def to_text(self) -> str:
        lines = []
        for a in self.ordered_nonterminals():
            alts = self.rules_for(a)
            if alts:
                lines.append(f"{self.show_symbol(a)} → " + " | ".join(self.show_rhs(r) for r in alts))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_text()

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "nonterminals": self.ordered_nonterminals(),
            "terminals": sorted(self.terminals),
            "rules": [{"lhs": a, "rhs": list(r)} for a, r in self.rules],
        }


def _tokenize_rhs(text: str, line: int) -> list[tuple[str, bool] | None]:
    out: list[tuple[str, bool] | None] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "|":
            out.append(None)
            i += 1
        elif ch == EPS:
            i += 1
        elif ch == "<":
            j = text.find(">", i)
            if j < 0:
                raise GrammarError("незакрита '<'", line)
            out.append((text[i + 1 : j].strip(), True))
            i = j + 1
        elif ch == '"':
            j = text.find('"', i + 1)
            if j < 0:
                raise GrammarError("незакрита '\"'", line)
            if j > i + 1:
                out.append((text[i + 1 : j], False))
            i = j + 1
        elif ch == "%":
            m = re.compile(r"%\w+").match(text, i)
            if not m:
                raise GrammarError("після '%' очікується назва класу терміналів", line)
            out.append((m.group(), False))
            i = m.end()
        elif m := _NT.match(text, i):
            out.append((m.group(), True))
            i = m.end()
        else:
            out.append((ch, False))
            i += 1
    return out


def _lhs(text: str, line: int) -> str:
    text = text.strip()
    if m := re.fullmatch(r"<([^<>]+)>", text):
        return m.group(1).strip()
    if _NT.fullmatch(text):
        return text
    raise GrammarError(f"ліва частина має бути нетерміналом, отримано '{text}'", line)


def parse_grammar(text: str) -> Grammar:
    rules: list[Rule] = []
    nts: set[str] = set()
    terms: set[str] = set()
    for no, raw in enumerate(text.splitlines(), 1):
        src = raw.strip()
        if not src or src.startswith("#"):
            continue
        parts = _ARROW.split(src, maxsplit=1)
        if len(parts) != 2:
            raise GrammarError("очікується правило вигляду 'A -> α | β'", no)
        lhs = _lhs(parts[0], no)
        alt: list[str] = []
        for tok in [*_tokenize_rhs(parts[1], no), None]:
            if tok is None:
                rules.append((lhs, tuple(alt)))
                alt = []
            else:
                sym, is_nt = tok
                alt.append(sym)
                (nts if is_nt else terms).add(sym)
    if not rules:
        raise GrammarError("граматика не містить жодного правила")
    g = Grammar(rules[0][0], rules, nts)
    if bad := terms & g.nonterminals:
        raise GrammarError(f"символ одночасно термінал і нетермінал: {sorted(bad)}")
    return g


def split_word(word: str) -> tuple[str, ...]:
    word = word.strip()
    if word in ("", EPS):
        return ()
    return tuple(word.split()) if " " in word else tuple(word)
