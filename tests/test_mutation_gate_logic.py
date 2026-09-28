"""Regression tests for tools/mutation_gate.py's verdict logic.

Skipped where tools/ is not present (e.g. an unpacked sdist): the gate is a
repository tool, not part of the installed package.
"""
import importlib.util
import json
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parent.parent / "tools" / "mutation_gate.py"
if not GATE.exists():
    pytest.skip("tools/mutation_gate.py not present (not a repository checkout)",
                allow_module_level=True)

spec = importlib.util.spec_from_file_location("mutation_gate", GATE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def _base(statuses, reasons=None):
    return {"mutants": {k: {"status": v} for k, v in statuses.items()},
            "survivor_reasons": reasons or {}}


LOC = {"b": ("tools/mutation_gate.py", 1)}


def test_pass_when_identical_and_survivors_explained():
    base = _base({"a": "killed", "b": "survived"}, {"b": "equivalent"})
    base["survivor_anchors"] = {"b": g.source_line(*LOC["b"])}
    assert g.verdict({"a": "killed", "b": "survived"}, base, LOC) == []


def test_fail_when_reason_anchored_to_another_line():
    # The ordinal-shift defect: the reason was written for line 2, the mutant now sits on line 1.
    base = _base({"a": "killed", "b": "survived"}, {"b": "equivalent"})
    base["survivor_anchors"] = {"b": g.source_line("tools/mutation_gate.py", 2)}
    f = g.verdict({"a": "killed", "b": "survived"}, base, LOC)
    assert any("written against a different source line" in x for x in f)


def test_rebaseline_drops_reason_whose_anchor_moved(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "BASELINE", tmp_path / "b.json")
    mutants = [{"id": "b", "file": "tools/mutation_gate.py", "line": 1, "operator": "x", "detail": "y"}]
    old = {"survivor_reasons": {"b": "r"}, "survivor_anchors": {"b": "something else"}}
    data = g.write_baseline(mutants, {"b": "survived"}, old, 1)
    assert data["survivor_reasons"] == {}
    old["survivor_anchors"] = {"b": g.source_line("tools/mutation_gate.py", 1)}
    data = g.write_baseline(mutants, {"b": "survived"}, old, 1)
    assert data["survivor_reasons"] == {"b": "r"}


def test_fail_below_floor():
    base = _base({"a": "killed", "b": "killed", "c": "survived"}, {"c": "x"})
    f = g.verdict({"a": "killed", "b": "survived", "c": "survived"}, base)
    assert any("below the derived floor" in x for x in f)


def test_fail_when_baseline_killed_now_survives_even_if_score_holds():
    # score holds (1 killed of 2 both times) but the identity of the survivor changed
    base = _base({"a": "killed", "b": "survived"}, {"a": "r", "b": "r"})
    f = g.verdict({"a": "survived", "b": "killed"}, base)
    assert any("baseline killed now survive" in x and "a" in x for x in f)
    assert not any("below the derived floor" in x for x in f)


def test_fail_when_baseline_killed_vanished_even_if_score_rises():
    base = _base({"a": "killed", "b": "survived"}, {"b": "r"})
    f = g.verdict({"a2": "killed", "b": "killed"}, base)
    assert any("no longer exist" in x for x in f)


def test_fail_on_survivor_without_reason():
    base = _base({"a": "killed", "b": "survived"}, {"b": "   "})
    f = g.verdict({"a": "killed", "b": "survived"}, base)
    assert any("no written reason" in x for x in f)


def test_timeout_counts_as_killed():
    assert g._score({"a": {"status": "timeout"}, "b": {"status": "survived"}}) == (1, 2, 0.5)


def test_hand_edited_baseline_refused(tmp_path, monkeypatch):
    data = {"summary": {"killed": 2, "total": 2}, "mutants": {"a": {"status": "killed"},
                                                              "b": {"status": "survived"}}}
    p = tmp_path / "b.json"
    p.write_text(json.dumps(data))
    monkeypatch.setattr(g, "BASELINE", p)
    with pytest.raises(SystemExit, match="disagrees with its own records"):
        g.load_baseline()


def test_missing_baseline_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "BASELINE", tmp_path / "absent.json")
    with pytest.raises(SystemExit, match="no baseline"):
        g.load_baseline()


SRC = '''
def f(x):
    if x > 0:
        raise ValueError("neg")
    return x * 2 + 1
'''


def test_ids_are_stable_under_line_shifts():
    a = {m["id"] for m in g.mutants_for_source("m.py", SRC)}
    b = {m["id"] for m in g.mutants_for_source("m.py", "# comment\n\n\n" + SRC)}
    assert a == b and len(a) > 0


def test_ids_change_when_function_renamed():
    a = {m["id"] for m in g.mutants_for_source("m.py", SRC)}
    b = {m["id"] for m in g.mutants_for_source("m.py", SRC.replace("def f", "def h"))}
    assert a.isdisjoint(b)


def test_operators_cover_the_audit_classes():
    ops = {m["operator"] for m in g.mutants_for_source("m.py", SRC)}
    assert {"binop", "compare", "const", "raise", "if"} <= ops
    src = "def _h():\n    return 1\n\ndef k():\n    r = _h()\n    return r\n"
    subs = [m for m in g.mutants_for_source("m.py", src) if m["operator"] == "callsub"]
    assert subs and "0.0499" in subs[0]["source"]


def test_raise_mutant_deletes_the_raise():
    m = [m for m in g.mutants_for_source("m.py", SRC) if m["operator"] == "raise"][0]
    assert "raise" not in m["source"] and "pass" in m["source"]


def test_string_separators_not_mutated():
    ms = g.mutants_for_source("m.py", 'def s():\n    return "=" * 80\n')
    assert ms == []


def test_real_module_generates_mutants_with_unique_ids():
    # One module only: generating all mutants here would run once per mutant in the campaign.
    path = GATE.parent.parent / "nmtccalc" / "statute.py"
    ms = g.mutants_for_source("nmtccalc/statute.py", path.read_text())
    assert len(ms) > 5
    assert len({m["id"] for m in ms}) == len(ms)


def test_string_operators_drop_not_and_last_sentence():
    src = 'NOTE = ("This figure is not a return. It depends on the price. Read it so.")\n'
    ms = {m["operator"]: m for m in g.mutants_for_source("m.py", src)}
    assert "It is" not in ms["strnot"]["source"]
    assert "This figure is a return." in ms["strnot"]["source"]
    drops = [m["source"] for m in g.mutants_for_source("m.py", src) if m["operator"] == "strsentence"]
    assert len(drops) == 3
    assert "This figure is not a return." not in drops[0] and "Read it so" in drops[0]
    assert "It depends on the price." not in drops[1]
    assert "Read it so" not in drops[2] and "It depends on the price." in drops[2]


def test_docstrings_and_short_strings_and_fstrings_not_text_mutated():
    src = ('def f(x):\n    """This docstring is not code. It has sentences."""\n'
           '    y = "short not"\n    return f"value {x} is not checked. Ever. Again."\n')
    assert [m for m in g.mutants_for_source("m.py", src) if m["operator"].startswith("str")] == []


def _bl(statuses):
    return {"mutants": {k: {"status": v} for k, v in statuses.items()}}


def test_ratchet_skips_explicitly_without_reference(capsys):
    assert g.ratchet(_bl({"a": "killed"}), None, {}, "main") == []
    assert "SKIPPED, explicitly" in capsys.readouterr().out


def test_ratchet_fails_on_consistent_flip_and_floor_drop():
    ref = _bl({"a": "killed", "b": "killed", "c": "survived"})
    cur = _bl({"a": "survived", "b": "killed", "c": "survived"})
    f = g.ratchet(cur, ref, {}, "main")
    assert any("below the reference floor" in x for x in f)
    assert any("killed in the reference baseline survive" in x and "a" in x for x in f)


def test_ratchet_overrides_need_each_id_and_floor_drop():
    ref = _bl({"a": "killed", "b": "killed"})
    cur = _bl({"a": "survived", "b": "killed"})
    assert len(g.ratchet(cur, ref, {"a": "reviewed"}, "main")) == 1          # floor drop still fails
    assert g.ratchet(cur, ref, {"a": "reviewed", "floor_drop": "accepted"}, "main") == []


def test_ratchet_passes_when_floor_rises_and_ids_change(capsys):
    ref = _bl({"a": "killed", "b": "survived"})
    cur = _bl({"a": "killed", "c": "killed"})
    assert g.ratchet(cur, ref, {}, "main") == []
    assert "1 mutant(s) only in the reference, 1 only in the committed" in capsys.readouterr().out


def test_ratchet_catches_rename_dodge():
    # R1-2: rename a function (new IDs), mark its mutant survived, pad with 30 killed mutants
    # so the floor rises. Before this rule ratchet() returned [].
    ref = _bl({"m.py::_compute_irr::const::x#0": "killed", "m.py::f::c#0": "killed",
               "m.py::f::c#1": "survived"})
    cur = {"m.py::_solve_irr::const::x#0": "survived", "m.py::f::c#0": "killed",
           "m.py::f::c#1": "survived"}
    cur.update({f"m.py::pad::c#{i}": "killed" for i in range(30)})
    cur = _bl(cur)
    f = g.ratchet(cur, ref, {}, "main")
    assert len(f) == 1 and "IDs the reference baseline does not have" in f[0]
    assert "m.py::_solve_irr::const::x#0" in f[0]
    assert g.ratchet(cur, ref, {"m.py::_solve_irr::const::x#0": "renamed; reviewed"}, "main") == []


def test_overrides_without_reason_refused(tmp_path, monkeypatch):
    p = tmp_path / "o.json"
    p.write_text('{"x": "  "}')
    monkeypatch.setattr(g, "OVERRIDES", p)
    with pytest.raises(SystemExit, match="without a written reason"):
        g.load_overrides()
