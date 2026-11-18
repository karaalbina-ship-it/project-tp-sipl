import pytest

from formlang.grammar import GrammarError, parse_grammar
from formlang.pumping import (
    Decomposition,
    decompositions,
    explore,
    explore_word,
    make_member,
    parse_pattern,
    pump,
)


def w(s):
    return tuple(s)


def test_pattern_membership():
    p = parse_pattern("d b^n a^{3n} e c^{3n} b")
    assert p.contains(w("deb"))
    assert p.contains(w("dbaaaecccb"))
    assert not p.contains(w("dbaaecccb"))
    q = parse_pattern("(ab)^{n+1} c", min_n=1)
    assert q.contains(w("ababc")) and not q.contains(w("abc"))


@pytest.mark.parametrize("bad", ["a^{2m}", "", "a^{n-3}"])
def test_bad_patterns(bad):
    with pytest.raises(GrammarError):
        parse_pattern(bad)


def test_decomposition_constraints():
    ds = list(decompositions(w("abcd"), 2))
    assert ds
    for d in ds:
        assert d.u + d.t1 + d.x + d.t2 + d.v == w("abcd")
        assert len(d.t1 + d.t2) >= 1
        assert len(d.t1 + d.x + d.t2) <= 2


def test_non_context_free_language_gives_witnesses():
    reps = explore(parse_pattern("a^n b^n c^n"), 6)
    assert all(r.witness for r in reps)


def test_practicum_language_gives_witnesses():
    reps = explore(parse_pattern("d b^n a^{3n} e c^{3n} b"), 8)
    assert all(r.witness for r in reps)


def test_context_free_language_survives():
    reps = explore(parse_pattern("a^n b^n"), 5)
    assert not reps[-1].witness
    d = reps[-1].surviving[0]
    assert len(d.t1) == len(d.t2)


def test_grammar_language():
    member = make_member(parse_grammar("S -> aSb | ε"))
    rep = explore_word(member, w("aaabbb"), 4)
    assert not rep.witness


def test_pump_specific_decomposition():
    member = make_member(parse_pattern("a^n b^n c^n"))
    d = pump(Decomposition(w("a"), w("a"), w("b"), w("b"), w("cc")), member, 3)
    assert not d.survives
    assert d.pumped[-1][0] == 0
