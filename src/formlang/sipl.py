from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.resources import files

from .grammar import Grammar, parse_grammar
from .parsing import Earley, Tree
from .render import Renderer, Source

KEYWORDS = {"begin", "end", "if", "then", "else", "while", "do", "skip"}
ALIASES = {"or": "∨", "not": "¬"}
_TOKEN = re.compile(r"(?P<ws>\s+)|(?P<num>[0-9]+)|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<op>:=|[;+\-*()=>∨¬])")


@dataclass
class Token:
    symbol: str
    text: str
    start: int
    end: int
    line: int
    col: int


class SiplSyntaxError(ValueError):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"{line}:{col}: {message}")
        self.message, self.line, self.col = message, line, col

    def to_dict(self) -> dict:
        return {"message": self.message, "line": self.line, "col": self.col}


def sipl_grammar() -> Grammar:
    return parse_grammar(files("formlang").joinpath("data/sipl.cfg").read_text(encoding="utf-8"))


def lex(text: str) -> list[Token]:
    tokens, pos, line, line_start = [], 0, 1, 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        col = pos - line_start + 1
        if not m:
            raise SiplSyntaxError(f"недопустимий символ '{text[pos]}'", line, col)
        kind, lexeme = m.lastgroup, m.group()
        if kind == "ws":
            for k, ch in enumerate(lexeme):
                if ch == "\n":
                    line, line_start = line + 1, pos + k + 1
        elif kind == "num":
            tokens.append(Token("%number", lexeme, pos, m.end(), line, col))
        elif kind == "id":
            sym = lexeme if lexeme in KEYWORDS else ALIASES.get(lexeme, "%ident")
            tokens.append(Token(sym, lexeme, pos, m.end(), line, col))
        else:
            tokens.append(Token(lexeme, lexeme, pos, m.end(), line, col))
        pos = m.end()
    return tokens


_NAMES = {"%ident": "змінна", "%number": "число"}


@dataclass
class SiplParse:
    source: str
    tokens: list[Token]
    trees: list[Tree]
    renderer: Renderer

    @property
    def tree(self) -> Tree:
        return self.trees[0]

    @property
    def ambiguous(self) -> bool:
        return len(self.trees) > 1

    def leaf_check(self) -> tuple[str, bool]:
        leaves = self.renderer.leaf_yield(self.tree)
        return " ".join(leaves), leaves == [t.text for t in self.tokens]


def parse_program(text: str, max_trees: int = 2) -> SiplParse:
    g = sipl_grammar()
    tokens = lex(text)
    word = tuple(t.symbol for t in tokens)
    e = Earley(g, word)
    if err := e.error():
        expected = ", ".join(f"'{_NAMES.get(s, s)}'" for s in err.expected) or "нічого"
        if err.found is None:
            last = tokens[-1] if tokens else None
            line, col = (last.line, last.col + len(last.text)) if last else (1, 1)
            raise SiplSyntaxError(f"неочікуваний кінець програми; очікувалось: {expected}", line, col)
        tok = tokens[err.position]
        raise SiplSyntaxError(f"неочікуваний токен '{tok.text}'; очікувалось: {expected}", tok.line, tok.col)
    src = Source(text, [(t.start, t.end, t.line, t.col) for t in tokens])
    return SiplParse(text, tokens, e.trees(max_trees), Renderer(g, word, src))
