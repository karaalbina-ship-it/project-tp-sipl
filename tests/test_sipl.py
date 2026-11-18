import xml.etree.ElementTree as ET

import pytest

from formlang.sipl import SiplSyntaxError, lex, parse_program

POWER = """begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end"""


def test_lexer_positions_and_kinds():
    toks = lex("begin\n  X := 10\nend")
    assert [t.symbol for t in toks] == ["begin", "%ident", ":=", "%number", "end"]
    assert (toks[1].line, toks[1].col) == (2, 3)
    assert lex("not X or Y")[0].symbol == "¬"


def test_lexer_error():
    with pytest.raises(SiplSyntaxError) as e:
        lex("begin\n  X := 1 ? 2\nend")
    assert (e.value.line, e.value.col) == (2, 10)


def test_power_program_tree_and_leaf_check():
    p = parse_program(POWER)
    leaves, ok = p.leaf_check()
    assert ok
    assert leaves.startswith("begin R := 1 ; while")
    assert not p.ambiguous
    assert p.tree.symbol == "програма"


def test_spans_link_to_source():
    p = parse_program(POWER)
    d = p.renderer.to_dict(p.tree)
    assert d["source"]["text"] == POWER
    stm = d["children"][1]
    assert stm["source"]["start"] == {"offset": 8, "line": 2, "col": 3}


def test_sequence_is_ambiguous_in_course_bnf():
    p = parse_program("begin X := 1; Y := 2; Z := 3 end", max_trees=3)
    assert p.ambiguous


def test_parenthesised_condition_and_expression():
    parse_program("begin if (X + 1) > 2 ∨ ¬(X = 1) then skip else skip end")


@pytest.mark.parametrize(
    "src, line, col",
    [
        ("begin\n  while X >= Y do skip\nend", 2, 12),
        ("begin X := 1", 1, 13),
        ("begin X := 1; end", 1, 15),
        ("X := 1", 1, 1),
    ],
)
def test_syntax_errors(src, line, col):
    with pytest.raises(SiplSyntaxError) as e:
        parse_program(src)
    assert (e.value.line, e.value.col) == (line, col)


def test_exports():
    p = parse_program(POWER)
    svg = p.renderer.svg(p.tree)
    ET.fromstring(svg)
    assert "<title>" in svg
    dot = p.renderer.dot(p.tree)
    assert dot.startswith("digraph") and "->" in dot
    assert "└── end" in p.renderer.text(p.tree)
