import json

import pytest

from formlang.cli import main


def run(capsys, *args):
    code = main([str(a) for a in args])
    out, err = capsys.readouterr()
    return code, out, err


def test_analyze_json(capsys, example):
    code, out, _ = run(capsys, "analyze", example("grammars/pr4_example.cfg"), "--json")
    data = json.loads(out)
    assert code == 0 and data["schema_version"] == 1
    assert data["unproductive"] == ["D"]


@pytest.mark.parametrize("cmd", ["reduce", "eps", "unit", "cnf"])
def test_transform_commands_with_check(capsys, example, cmd):
    code, out, _ = run(capsys, cmd, example("grammars/pr4_task.cfg"), "--check", 5)
    assert code == 0 and "збігаються" in out


def test_derive_ambiguous(capsys, example):
    code, out, _ = run(capsys, "derive", example("grammars/expr_ambiguous.cfg"), "a+a*a", "--json")
    data = json.loads(out)
    assert code == 0 and data["ambiguous"] and len(data["trees"]) == 2


def test_derive_not_in_language(capsys, example):
    code, _, err = run(capsys, "derive", example("grammars/anbn.cfg"), "aab")
    assert code == 1 and "∉ L(G)" in err


def test_derive_svg_to_file(capsys, example, tmp_path):
    out = tmp_path / "t.svg"
    code, _, _ = run(capsys, "derive", example("grammars/anbn.cfg"), "aabb", "--format", "svg", "-o", out)
    assert code == 0 and out.read_text(encoding="utf-8").startswith("<svg")


def test_words(capsys, example):
    code, out, _ = run(capsys, "words", example("grammars/balanced.cfg"), "--max-len", 4, "--json")
    assert json.loads(out)["words"] == ["ε", "()", "(())", "()()"]


def test_solve_and_equations(capsys, example):
    code, out, _ = run(capsys, "solve", example("equations/pr5_example.eq"), "--iterations", 3)
    assert code == 0 and "Збігаються" in out
    code, out, _ = run(capsys, "equations", example("grammars/pr5_example.cfg"))
    assert out.strip() == "S = {c}A\nA = {a}A{bbb} ∪ {ε}"
    code, out, _ = run(capsys, "to-grammar", example("equations/anbn.eq"))
    assert out.strip() == "S → ε | aSb"


def test_pump_modes(capsys, example):
    code, out, _ = run(capsys, "pump", "a^n b^n c^n", "--k-max", 4, "--json")
    assert code == 0 and json.loads(out)["all_witnesses"]
    code, out, _ = run(capsys, "pump", "a^n b^n c^n", "--decomp", "a,a,b,b,cc")
    assert "Не витримує" in out
    code, out, _ = run(capsys, "pump", "--grammar", example("grammars/anbn.cfg"), "--word", "aabb")
    assert code == 0 and "✓" in out
    code, _, err = run(capsys, "pump", "a^n b^n", "--word", "aab")
    assert code == 1


def test_tree_formats(capsys, example):
    code, out, _ = run(capsys, "tree", example("sipl/power.sipl"))
    assert code == 0 and "синтаксично правильна" in out
    code, out, _ = run(capsys, "tree", example("sipl/max.sipl"), "--format", "json")
    assert json.loads(out)["leaf_yield_matches"]
    code, out, _ = run(capsys, "tree", example("sipl/division.sipl"), "--format", "dot")
    assert out.startswith("digraph")


def test_tree_syntax_error(capsys, example):
    code, _, err = run(capsys, "tree", example("sipl/bad_ge.sipl"))
    assert code == 1 and "3:12" in err


def test_bad_input_and_io_errors(capsys, tmp_path):
    bad = tmp_path / "bad.cfg"
    bad.write_text("без стрілки", encoding="utf-8")
    assert run(capsys, "analyze", bad)[0] == 2
    assert run(capsys, "analyze", tmp_path / "missing.cfg")[0] == 5
