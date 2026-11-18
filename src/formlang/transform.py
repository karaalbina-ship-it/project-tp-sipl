from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

from .grammar import Grammar
from .parsing import nullable_set


@dataclass
class Result:
    grammar: Grammar
    steps: list[str] = field(default_factory=list)


def _set(g: Grammar, xs) -> str:
    order = g.ordered_nonterminals()
    return "{" + ", ".join(sorted(xs, key=lambda s: (order.index(s) if s in order else 99, s))) + "}"


def _rule(g: Grammar, a: str, rhs: tuple[str, ...]) -> str:
    return f"{g.show_symbol(a)} → {g.show_rhs(rhs)}"


def reachable(g: Grammar) -> tuple[set[str], list[set[str]]]:
    chain = [{g.start}]
    while True:
        prev = chain[-1]
        nxt = prev | {s for a, rhs in g.rules if a in prev for s in rhs if g.is_nt(s)}
        if nxt == prev:
            return prev, chain
        chain.append(nxt)


def productive(g: Grammar) -> tuple[set[str], list[set[str]]]:
    def step(prev: set[str]) -> set[str]:
        return prev | {a for a, rhs in g.rules if all(not g.is_nt(s) or s in prev for s in rhs)}

    chain = [step(set())]
    while (nxt := step(chain[-1])) != chain[-1]:
        chain.append(nxt)
    return chain[-1], chain


def remove_useless(g: Grammar) -> Result:
    steps = []
    prod, chain = productive(g)
    steps.append("Продуктивні нетермінали:")
    steps += [f"  Pr{i} = {_set(g, s)}" for i, s in enumerate(chain)]
    bad = g.nonterminals - prod
    steps.append(f"  непродуктивні: {_set(g, bad) if bad else '∅'}")
    if g.start not in prod:
        steps.append("  аксіома непродуктивна ⇒ L(G) = ∅, правил не лишається")
        return Result(Grammar(g.start, [], {g.start}), steps)
    rules = [(a, r) for a, r in g.rules if a in prod and all(not g.is_nt(s) or s in prod for s in r)]
    g1 = Grammar(g.start, rules, g.nonterminals & prod)

    reach, chain = reachable(g1)
    steps.append("Досяжні нетермінали:")
    steps += [f"  R{i} = {_set(g1, s)}" for i, s in enumerate(chain)]
    unreach = g1.nonterminals - reach
    steps.append(f"  недосяжні: {_set(g1, unreach) if unreach else '∅'}")
    g2 = Grammar(g.start, [(a, r) for a, r in g1.rules if a in reach], reach)
    removed = [r for r in g.rules if r not in g2.rules]
    if removed:
        steps.append("Видалені правила: " + "; ".join(_rule(g, a, r) for a, r in removed))
    return Result(g2, steps)


def remove_epsilon(g: Grammar) -> Result:
    null = nullable_set(g)
    steps = [f"ε-нетермінали (A ⇒* ε): {_set(g, null) if null else '∅'}"]
    rules = []
    for a, rhs in g.rules:
        options = [((s,), ()) if s in null else ((s,),) for s in rhs]
        variants = [tuple(x for part in combo for x in part) for combo in product(*options)]
        new = [v for v in dict.fromkeys(variants) if v and v != rhs and (a, v) not in g.rules]
        rules += [(a, v) for v in dict.fromkeys(variants) if v]
        if new:
            steps.append(f"  з {_rule(g, a, rhs)} додаємо: " + " | ".join(g.show_rhs(v) for v in new))
    dropped = [(a, r) for a, r in g.rules if not r]
    if dropped:
        steps.append("Видаляємо ε-правила: " + "; ".join(_rule(g, a, r) for a, r in dropped))
    if g.start in null:
        steps.append(f"Увага: аксіома {g.start} - ε-нетермінал, тобто ε ∈ L(G); нова граматика породжує L(G) \\ {{ε}}")
    return Result(Grammar(g.start, rules, g.nonterminals), steps)


def remove_unit(g: Grammar) -> Result:
    def unit(rhs: tuple[str, ...]) -> bool:
        return len(rhs) == 1 and g.is_nt(rhs[0])

    steps = []
    rules = []
    for a in g.ordered_nonterminals():
        closure, todo = {a}, [a]
        while todo:
            x = todo.pop()
            for rhs in g.rules_for(x):
                if unit(rhs) and rhs[0] not in closure:
                    closure.add(rhs[0])
                    todo.append(rhs[0])
        own = [r for r in g.rules_for(a) if not unit(r)]
        added = [r for b in closure - {a} for r in g.rules_for(b) if not unit(r) and r not in own]
        rules += [(a, r) for r in own + added]
        if len(closure) > 1:
            steps.append(
                f"  {g.show_symbol(a)} ⇒* {_set(g, closure - {a})}"
                + (": додаємо " + " | ".join(g.show_rhs(r) for r in dict.fromkeys(added)) if added else "")
            )
    units = [(a, r) for a, r in g.rules if unit(r)]
    if units:
        steps.insert(0, "Ланцюгові правила: " + "; ".join(_rule(g, a, r) for a, r in units))
    else:
        steps.append("Ланцюгових правил немає")
    return Result(Grammar(g.start, rules, g.nonterminals), steps)


def _fresh(used: set[str], preferred: list[str]) -> str:
    for name in preferred:
        if name not in used:
            used.add(name)
            return name
    k = 1
    while f"N{k}" in used:
        k += 1
    used.add(f"N{k}")
    return f"N{k}"


def is_cnf(g: Grammar) -> bool:
    on_rhs = {s for _, r in g.rules for s in r}
    for a, rhs in g.rules:
        ok = (
            (len(rhs) == 1 and not g.is_nt(rhs[0]))
            or (len(rhs) == 2 and all(g.is_nt(s) for s in rhs))
            or (not rhs and a == g.start and g.start not in on_rhs)
        )
        if not ok:
            return False
    return True


def to_cnf(g: Grammar) -> Result:
    steps: list[str] = []
    has_eps = g.start in nullable_set(g)

    def stage(title: str, res: Result) -> Grammar:
        steps.append(f"== {title} ==")
        steps.extend(res.steps)
        steps.append(str(res.grammar) or "(порожня граматика)")
        return res.grammar

    cur = stage("1. Видалення несуттєвих символів", remove_useless(g))
    cur = stage("2. Видалення ε-правил", remove_epsilon(cur))
    cur = stage("3. Видалення ланцюгових правил", remove_unit(cur))
    cur = stage("4. Повторне видалення несуттєвих символів", remove_useless(cur))

    used = set(cur.nonterminals)
    term_nt: dict[str, str] = {}
    rules = []
    for a, rhs in cur.rules:
        if len(rhs) >= 2:
            new = []
            for s in rhs:
                if not cur.is_nt(s):
                    if s not in term_nt:
                        base = s.upper() if len(s) == 1 and s.isalpha() else "T"
                        term_nt[s] = _fresh(used, [base + "′", base + "′′", base + "′′′"])
                    s = term_nt[s]
                new.append(s)
            rhs = tuple(new)
        rules.append((a, rhs))
    rules += [(nt, (t,)) for t, nt in term_nt.items()]
    cur = Grammar(cur.start, rules, used)
    steps.append("== 5. Заміна терміналів у правилах довжини ≥ 2 ==")
    steps.append(", ".join(f"{cur.show_symbol(n)} → {cur.show_symbol(t)}" for t, n in term_nt.items()) or "не потрібно")

    letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    tail_nt: dict[tuple[str, ...], str] = {}
    rules = []
    log = []
    for a, rhs in cur.rules:
        if len(rhs) <= 2:
            rules.append((a, rhs))
            continue
        log.append(f"{cur.show_symbol(a)} → {cur.show_rhs(rhs)}")
        head = a
        while len(rhs) > 2:
            tail = rhs[1:]
            new = tail_nt.get(tail)
            fresh = new is None
            if fresh:
                new = tail_nt[tail] = _fresh(used, letters)
            rules.append((head, (rhs[0], new)))
            if not fresh:
                break
            head, rhs = new, tail
        else:
            rules.append((head, rhs))
    cur = Grammar(cur.start, rules, used)
    steps.append("== 6. Розбиття правил довжини > 2 ==")
    if log:
        steps.append("Розбиті правила: " + "; ".join(log))
        steps.append("Нові: " + ", ".join(_rule(cur, a, r) for a, r in cur.rules if a in tail_nt.values()))
    else:
        steps.append("не потрібно")

    if has_eps:
        s0 = _fresh(used, [cur.start + "0", cur.start + "′", "S0"])
        cur = Grammar(s0, [(s0, ()), *[(s0, r) for r in cur.rules_for(cur.start)], *cur.rules], used)
        steps.append(f"== 7. ε ∈ L(G): нова аксіома {s0} → ε | (праві частини {g.start}) ==")
    steps.append("== Результат (НФ Хомського) ==")
    steps.append(str(cur))
    return Result(cur, steps)


def show_set(g: Grammar, xs) -> str:
    return _set(g, xs)
