from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .grammar import EPS, Grammar


@dataclass
class Tree:

    symbol: str
    start: int
    end: int
    children: list[Tree] = field(default_factory=list)
    terminal: bool = False

    @property
    def is_epsilon(self) -> bool:
        return self.symbol == EPS and self.terminal

    def leaves(self) -> list[Tree]:
        if not self.children:
            return [self]
        return [leaf for c in self.children for leaf in c.leaves()]

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)


@dataclass
class ParseError:
    position: int
    found: str | None
    expected: list[str]


def nullable_set(g: Grammar) -> set[str]:
    result: set[str] = set()
    changed = True
    while changed:
        changed = False
        for a, rhs in g.rules:
            if a not in result and all(s in result for s in rhs):
                result.add(a)
                changed = True
    return result


class Earley:
    def __init__(self, g: Grammar, word: tuple[str, ...] | list[str]):
        self.g = g
        self.word = tuple(word)
        self.nullable = nullable_set(g)
        self.ends: dict[tuple[str, int], set[int]] = defaultdict(set)
        self.sets = self._run()

    def _run(self) -> list[set]:
        g, w, n = self.g, self.word, len(self.word)
        rules = g.rules
        by_lhs: dict[str, list[int]] = defaultdict(list)
        for idx, (a, _) in enumerate(rules):
            by_lhs[a].append(idx)
        sets: list[set] = [set() for _ in range(n + 1)]
        waiting: list[dict[str, list]] = [defaultdict(list) for _ in range(n + 1)]

        def add(i: int, item: tuple[int, int, int], agenda: list | None) -> None:
            if item not in sets[i]:
                sets[i].add(item)
                r, d, _ = item
                rhs = rules[r][1]
                if d < len(rhs):
                    waiting[i][rhs[d]].append(item)
                if agenda is not None:
                    agenda.append(item)

        for r in by_lhs[g.start]:
            add(0, (r, 0, 0), None)
        for i in range(n + 1):
            agenda = list(sets[i])
            while agenda:
                r, d, o = agenda.pop()
                lhs, rhs = rules[r]
                if d == len(rhs):
                    self.ends[(lhs, o)].add(i)
                    for r2, d2, o2 in list(waiting[o][lhs]):
                        add(i, (r2, d2 + 1, o2), agenda)
                    continue
                x = rhs[d]
                if g.is_nt(x):
                    for r2 in by_lhs[x]:
                        add(i, (r2, 0, i), agenda)
                    if x in self.nullable:
                        add(i, (r, d + 1, o), agenda)
                elif i < n and w[i] == x:
                    add(i + 1, (r, d + 1, o), None)
        return sets

    @property
    def accepted(self) -> bool:
        return len(self.word) in self.ends.get((self.g.start, 0), ())

    def error(self) -> ParseError | None:
        if self.accepted:
            return None
        n = len(self.word)
        last = max(i for i in range(n + 1) if self.sets[i])
        expected = sorted(
            {
                self.g.rules[r][1][d]
                for r, d, _ in self.sets[last]
                if d < len(self.g.rules[r][1]) and not self.g.is_nt(self.g.rules[r][1][d])
            }
        )
        return ParseError(last, self.word[last] if last < n else None, expected)


    def trees(self, limit: int = 2) -> list[Tree]:
        if not self.accepted:
            return []
        self._limit, self._memo, self._stack, self._cut = limit, {}, set(), False
        return self._trees(self.g.start, 0, len(self.word))

    def _trees(self, a: str, i: int, j: int) -> list[Tree]:
        key = (a, i, j)
        if key in self._memo:
            return self._memo[key]
        if key in self._stack:
            self._cut = True
            return []
        self._stack.add(key)
        outer_cut, self._cut = self._cut, False
        out: list[Tree] = []
        for rhs in self.g.rules_for(a):
            for kids in self._splits(rhs, 0, i, j):
                out.append(Tree(a, i, j, kids or [Tree(EPS, i, i, terminal=True)]))
                if len(out) >= self._limit:
                    break
            if len(out) >= self._limit:
                break
        self._stack.discard(key)
        if not self._cut:
            self._memo[key] = out
        self._cut = self._cut or outer_cut
        return out

    def _splits(self, rhs: tuple[str, ...], k: int, p: int, j: int) -> list[list[Tree]]:
        if k == len(rhs):
            return [[]] if p == j else []
        sym = rhs[k]
        if not self.g.is_nt(sym):
            if p < j and self.word[p] == sym:
                leaf = Tree(sym, p, p + 1, terminal=True)
                return [[leaf, *rest] for rest in self._splits(rhs, k + 1, p + 1, j)]
            return []
        res: list[list[Tree]] = []
        for q in sorted(self.ends.get((sym, p), ())):
            if q > j:
                continue
            rests = self._splits(rhs, k + 1, q, j)
            if not rests:
                continue
            for sub in self._trees(sym, p, q):
                for rest in rests:
                    res.append([sub, *rest])
                    if len(res) >= self._limit:
                        return res
        return res


def accepts(g: Grammar, word: tuple[str, ...]) -> bool:
    return Earley(g, word).accepted


Step = tuple[tuple[str, ...], "tuple[str, tuple[str, ...]] | None"]


def derivation(tree: Tree, leftmost: bool = True) -> list[Step]:
    frontier: list[Tree] = [tree]
    steps: list[Step] = [((tree.symbol,), None)]
    while True:
        idx = [k for k, t in enumerate(frontier) if not t.terminal]
        if not idx:
            return steps
        k = idx[0] if leftmost else idx[-1]
        node = frontier[k]
        kids = [c for c in node.children if not c.is_epsilon]
        frontier[k : k + 1] = kids
        steps.append((tuple(t.symbol for t in frontier), (node.symbol, tuple(c.symbol for c in kids))))
