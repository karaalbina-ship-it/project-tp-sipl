from formlang.grammar import parse_grammar
from formlang.parsing import nullable_set
from formlang.transform import (
    is_cnf,
    productive,
    reachable,
    remove_epsilon,
    remove_unit,
    remove_useless,
    to_cnf,
)
from formlang.words import generate_words

PR4 = """
S -> AbCa | ABB | BScB | aSB
A -> Aa | ε
B -> bB | ε
C -> Dc | Cc | c
D -> Dd
"""


def rules(g, lhs):
    return {g.show_rhs(r) for r in g.rules_for(lhs)}


def test_reachable_chain_matches_practicum():
    g = parse_grammar(PR4)
    reach, chain = reachable(g)
    assert chain == [{"S"}, {"S", "A", "B", "C"}, {"S", "A", "B", "C", "D"}]
    assert reach == g.nonterminals


def test_productive_chain_matches_practicum():
    _, chain = productive(parse_grammar(PR4))
    assert chain == [{"A", "B", "C"}, {"A", "B", "C", "S"}]


def test_remove_useless_drops_d():
    g = remove_useless(parse_grammar(PR4)).grammar
    assert "D" not in g.nonterminals
    assert rules(g, "C") == {"Cc", "c"}


def test_unreachable_after_unproductive():
    g = remove_useless(parse_grammar("S -> a | CB\nC -> C\nB -> b")).grammar
    assert g.nonterminals == {"S"}


def test_empty_language():
    res = remove_useless(parse_grammar("S -> aS"))
    assert res.grammar.rules == []
    assert any("L(G) = ∅" in s for s in res.steps)


def test_epsilon_free_form_matches_practicum():
    g = remove_epsilon(remove_useless(parse_grammar(PR4)).grammar).grammar
    expected_s = {
        "AbCa", "ABB", "BScB", "aSB", "bCa", "BB", "AB", "A", "BSc", "ScB", "Sc",
        "aS", "B", "BcB", "aB", "Bc", "cB", "c", "a",
    }
    assert rules(g, "S") == expected_s
    assert rules(g, "A") == {"Aa", "a"}
    assert rules(g, "B") == {"bB", "b"}
    assert not any(not r for _, r in g.rules)


def test_nullable():
    assert nullable_set(parse_grammar(PR4)) == {"S", "A", "B"}


def test_remove_unit_cycle():
    g = remove_unit(parse_grammar("S -> A | a\nA -> S | b")).grammar
    assert rules(g, "S") == {"a", "b"}
    assert rules(g, "A") == {"a", "b"}


def same_language(g1, g2, n):
    return generate_words(g1, n) == generate_words(g2, n)


def test_cnf_practicum_example_is_cnf_and_equivalent():
    g = parse_grammar(PR4)
    cnf = to_cnf(g).grammar
    assert is_cnf(cnf)
    assert same_language(g, cnf, 6)
    assert cnf.rules_for(cnf.start).count(()) == 1


def test_cnf_practicum_task_grammar():
    g = parse_grammar("""
S -> AbBE | ADcBE | AEcC
E -> ε | bEc
A -> ε | aA
B -> ε | bB
C -> ε | cC
D -> d | dD
""")
    cnf = to_cnf(g).grammar
    assert is_cnf(cnf)
    assert same_language(g, cnf, 6)


def test_cnf_without_epsilon_keeps_start():
    g = parse_grammar("E -> E+T | T\nT -> T*F | F\nF -> (E) | a")
    cnf = to_cnf(g).grammar
    assert is_cnf(cnf)
    assert cnf.start == "E"
    assert same_language(g, cnf, 7)


def test_is_cnf_rejects_bad_forms():
    assert not is_cnf(parse_grammar("S -> aB\nB -> b"))
    assert not is_cnf(parse_grammar("S -> ABC\nA -> a\nB -> b\nC -> c"))
    assert not is_cnf(parse_grammar("S -> AS | ε\nA -> a"))
