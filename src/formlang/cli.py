from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .equations import (
    approximations,
    compare,
    from_grammar,
    parse_system,
    show_approximations,
    to_grammar,
)
from .grammar import Grammar, GrammarError, parse_grammar, split_word
from .parsing import Earley, derivation, nullable_set
from .pumping import Decomposition, explore, explore_word, make_member, parse_pattern, pump
from .render import Renderer
from .sipl import SiplSyntaxError, parse_program
from .transform import productive, reachable, remove_epsilon, remove_unit, remove_useless, show_set, to_cnf
from .words import generate_words, show_language, show_word

OK, NOT_IN_LANGUAGE, BAD_INPUT, IO_ERROR = 0, 1, 2, 5


class CliError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise CliError(f"не вдалося прочитати '{path}': {e.strerror}", IO_ERROR) from e


def _grammar(path: str) -> Grammar:
    return parse_grammar(_read(path))


def _emit(args, text: str, data: dict) -> None:
    if getattr(args, "json", False):
        text = json.dumps({"schema_version": 1, "command": args.command, **data}, ensure_ascii=False, indent=2)
    out = getattr(args, "output", None)
    if out:
        try:
            Path(out).write_text(text + "\n", encoding="utf-8")
        except OSError as e:
            raise CliError(f"не вдалося записати '{out}': {e.strerror}", IO_ERROR) from e
        print(f"записано: {out}")
    else:
        print(text)


def cmd_analyze(args) -> int:
    g = _grammar(args.grammar)
    reach, rchain = reachable(g)
    prod, pchain = productive(g)
    null = nullable_set(g)
    terms = ", ".join(sorted(g.terminals))
    lines = [str(g), "", f"N = {show_set(g, g.nonterminals)}, T = {{{terms}}}, S = {g.start}", ""]
    lines += ["Досяжні:"] + [f"  R{i} = {show_set(g, s)}" for i, s in enumerate(rchain)]
    lines += ["Продуктивні:"] + [f"  Pr{i} = {show_set(g, s)}" for i, s in enumerate(pchain)]
    lines += [
        f"Недосяжні: {show_set(g, g.nonterminals - reach) if g.nonterminals - reach else '∅'}",
        f"Непродуктивні: {show_set(g, g.nonterminals - prod) if g.nonterminals - prod else '∅'}",
        f"ε-нетермінали: {show_set(g, null) if null else '∅'}",
        f"L(G) {'порожня' if g.start not in prod else 'непорожня'}; ε {'∈' if g.start in null else '∉'} L(G)",
    ]
    data = {
        "grammar": g.to_dict(),
        "reachable": [sorted(s) for s in rchain],
        "productive": [sorted(s) for s in pchain],
        "unreachable": sorted(g.nonterminals - reach),
        "unproductive": sorted(g.nonterminals - prod),
        "nullable": sorted(null),
    }
    _emit(args, "\n".join(lines), data)
    return OK


def cmd_transform(args) -> int:
    g = _grammar(args.grammar)
    fn = {"reduce": remove_useless, "eps": remove_epsilon, "unit": remove_unit, "cnf": to_cnf}[args.command]
    res = fn(g)
    lines = list(res.steps)
    if args.command != "cnf":
        lines += ["", "Результат:", str(res.grammar) or "(порожня граматика)"]
    data = {"steps": res.steps, "grammar": res.grammar.to_dict()}
    if args.check is not None:
        a, b = generate_words(g, args.check), generate_words(res.grammar, args.check)
        if args.command == "eps":
            a.discard(())
        same = a == b
        lines += ["", f"Перевірка еквівалентності на словах довжини ≤ {args.check}: "
                  f"{'збігаються' if same else 'НЕ збігаються'} ({len(a)} слів)"]
        if not same:
            lines.append(f"  лише в G: {show_language(a - b)}; лише в G′: {show_language(b - a)}")
        data["check"] = {"max_len": args.check, "equal": same, "words": len(a)}
    _emit(args, "\n".join(lines), data)
    return OK


def cmd_derive(args) -> int:
    g = _grammar(args.grammar)
    word = split_word(args.word)
    e = Earley(g, word)
    if not e.accepted:
        err = e.error()
        where = "кінець слова" if err.found is None else f"символ '{err.found}' (позиція {err.position + 1})"
        exp = ", ".join(err.expected) or "—"
        raise CliError(f"слово '{show_word(word)}' ∉ L(G): неочікуваний {where}; очікувалось: {exp}", NOT_IN_LANGUAGE)
    trees = e.trees(args.max_trees)
    r = Renderer(g, word)
    if args.format in ("dot", "svg"):
        t = trees[min(args.tree, len(trees)) - 1]
        _emit(args, r.dot(t) if args.format == "dot" else r.svg(t), {})
        return OK

    def show_derivation(t, leftmost: bool) -> list[str]:
        steps = derivation(t, leftmost)
        return [
            ("  " if rule is None else "  ⇒ ") + g.show_form(form)
            + ("" if rule is None else f"    [{g.show_symbol(rule[0])} → {g.show_rhs(rule[1])}]")
            for form, rule in steps
        ]

    amb = len(trees) > 1
    lines = [f"Слово '{show_word(word)}' ∈ L(G).",
             f"Знайдено дерев виводу: {len(trees)}{'+' if len(trees) == args.max_trees else ''} "
             f"⇒ {'граматика НЕОДНОЗНАЧНА для цього слова' if amb else 'дерево єдине'}"]
    data_trees = []
    for i, t in enumerate(trees, 1):
        lines += ["", f"Дерево {i} (глибина {t.depth()}):", r.text(t),
                  "Лівостороннє виведення:", *show_derivation(t, True),
                  "Правостороннє виведення:", *show_derivation(t, False)]
        data_trees.append({
            "tree": r.to_dict(t),
            "leftmost": [list(f) for f, _ in derivation(t, True)],
            "rightmost": [list(f) for f, _ in derivation(t, False)],
        })
    _emit(args, "\n".join(lines), {"word": list(word), "accepted": True, "ambiguous": amb, "trees": data_trees})
    return OK


def cmd_words(args) -> int:
    g = _grammar(args.grammar)
    ws = generate_words(g, args.max_len)
    _emit(args, f"L(G) ∩ T^≤{args.max_len} ({len(ws)} слів): {show_language(ws, args.limit)}",
          {"max_len": args.max_len, "words": [show_word(w) for w in sorted(ws, key=lambda w: (len(w), w))]})
    return OK


def _system_or_grammar(path: str):
    text = _read(path)
    if any(a in text for a in ("->", "→", "::=")):
        g = parse_grammar(text)
        return from_grammar(g), g
    return parse_system(text), None


def cmd_equations(args) -> int:
    sys_, _ = _system_or_grammar(args.file)
    _emit(args, sys_.to_text(), {"system": sys_.to_text().splitlines()})
    return OK


def cmd_to_grammar(args) -> int:
    sys_, _ = _system_or_grammar(args.file)
    g = to_grammar(sys_)
    _emit(args, str(g), {"grammar": g.to_dict()})
    return OK


def cmd_solve(args) -> int:
    sys_, g = _system_or_grammar(args.file)
    chain = approximations(sys_, args.iterations, args.max_len)
    cmp = compare(sys_, args.max_len, g)
    lines = ["Система:", sys_.to_text(), "",
             f"Наближення R(i) (слова довжини ≤ {args.max_len}):", show_approximations(sys_, chain, args.limit), "",
             f"Стабілізація зрізаних наближень на кроці {cmp.stable_at}.",
             f"R(E) ∩ T^≤{args.max_len} = {show_language(cmp.from_equations, args.limit)}",
             f"L(G) ∩ T^≤{args.max_len} = {show_language(cmp.from_grammar, args.limit)}  (ліві виведення)",
             "Збігаються ✓" if cmp.equal else "НЕ збігаються ✗"]
    if not cmp.equal:
        lines.append(f"  лише в R(E): {show_language(cmp.from_equations - cmp.from_grammar)}; "
                     f"лише в L(G): {show_language(cmp.from_grammar - cmp.from_equations)}")
    data = {
        "system": sys_.to_text().splitlines(),
        "approximations": [{v: [show_word(w) for w in sorted(s, key=lambda w: (len(w), w))] for v, s in nu.items()}
                           for nu in chain],
        "stable_at": cmp.stable_at,
        "equal": cmp.equal,
    }
    _emit(args, "\n".join(lines), data)
    return OK if cmp.equal else NOT_IN_LANGUAGE


def _show_report(rep, max_i: int, verbose: bool) -> list[str]:
    w = show_word(rep.word)
    lines = [f"k = {rep.k}: слово t = {w} (|t| = {len(rep.word)}), розкладів: {rep.total}, "
             f"витримали накачування (i = 0..{max_i}): {len(rep.surviving)}"]
    if rep.witness:
        lines.append("  ✗ жоден розклад не витримав - t є контрприкладом для цього k")
    else:
        d = rep.surviving[0]
        lines.append(f"  ✓ напр. u[t1]x[t2]v = {d.show()}")
    if verbose:
        for d in rep.killed_examples:
            i, bad, _ = d.pumped[-1]
            lines.append(f"    {d.show()}: i = {i} дає {show_word(bad)} ∉ L")
    return lines


DISCLAIMER = ("Це асистент: перевірено лише скінченну кількість k та i ≤ max_i. "
              "Контрприклади - свідчення, а не доведення того, що мова не КВ.")


def cmd_pump(args) -> int:
    if args.grammar:
        lang = _grammar(args.grammar)
        if not args.word:
            raise CliError("для мови, заданої граматикою, вкажіть --word", BAD_INPUT)
    else:
        if not args.pattern:
            raise CliError("вкажіть шаблон мови або --grammar", BAD_INPUT)
        lang = parse_pattern(args.pattern, args.min_n)
    member = make_member(lang)
    lines = [f"L = {lang}" if not args.grammar else f"L = L(G), G з {args.grammar}"]
    data: dict = {"disclaimer": DISCLAIMER}

    if args.decomp:
        parts = args.decomp.split(",")
        if len(parts) != 5:
            raise CliError("--decomp має містити 5 частин: u,t1,x,t2,v", BAD_INPUT)
        u, t1, x, t2, v = (split_word(p) if p.strip() != "" else () for p in parts)
        if not t1 and not t2:
            raise CliError("має бути |t1 t2| ≥ 1", BAD_INPUT)
        d = Decomposition(u, t1, x, t2, v)
        pump(d, member, args.max_i)
        d.pumped = [(i, d.u + d.t1 * i + d.x + d.t2 * i + d.v, member(d.u + d.t1 * i + d.x + d.t2 * i + d.v))
                    for i in range(args.max_i + 1)]
        lines.append(f"Розклад {d.show()}  (|t1 x t2| = {len(t1 + x + t2)})")
        lines += [f"  i = {i}: {show_word(w)} {'∈' if ok else '∉'} L" for i, w, ok in d.pumped]
        lines.append("Витримує накачування ✓" if d.survives else "Не витримує ✗")
        data["decomposition"] = d.to_dict()
    elif args.word is not None:
        word = split_word(args.word)
        if not member(word):
            raise CliError(f"слово '{show_word(word)}' ∉ L", NOT_IN_LANGUAGE)
        k = args.k or len(word)
        rep = explore_word(member, word, k, args.max_i)
        lines += _show_report(rep, args.max_i, args.verbose)
        data["reports"] = [_report_dict(rep)]
    else:
        reps = explore(lang, args.k_max, args.max_i)
        for rep in reps:
            lines += _show_report(rep, args.max_i, args.verbose)
        all_w = all(r.witness for r in reps)
        lines.append("")
        lines.append(f"Для всіх k ≤ {args.k_max} знайдено контрприклад ⇒ є підстави вважати, що L не КВ."
                     if all_w else "Лему для деяких k не спростовано (це не доводить, що L - КВ).")
        data["reports"] = [_report_dict(r) for r in reps]
        data["all_witnesses"] = all_w
    lines += ["", DISCLAIMER]
    _emit(args, "\n".join(lines), data)
    return OK


def _report_dict(rep) -> dict:
    return {
        "k": rep.k,
        "word": show_word(rep.word),
        "decompositions": rep.total,
        "surviving": [d.to_dict() for d in rep.surviving[:20]],
        "witness": rep.witness,
        "killed_examples": [d.to_dict() for d in rep.killed_examples],
    }


def cmd_tree(args) -> int:
    try:
        p = parse_program(_read(args.program), args.max_trees)
    except SiplSyntaxError as e:
        if args.format == "json":
            print(json.dumps({"schema_version": 1, "command": "tree", "ok": False, "error": e.to_dict()},
                             ensure_ascii=False, indent=2))
        raise CliError(f"{args.program}:{e}", NOT_IN_LANGUAGE) from e
    t = p.trees[min(args.tree, len(p.trees)) - 1]
    r = p.renderer
    if args.format == "dot":
        _emit(args, r.dot(t), {})
    elif args.format == "svg":
        _emit(args, r.svg(t), {})
    elif args.format == "json":
        leaves, ok = p.leaf_check()
        args.json = True
        _emit(args, "", {"ok": True, "ambiguous": p.ambiguous, "leaf_yield": leaves, "leaf_yield_matches": ok,
                         "tree": r.to_dict(t)})
    else:
        leaves, ok = p.leaf_check()
        lines = [r.text(t), "", f"Обхід листків: {leaves}",
                 "Збігається з текстом програми ⇒ програма синтаксично правильна ✓" if ok else "НЕ збігається ✗"]
        if p.ambiguous:
            lines.append(f"Увага: БНФ SIPL неоднозначна - для цієї програми існує ≥ {len(p.trees)} дерев "
                         "(див. --tree 2). Показано дерево №" + str(args.tree))
        _emit(args, "\n".join(lines), {})
    return OK


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="formlang", description="Інструменти для КВ-граматик і мови SIPL")
    ap.add_argument("--version", action="version", version=f"formlang {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    def add(name: str, func, help_: str, json_flag: bool = True, output: bool = False):
        p = sub.add_parser(name, help=help_, description=help_)
        p.set_defaults(func=func)
        if json_flag:
            p.add_argument("--json", action="store_true", help="вивід у JSON")
        if output:
            p.add_argument("-o", "--output", help="записати результат у файл")
        return p

    p = add("analyze", cmd_analyze, "FORM-01: досяжні, продуктивні та ε-нетермінали")
    p.add_argument("grammar")
    for name, help_ in [("reduce", "FORM-01: видалити несуттєві символи"),
                        ("eps", "FORM-01: видалити ε-правила"),
                        ("unit", "FORM-01: видалити ланцюгові правила"),
                        ("cnf", "FORM-01: побудувати нормальну форму Хомського")]:
        p = add(name, cmd_transform, help_)
        p.add_argument("grammar")
        p.add_argument("--check", type=int, metavar="N", help="перевірити рівність мов на словах довжини ≤ N")

    p = add("derive", cmd_derive, "FORM-04: виведення та дерева виводу слова", output=True)
    p.add_argument("grammar")
    p.add_argument("word", help="слово; з пробілами - як послідовність токенів; ε - порожнє")
    p.add_argument("--max-trees", type=int, default=2, help="скільки дерев шукати (≥2 - перевірка неоднозначності)")
    p.add_argument("--format", choices=["text", "dot", "svg"], default="text")
    p.add_argument("--tree", type=int, default=1, help="номер дерева для dot/svg")

    p = add("words", cmd_words, "FORM-04: усі слова L(G) обмеженої довжини")
    p.add_argument("grammar")
    p.add_argument("--max-len", type=int, default=6)
    p.add_argument("--limit", type=int, default=60, help="скільки слів показувати")

    p = add("equations", cmd_equations, "FORM-02: система рівнянь для граматики")
    p.add_argument("file", help=".cfg (граматика) або .eq (система)")
    p = add("to-grammar", cmd_to_grammar, "FORM-02: граматика для системи рівнянь")
    p.add_argument("file")
    p = add("solve", cmd_solve, "FORM-02: наближення R(i) і порівняння з граматикою")
    p.add_argument("file")
    p.add_argument("--iterations", type=int, default=5)
    p.add_argument("--max-len", type=int, default=8)
    p.add_argument("--limit", type=int, default=12, help="скільки слів показувати в кожному наближенні")

    p = add("pump", cmd_pump, "FORM-03: дослідник леми про накачку")
    p.add_argument("pattern", nargs="?", help="шаблон мови, напр. 'a^n b^n c^n'")
    p.add_argument("--grammar", help="мова задана КВ-граматикою (потрібен --word)")
    p.add_argument("--min-n", type=int, default=0)
    p.add_argument("--k-max", type=int, default=6)
    p.add_argument("--max-i", type=int, default=3)
    p.add_argument("--word", help="дослідити конкретне слово")
    p.add_argument("--k", type=int, help="k для --word (за замовчуванням |word|)")
    p.add_argument("--decomp", help="дослідити розклад 'u,t1,x,t2,v'")
    p.add_argument("-v", "--verbose", action="store_true", help="показати приклади відкинутих розкладів")

    p = add("tree", cmd_tree, "VIS-01: дерево синтаксичного виводу SIPL-програми", json_flag=False, output=True)
    p.add_argument("program")
    p.add_argument("--format", choices=["text", "json", "dot", "svg"], default="text")
    p.add_argument("--max-trees", type=int, default=2)
    p.add_argument("--tree", type=int, default=1, help="номер дерева, якщо їх кілька")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except CliError as e:
        print(f"помилка: {e}", file=sys.stderr)
        return e.code
    except (GrammarError, RuntimeError) as e:
        print(f"помилка: {e}", file=sys.stderr)
        return BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
