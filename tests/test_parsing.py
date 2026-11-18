from formlang.grammar import parse_grammar
from formlang.parsing import Earley, accepts, derivation
from formlang.words import generate_words


def test_membership_with_epsilon_and_left_recursion():
    g = parse_grammar("S -> aSb | ε")
    assert accepts(g, ())
    assert accepts(g, tuple("aaabbb"))
    assert not accepts(g, tuple("aab"))
    left = parse_grammar("E -> E+a | a")
    assert accepts(left, tuple("a+a+a"))


def test_ambiguity_detected():
    g = parse_grammar("E -> E+E | E*E | a")
    assert len(Earley(g, tuple("a+a*a")).trees(5)) == 2
    assert len(Earley(g, tuple("a+a+a+a")).trees(10)) == 5


def test_unambiguous_grammar_has_single_tree():
    g = parse_grammar("E -> E+T | T\nT -> T*F | F\nF -> (E) | a")
    assert len(Earley(g, tuple("a+a*(a+a)")).trees(5)) == 1


def test_cyclic_grammar_terminates():
    g = parse_grammar("S -> SS | (S) | ε\nA -> A | a")
    trees = Earley(g, tuple("()()")).trees(3)
    assert trees and all(t.symbol == "S" for t in trees)


def test_leftmost_and_rightmost_derivations():
    g = parse_grammar("S -> AB\nA -> a\nB -> b")
    t = Earley(g, ("a", "b")).trees()[0]
    left = [f for f, _ in derivation(t, True)]
    right = [f for f, _ in derivation(t, False)]
    assert left == [("S",), ("A", "B"), ("a", "B"), ("a", "b")]
    assert right == [("S",), ("A", "B"), ("A", "b"), ("a", "b")]


def test_tree_leaves_give_word():
    g = parse_grammar("S -> aSb | ε")
    t = Earley(g, tuple("aabb")).trees()[0]
    assert [x.symbol for x in t.leaves() if not x.is_epsilon] == list("aabb")


def test_error_position_and_expected():
    g = parse_grammar("S -> aSb | ε")
    err = Earley(g, tuple("abb")).error()
    assert err.position == 2 and err.found == "b" and err.expected == []
    err = Earley(g, tuple("aa")).error()
    assert err.found is None and set(err.expected) == {"a", "b"}


def test_generate_words():
    g = parse_grammar("S -> aSb | ε")
    assert generate_words(g, 6) == {(), tuple("ab"), tuple("aabb"), tuple("aaabbb")}
    pal = parse_grammar("P -> aPa | bPb | a | b | ε")
    words = generate_words(pal, 4)
    assert len(words) == 1 + 2 + 2 + 4 + 4
    assert all(w == w[::-1] for w in words)
