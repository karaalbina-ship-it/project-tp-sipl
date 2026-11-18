import pytest

from formlang.grammar import GrammarError, parse_grammar, split_word


def test_compact_and_spaced_forms_are_equal():
    a = parse_grammar("S -> AbCa | ε\nA -> a")
    b = parse_grammar("S → A b C a | ε\nA → a")
    assert a.rules == b.rules
    assert a.start == "S"
    assert a.nonterminals == {"S", "A", "C"}
    assert a.terminals == {"a", "b"}


def test_long_names_quoted_terminals_and_classes():
    g = parse_grammar('<prog> ::= "begin" <stm> "end"\n<stm> ::= %ident ":=" %number')
    assert g.rules[0] == ("prog", ("begin", "stm", "end"))
    assert g.rules[1] == ("stm", ("%ident", ":=", "%number"))
    assert not g.compact()


def test_primes_and_digits_in_nonterminals():
    g = parse_grammar("S0 -> A′B' | ε\nA′ -> a\nB' -> b")
    assert g.rules[0] == ("S0", ("A′", "B'"))


def test_round_trip_through_text():
    g = parse_grammar("S -> aSb | ε | A\nA -> A a | a")
    assert parse_grammar(g.to_text()).rules == g.rules


def test_comments_and_blank_lines_are_ignored():
    g = parse_grammar("# коментар\n\nS -> a\n")
    assert g.rules == [("S", ("a",))]


@pytest.mark.parametrize(
    "text",
    ["", "S a b", "a -> b", "S -> <A", 'S -> "abc', 'S -> "S"\nS -> a'],
)
def test_bad_grammars(text):
    with pytest.raises(GrammarError):
        parse_grammar(text)


def test_error_has_line_number():
    with pytest.raises(GrammarError, match="рядок 2"):
        parse_grammar("S -> a\nбез стрілки")


def test_split_word():
    assert split_word("aab") == ("a", "a", "b")
    assert split_word("begin x end") == ("begin", "x", "end")
    assert split_word("ε") == ()
