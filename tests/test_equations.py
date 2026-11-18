import pytest

from formlang.equations import (
    approximations,
    compare,
    evaluate,
    from_grammar,
    parse_system,
    show_expr,
    to_grammar,
)
from formlang.grammar import GrammarError, parse_grammar


def lang(*ws):
    return frozenset(tuple(w) for w in ws)


def test_practicum_anbn_approximations():
    sys_ = parse_system("S = {ε} ∪ {a}S{b}")
    chain = approximations(sys_, 3, 10)
    assert [nu["S"] for nu in chain] == [lang(), lang(""), lang("", "ab"), lang("", "ab", "aabb")]


def test_practicum_pr5_approximations():
    sys_ = parse_system("S = {c}A\nA = {a}A{bbb} ∪ {ε}")
    chain = approximations(sys_, 3, 20)
    assert chain[1] == {"S": lang(), "A": lang("")}
    assert chain[2] == {"S": lang("c"), "A": lang("", "abbb")}
    assert chain[3]["S"] == lang("c", "cabbb")


def test_interpretation_of_expression():
    sys_ = parse_system("X = {a, ab}{c}Y\nY = {ε, b}")
    nu = {"X": frozenset(), "Y": lang("", "b")}
    assert evaluate(sys_.equations["X"], nu, 10) == lang("ac", "acb", "abc", "abcb")


def test_truncation_is_exact():
    sys_ = parse_system("S = {ε} ∪ {a}S{b}")
    assert compare(sys_, 6).from_equations == lang("", "ab", "aabb", "aaabbb")


def test_grammar_to_system_merges_terminals():
    sys_ = from_grammar(parse_grammar("S -> cA\nA -> aAbbb | ε"))
    assert sys_.to_text() == "S = {c}A\nA = {a}A{bbb} ∪ {ε}"


def test_system_to_grammar_and_back():
    sys_ = parse_system("P = {ε, a, b} ∪ {a}P{a} ∪ {b}P{b}")
    g = to_grammar(sys_)
    assert {g.show_rhs(r) for r in g.rules_for("P")} == {"ε", "a", "b", "aPa", "bPb"}


@pytest.mark.parametrize("path", ["equations/pr5_example.eq", "equations/anbn.eq", "equations/palindromes.eq",
                                  "grammars/pr4_task.cfg", "grammars/pr5_example.cfg"])
def test_equations_agree_with_grammar(example, path):
    from formlang.cli import _system_or_grammar

    sys_, g = _system_or_grammar(str(example(path)))
    assert compare(sys_, 6, g).equal


def test_bare_terminals_and_grouping():
    sys_ = parse_system("S = ε | a(S)b")
    assert show_expr(sys_.equations["S"]) == "{ε} ∪ {a}S{b}"


@pytest.mark.parametrize("text", ["S {a}", "s = {a}", "S = {a", "S = A", "S = (a", "S = a)"])
def test_bad_systems(text):
    with pytest.raises(GrammarError):
        parse_system(text)
