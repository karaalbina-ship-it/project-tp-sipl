from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import product

from .grammar import EPS, Grammar, GrammarError
from .words import Word, generate_words, show_language, show_word

_VAR = re.compile(r"[A-Z][′'0-9]*")

Expr = tuple


@dataclass
class System:
    equations: dict[str, Expr]

    @property
    def main(self) -> str:
        return next(iter(self.equations))

    def to_text(self) -> str:
        return "\n".join(f"{v} = {show_expr(e)}" for v, e in self.equations.items())


class _Parser:
    def __init__(self, text: str, line: int):
        self.s, self.i, self.line = text, 0, line

    def err(self, msg: str) -> GrammarError:
        return GrammarError(f"{msg} (позиція {self.i + 1})", self.line)

    def peek(self) -> str:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1
        return self.s[self.i] if self.i < len(self.s) else ""

    def union(self) -> Expr:
        parts = [self.cat()]
        while self.peek() in ("∪", "|"):
            self.i += 1
            parts.append(self.cat())
        return parts[0] if len(parts) == 1 else ("union", parts)

    def cat(self) -> Expr:
        parts = []
        while (ch := self.peek()) and ch not in "∪|)":
            if ch == "·":
                self.i += 1
                continue
            parts.append(self.atom())
        if not parts:
            raise self.err("очікується вираз")
        return parts[0] if len(parts) == 1 else ("cat", parts)

    def atom(self) -> Expr:
        ch = self.peek()
        if ch == "(":
            self.i += 1
            e = self.union()
            if self.peek() != ")":
                raise self.err("очікується ')'")
            self.i += 1
            return e
        if ch == "{":
            j = self.s.find("}", self.i)
            if j < 0:
                raise self.err("незакрита '{'")
            body, self.i = self.s[self.i + 1 : j], j + 1
            words = {_word(w) for w in body.split(",")} if body.strip() else set()
            return ("const", frozenset(words))
        if m := _VAR.match(self.s, self.i):
            self.i = m.end()
            return ("var", m.group())
        self.i += 1
        if ch == EPS:
            return ("const", frozenset({()}))
        if ch == "∅":
            return ("const", frozenset())
        return ("const", frozenset({(ch,)}))


def _word(text: str) -> Word:
    text = text.strip()
    if text in ("", EPS):
        return ()
    return tuple(text.split()) if " " in text else tuple(text)


def parse_system(text: str) -> System:
    eqs: dict[str, Expr] = {}
    for no, raw in enumerate(text.splitlines(), 1):
        src = raw.strip()
        if not src or src.startswith("#"):
            continue
        if "=" not in src:
            raise GrammarError("очікується рівняння 'X = вираз'", no)
        lhs, rhs = (p.strip() for p in src.split("=", 1))
        if not _VAR.fullmatch(lhs):
            raise GrammarError(f"ліва частина має бути змінною, отримано '{lhs}'", no)
        p = _Parser(rhs, no)
        e = p.union()
        if p.peek():
            raise p.err(f"зайвий символ '{p.peek()}'")
        eqs[lhs] = ("union", [eqs[lhs], e]) if lhs in eqs else e
    if not eqs:
        raise GrammarError("система не містить рівнянь")
    unknown = {v for e in eqs.values() for v in _vars(e)} - eqs.keys()
    if unknown:
        raise GrammarError(f"змінні без рівнянь: {sorted(unknown)}")
    return System(eqs)


def _vars(e: Expr) -> set[str]:
    if e[0] == "var":
        return {e[1]}
    if e[0] == "const":
        return set()
    return set().union(*(_vars(x) for x in e[1]))


def show_expr(e: Expr) -> str:
    kind = e[0]
    if kind == "var":
        return e[1]
    if kind == "const":
        return "{" + ", ".join(show_word(w) for w in sorted(e[1], key=lambda w: (len(w), w))) + "}" if e[1] else "∅"
    if kind == "cat":
        return "".join(f"({show_expr(x)})" if x[0] == "union" else show_expr(x) for x in e[1])
    return " ∪ ".join(show_expr(x) for x in e[1])


def from_grammar(g: Grammar) -> System:
    if not g.compact():
        raise GrammarError("для системи рівнянь нетермінали мають бути вигляду A, S0, A′")
    eqs: dict[str, Expr] = {}
    for a in g.ordered_nonterminals():
        alts: list[Expr] = []
        for rhs in g.rules_for(a):
            items: list[Expr] = []
            buf: list[str] = []
            for s in rhs:
                if g.is_nt(s):
                    if buf:
                        items.append(("const", frozenset({tuple(buf)})))
                        buf = []
                    items.append(("var", s))
                else:
                    buf.append(s)
            if buf or not items:
                items.append(("const", frozenset({tuple(buf)})))
            alts.append(items[0] if len(items) == 1 else ("cat", items))
        eqs[a] = ("const", frozenset()) if not alts else alts[0] if len(alts) == 1 else ("union", alts)
    return System(eqs)


def _expand(e: Expr) -> list[list[tuple[bool, object]]]:
    kind = e[0]
    if kind == "var":
        return [[(True, e[1])]]
    if kind == "const":
        return [[(False, w)] for w in sorted(e[1], key=lambda w: (len(w), w))]
    if kind == "union":
        return [seq for x in e[1] for seq in _expand(x)]
    return [[it for part in combo for it in part] for combo in product(*(_expand(x) for x in e[1]))]


def to_grammar(sys: System) -> Grammar:
    rules = []
    for v, e in sys.equations.items():
        for seq in _expand(e):
            rhs: list[str] = []
            for is_var, x in seq:
                rhs += [x] if is_var else list(x)
            rules.append((v, tuple(rhs)))
    return Grammar(sys.main, rules, set(sys.equations))


Interp = dict[str, frozenset]


def evaluate(e: Expr, nu: Interp, max_len: int) -> frozenset:
    kind = e[0]
    if kind == "var":
        return nu[e[1]]
    if kind == "const":
        return frozenset(w for w in e[1] if len(w) <= max_len)
    if kind == "union":
        return frozenset().union(*(evaluate(x, nu, max_len) for x in e[1]))
    acc = frozenset({()})
    for x in e[1]:
        right = evaluate(x, nu, max_len)
        acc = frozenset(u + v for u in acc for v in right if len(u) + len(v) <= max_len)
        if not acc:
            break
    return acc


def approximations(sys: System, iterations: int, max_len: int) -> list[Interp]:
    cur: Interp = {v: frozenset() for v in sys.equations}
    chain = [cur]
    for _ in range(iterations):
        cur = {v: evaluate(e, cur, max_len) for v, e in sys.equations.items()}
        chain.append(cur)
    return chain


def least_solution(sys: System, max_len: int, cap: int = 10_000) -> tuple[Interp, int]:
    cur: Interp = {v: frozenset() for v in sys.equations}
    for k in range(cap):
        nxt = {v: evaluate(e, cur, max_len) for v, e in sys.equations.items()}
        if nxt == cur:
            return cur, k
        cur = nxt
    raise RuntimeError("наближення не стабілізувались")


@dataclass
class Comparison:
    max_len: int
    stable_at: int
    from_equations: frozenset
    from_grammar: frozenset

    @property
    def equal(self) -> bool:
        return self.from_equations == self.from_grammar


def compare(sys: System, max_len: int, grammar: Grammar | None = None) -> Comparison:
    sol, k = least_solution(sys, max_len)
    g = grammar or to_grammar(sys)
    return Comparison(max_len, k, sol[sys.main], frozenset(generate_words(g, max_len)))


def show_approximations(sys: System, chain: list[Interp], limit: int = 12) -> str:
    lines = []
    for i, nu in enumerate(chain):
        lines.append(", ".join(f"{v}{i} = {show_language(nu[v], limit)}" for v in sys.equations))
    return "\n".join(lines)
