#!/usr/bin/env python3
"""Mutation-testing gate for nmtc-calc.

Generates mutants of every module under ``nmtccalc/`` by AST transformation
(arithmetic, comparison, numeric-constant, raise, boolean, `not`, `if`,
call-result and call-statement operators, plus two TEXT operators on string
constants of 40+ characters outside f-strings and docstrings: drop the first
" not ", and drop the last sentence),
runs the test suite against each one in an isolated copy of the tree, and
compares the result with the committed baseline ``tools/mutation_baseline.json``.

A mutant is KILLED when the suite fails (or times out) with it applied, and
SURVIVES when the suite stays green.

THE GATE FAILS WHEN ANY OF THESE HOLDS
  1. the mutation score is below the floor;
  2. a mutant the baseline killed now survives;
  3. a mutant the baseline killed no longer exists (the code it mutated
     changed) — re-baseline deliberately after review;
  4. a surviving mutant has no written reason in the baseline.

THE FLOOR IS DERIVED, NOT TYPED. It is recomputed on every run from the
baseline's per-mutant records (killed / total). No score is typed anywhere in
this file or in the baseline. The baseline's stored summary is cross-checked
against its own records, which catches an edit that changes one without the
other -- and ONLY that: a CONSISTENT hand edit (a status flipped to survived,
the summary adjusted to match, a reason added) passes that check, and
--rebaseline can legitimately lower the floor. What stops both is the RATCHET:

THE RATCHET compares the committed baseline with a REFERENCE baseline -- the
one at the merge-base with origin/main (falling back to main), or --reference
REF. It fails when
  5. the floor is lower than the reference floor, or
  6. a mutant killed in the reference survives in the committed baseline,
unless tools/mutation_ratchet_overrides.json lists that mutant ID (or
"floor_drop") with a written reason. Mutants that exist in only one of the two
baselines are reported, not failed: code changes add and remove mutants, and
rules 2-4 above govern the current run. When the reference has NO baseline
(the release that introduces the gate), the ratchet says so loudly and skips;
pass --require-reference to make that a failure instead.

Mutant IDs are content-based, not line-based:
    <file>::<enclosing function>::<operator>::<detail>#<n>
so an edit elsewhere in a file does not reshuffle IDs. Renaming a function or
changing a mutated expression does change them, which rule 3 catches.

Usage
    python tools/mutation_gate.py                  # run the gate
    python tools/mutation_gate.py --rebaseline     # write a new baseline (keeps
                                                   # reasons for survivors that persist)
    python tools/mutation_gate.py --list           # list mutants without running
    python tools/mutation_gate.py --workers 4
    python tools/mutation_gate.py --ratchet-only [--reference origin/main]
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = "nmtccalc"
BASELINE = REPO / "tools" / "mutation_baseline.json"
OVERRIDES = REPO / "tools" / "mutation_ratchet_overrides.json"
BASELINE_GIT_PATH = "tools/mutation_baseline.json"
PYTEST_ARGS = ["-x", "-q", "-p", "no:cacheprovider", "--no-header"]
LITERAL = 0.0499  # the audit's "IRR engine replaced by a literal" value
STRING_MIN_LEN = 40  # string constants at least this long get clause/negation mutants

# ── mutant generation ───────────────────────────────────────────────────────

_BINOP_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div,
               ast.Div: ast.Mult, ast.Pow: ast.Mult, ast.FloorDiv: ast.Div,
               ast.Mod: ast.Mult}
_CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot,
             ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}


def _is_str_const(node) -> bool:
    return isinstance(node, (ast.Constant,)) and isinstance(node.value, str) \
        or isinstance(node, ast.JoinedStr)


def _qualname_map(tree: ast.AST) -> dict:
    """node id -> dotted name of the innermost enclosing def/class."""
    out = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}.{child.name}" if prefix else child.name
                out[id(child)] = name
                visit(child, name)
            else:
                out[id(child)] = prefix or "<module>"
                visit(child, prefix)
    visit(tree, "")
    return out


def _docstring_nodes(tree: ast.AST) -> set:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0]))
                ids.add(id(body[0].value))  # the string Constant itself, not only its Expr
    return ids


def _local_functions(tree: ast.Module) -> set:
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _perturb(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return 1.0 if value == 0 else value * 1.1
    return None


def _sites(tree: ast.Module):
    """Yield (walk_index, operator, detail) for every mutable site."""
    local_fns = _local_functions(tree)
    parents = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p):
            parents[id(c)] = p
    for idx, node in enumerate(ast.walk(tree)):
        parent = parents.get(id(node))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOP_SWAP:
            if _is_str_const(node.left) or _is_str_const(node.right):
                continue  # "=" * 80 separators and string formatting
            yield idx, "binop", f"{type(node.op).__name__}->{_BINOP_SWAP[type(node.op)].__name__}"
        elif isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in _CMP_SWAP:
                    yield idx, "compare", f"{i}:{type(op).__name__}->{_CMP_SWAP[type(op)].__name__}"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and len(node.value) >= STRING_MIN_LEN and not isinstance(parent, ast.JoinedStr):
            # Disclosure and refusal text: a clause or a negation can be lost
            # without any number moving. f-string parts are not mutated.
            if " not " in node.value:
                yield idx, "strnot", "drop-first-not"
            if ". " in node.value.rstrip(". "):
                yield idx, "strclause", "drop-last-sentence"
        elif isinstance(node, ast.Constant) and not isinstance(node.value, (str, bytes)) \
                and node.value is not None and _perturb(node.value) is not None:
            if isinstance(parent, ast.BinOp) and (_is_str_const(parent.left) or _is_str_const(parent.right)):
                continue
            if isinstance(parent, ast.FormattedValue):
                continue
            yield idx, "const", f"{node.value!r}->{_perturb(node.value)!r}"
        elif isinstance(node, ast.Raise):
            yield idx, "raise", "raise->pass"
        elif isinstance(node, ast.BoolOp):
            new = "Or" if isinstance(node.op, ast.And) else "And"
            yield idx, "boolop", f"{type(node.op).__name__}->{new}"
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            yield idx, "not", "not->identity"
        elif isinstance(node, ast.If):
            yield idx, "if", "negate"
        elif isinstance(node, (ast.Assign, ast.Return)) and isinstance(node.value, ast.Call) \
                and isinstance(node.value.func, ast.Name) and node.value.func.id in local_fns:
            yield idx, "callsub", f"{node.value.func.id}()->{LITERAL}"
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            f = node.value.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if name != "print":
                yield idx, "stmtdel", f"{name}()->pass"


def _apply(tree: ast.Module, idx: int, op: str, detail: str) -> ast.Module:
    new = copy.deepcopy(tree)
    node = list(ast.walk(new))[idx]
    parents = {}
    for p in ast.walk(new):
        for c in ast.iter_child_nodes(p):
            parents[id(c)] = p

    def replace_stmt(target, replacement):
        parent = parents[id(target)]
        for field, value in ast.iter_fields(parent):
            if isinstance(value, list) and target in value:
                value[value.index(target)] = replacement
                return
        raise RuntimeError("statement not found in parent")

    if op == "binop":
        node.op = _BINOP_SWAP[type(node.op)]()
    elif op == "compare":
        i = int(detail.split(":")[0])
        node.ops[i] = _CMP_SWAP[type(node.ops[i])]()
    elif op == "const":
        node.value = _perturb(node.value)
    elif op == "raise":
        replace_stmt(node, ast.Pass())
    elif op == "boolop":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif op == "not":
        parent = parents[id(node)]
        for field, value in ast.iter_fields(parent):
            if value is node:
                setattr(parent, field, node.operand)
                break
            if isinstance(value, list) and node in value:
                value[value.index(node)] = node.operand
                break
    elif op == "if":
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    elif op == "strnot":
        node.value = node.value.replace(" not ", " ", 1)
    elif op == "strclause":
        body = node.value.rstrip()
        cut = body.rstrip(". ").rindex(". ")
        node.value = body[:cut + 1]
    elif op == "callsub":
        node.value = ast.Constant(value=LITERAL)
    elif op == "stmtdel":
        replace_stmt(node, ast.Pass())
    else:
        raise ValueError(op)
    return ast.fix_missing_locations(new)


def mutants_for_source(rel: str, src: str) -> list:
    """Mutants of one module's source; ``rel`` is its repo-relative path."""
    tree = ast.parse(src)
    qn = _qualname_map(tree)
    docstrings = _docstring_nodes(tree)
    nodes = list(ast.walk(tree))
    seen = {}
    out = []
    for idx, op, detail in _sites(tree):
        node = nodes[idx]
        if id(node) in docstrings:
            continue
        owner = qn.get(id(node), "<module>")
        key = f"{rel}::{owner}::{op}::{detail}"
        n = seen.get(key, 0)
        seen[key] = n + 1
        out.append({
            "id": f"{key}#{n}",
            "file": rel,
            "line": getattr(node, "lineno", 0),
            "operator": op,
            "detail": detail,
            "source": ast.unparse(_apply(tree, idx, op, detail)),
        })
    return out


def generate_mutants():
    """Return a list of dicts: id, file, line, operator, detail, source."""
    mutants = []
    for path in sorted((REPO / PACKAGE).rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        mutants.extend(mutants_for_source(rel, path.read_text()))
    ids = [m["id"] for m in mutants]
    if len(ids) != len(set(ids)):
        raise SystemExit("mutation_gate: duplicate mutant IDs generated; refusing to run")
    if not mutants:
        raise SystemExit("mutation_gate: zero mutants generated; refusing to pass vacuously")
    return mutants


# ── execution ───────────────────────────────────────────────────────────────

def _make_worktree(root: Path) -> Path:
    wt = Path(tempfile.mkdtemp(prefix="mutgate-", dir=root))
    shutil.copytree(REPO / PACKAGE, wt / PACKAGE,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(REPO / "tests", wt / "tests",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for extra in ("pyproject.toml",):
        if (REPO / extra).exists():
            shutil.copy2(REPO / extra, wt / extra)
    return wt


def _env(wt: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(wt) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _probe_isolation(wt: Path) -> None:
    """Fail closed unless the worktree copy is the one imported."""
    proc = subprocess.run(
        [sys.executable, "-c", f"import {PACKAGE}, os; print(os.path.realpath({PACKAGE}.__file__))"],
        cwd=wt, env=_env(wt), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"mutation_gate: ISOLATION PROBE FAILED to import {PACKAGE} from the "
                         f"worktree copy:\n{proc.stderr.strip()}")
    out = proc.stdout.strip()
    expected = os.path.realpath(wt / PACKAGE / "__init__.py")
    if out != expected:
        raise SystemExit(
            f"mutation_gate: ISOLATION FAILED — the suite would import {out}, "
            f"not the mutated copy {expected}. Refusing to run.")


def _run_suite(wt: Path, timeout: float) -> tuple:
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", *PYTEST_ARGS],
            cwd=wt, env=_env(wt), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "timeout", time.monotonic() - t0
    return ("passed" if proc.returncode == 0 else "failed"), time.monotonic() - t0


def run_campaign(mutants, workers: int, progress: bool = True) -> dict:
    root = Path(tempfile.mkdtemp(prefix="mutgate-root-"))
    try:
        worktrees = [_make_worktree(root) for _ in range(workers)]
        for wt in worktrees:
            _probe_isolation(wt)
        status, dur = _run_suite(worktrees[0], timeout=600)
        if status != "passed":
            raise SystemExit("mutation_gate: the UNMUTATED suite does not pass; refusing to run")
        timeout = max(60.0, dur * 20)
        free = list(worktrees)
        results = {}
        import threading
        lock = threading.Lock()

        def one(m):
            with lock:
                wt = free.pop()
            try:
                target = wt / m["file"]
                original = (REPO / m["file"]).read_text()
                target.write_text(m["source"])
                try:
                    st, _ = _run_suite(wt, timeout)
                finally:
                    target.write_text(original)
            finally:
                with lock:
                    free.append(wt)
            return m["id"], ("survived" if st == "passed" else ("timeout" if st == "timeout" else "killed"))

        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(one, m) for m in mutants]
            for f in as_completed(futs):
                mid, st = f.result()
                results[mid] = st
                done += 1
                if progress and (done % 25 == 0 or done == len(mutants)):
                    print(f"  {done}/{len(mutants)} mutants run", file=sys.stderr, flush=True)
        return results
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── baseline and verdict ────────────────────────────────────────────────────

def _score(records: dict) -> tuple:
    total = len(records)
    killed = sum(1 for r in records.values() if r["status"] in ("killed", "timeout"))
    return killed, total, (killed / total if total else 0.0)


def load_baseline() -> dict:
    if not BASELINE.exists():
        raise SystemExit(f"mutation_gate: no baseline at {BASELINE}. Run with --rebaseline.")
    data = json.loads(BASELINE.read_text())
    killed, total, _ = _score(data["mutants"])
    s = data["summary"]
    if s["killed"] != killed or s["total"] != total:
        raise SystemExit(
            "mutation_gate: the baseline's stored summary disagrees with its own "
            f"records (stored {s['killed']}/{s['total']}, records {killed}/{total}). "
            "Refusing a hand-edited baseline.")
    return data


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def write_baseline(mutants, results, old: dict | None, workers: int) -> dict:
    old_reasons = (old or {}).get("survivor_reasons", {})
    records = {m["id"]: {"status": results[m["id"]], "file": m["file"], "line": m["line"],
                         "operator": m["operator"], "detail": m["detail"]} for m in mutants}
    reasons = {mid: old_reasons[mid] for mid, r in records.items()
               if r["status"] == "survived" and mid in old_reasons}
    killed, total, score = _score(records)
    data = {
        "_comment": ("Generated by tools/mutation_gate.py --rebaseline. Do not edit "
                     "mutants/summary by hand; the gate cross-checks them. Add a written "
                     "reason for every survivor under survivor_reasons."),
        "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "command": f"python tools/mutation_gate.py --rebaseline --workers {workers}",
        "git_head_at_generation": _git_head(),
        "python": sys.version.split()[0],
        "summary": {"killed": killed, "total": total, "survived": total - killed},
        "survivor_reasons": dict(sorted(reasons.items())),
        "mutants": dict(sorted(records.items())),
    }
    BASELINE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return data


def verdict(results: dict, baseline: dict) -> list:
    """Return a list of failure strings (empty = pass)."""
    failures = []
    base = baseline["mutants"]
    reasons = baseline.get("survivor_reasons", {})
    b_killed, b_total, floor = _score(base)
    cur = {mid: {"status": st} for mid, st in results.items()}
    c_killed, c_total, score = _score(cur)

    if score < floor:
        failures.append(
            f"score below the derived floor: {score:.4f} ({c_killed}/{c_total}) < "
            f"{floor:.4f} ({b_killed}/{b_total}, recomputed from the baseline records)")
    now_survive = sorted(mid for mid, st in results.items()
                         if st == "survived" and base.get(mid, {}).get("status") in ("killed", "timeout"))
    if now_survive:
        failures.append(f"{len(now_survive)} mutant(s) the baseline killed now survive:\n    "
                        + "\n    ".join(now_survive))
    vanished = sorted(mid for mid, r in base.items()
                      if r["status"] in ("killed", "timeout") and mid not in results)
    if vanished:
        failures.append(
            f"{len(vanished)} mutant(s) the baseline killed no longer exist (the code they "
            "mutated changed). Review, then re-baseline deliberately with "
            "`python tools/mutation_gate.py --rebaseline`:\n    " + "\n    ".join(vanished))
    unexplained = sorted(mid for mid, st in results.items()
                         if st == "survived" and not reasons.get(mid, "").strip())
    if unexplained:
        failures.append(f"{len(unexplained)} surviving mutant(s) have no written reason in "
                        f"{BASELINE.relative_to(REPO)} survivor_reasons:\n    "
                        + "\n    ".join(unexplained))
    return failures


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def resolve_reference(ref: str | None) -> str | None:
    """The commit to compare against: --reference, else merge-base with origin/main, else main."""
    if ref:
        out = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
        if out.returncode != 0:
            raise SystemExit(f"mutation_gate: --reference {ref!r} does not resolve to a commit")
        return out.stdout.strip()
    for candidate in ("origin/main", "main"):
        if _git("rev-parse", "--verify", f"{candidate}^{{commit}}").returncode == 0:
            mb = _git("merge-base", "HEAD", candidate)
            if mb.returncode == 0:
                return mb.stdout.strip()
    return None


def reference_baseline(commit: str | None) -> dict | None:
    if commit is None:
        return None
    out = _git("show", f"{commit}:{BASELINE_GIT_PATH}")
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    data = json.loads(OVERRIDES.read_text())
    bad = [k for k, v in data.items() if not str(v).strip()]
    if bad:
        raise SystemExit(f"mutation_gate: ratchet overrides without a written reason: {bad}")
    return data


def ratchet(current: dict, reference: dict | None, overrides: dict, ref_label: str) -> list:
    """Failures from comparing the committed baseline with the reference baseline."""
    if reference is None:
        print(f"RATCHET: no reference baseline at {ref_label} -- this is the release that "
              "introduces the gate, so there is nothing to ratchet against. SKIPPED, explicitly.")
        return []
    failures = []
    _, _, cur_floor = _score(current["mutants"])
    _, _, ref_floor = _score(reference["mutants"])
    print(f"RATCHET: reference {ref_label} floor {ref_floor:.4f}; committed floor {cur_floor:.4f}")
    if cur_floor < ref_floor and "floor_drop" not in overrides:
        failures.append(f"ratchet: the committed floor {cur_floor:.4f} is below the reference floor "
                        f"{ref_floor:.4f} ({ref_label}); list \"floor_drop\" with a reason in "
                        f"{OVERRIDES.relative_to(REPO)} if this is deliberate")
    flipped = sorted(mid for mid, r in reference["mutants"].items()
                     if r["status"] in ("killed", "timeout")
                     and current["mutants"].get(mid, {}).get("status") == "survived"
                     and mid not in overrides)
    if flipped:
        failures.append(f"ratchet: {len(flipped)} mutant(s) killed in the reference baseline survive in "
                        f"the committed one (list each in {OVERRIDES.relative_to(REPO)} with a reason "
                        "if deliberate):\n    " + "\n    ".join(flipped))
    only_ref = len(set(reference["mutants"]) - set(current["mutants"]))
    only_cur = len(set(current["mutants"]) - set(reference["mutants"]))
    print(f"RATCHET: {only_ref} mutant(s) only in the reference, {only_cur} only in the committed "
          "baseline (code changed; reported, not failed)")
    return failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebaseline", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--reference", help="git ref whose baseline the ratchet compares against")
    ap.add_argument("--require-reference", action="store_true",
                    help="fail if the reference has no baseline instead of skipping")
    ap.add_argument("--ratchet-only", action="store_true",
                    help="run only the ratchet against the reference baseline (no campaign)")
    args = ap.parse_args(argv)

    if args.ratchet_only or not args.rebaseline:
        commit = resolve_reference(args.reference)
        label = args.reference or (f"merge-base {commit[:7]}" if commit else "(no main branch)")
        ref = reference_baseline(commit)
        if ref is None and args.require_reference:
            print(f"RATCHET FAILED: no reference baseline at {label} and --require-reference given")
            return 1
        rfail = ratchet(load_baseline(), ref, load_overrides(), label)
        if rfail:
            print("\nMUTATION GATE FAILED (ratchet)")
            for f in rfail:
                print(f"  - {f}")
            return 1
        if args.ratchet_only:
            print("RATCHET PASSED")
            return 0

    mutants = generate_mutants()
    if args.list:
        for m in mutants:
            print(f"{m['id']}  (line {m['line']})")
        print(f"{len(mutants)} mutants")
        return 0

    old = json.loads(BASELINE.read_text()) if BASELINE.exists() else None
    baseline = None if args.rebaseline else load_baseline()  # fail fast, before the campaign
    print(f"mutation_gate: {len(mutants)} mutants, {args.workers} worker(s)", file=sys.stderr)
    t0 = time.monotonic()
    results = run_campaign(mutants, args.workers)
    elapsed = time.monotonic() - t0
    killed, total, score = _score({k: {"status": v} for k, v in results.items()})
    survivors = sorted(k for k, v in results.items() if v == "survived")
    print(f"mutants {total}  killed {killed}  survived {len(survivors)}  "
          f"score {score:.4f} ({score*100:.1f}%)  [{elapsed:.0f}s]")

    if args.rebaseline:
        data = write_baseline(mutants, results, old, args.workers)
        missing = [s for s in survivors if s not in data["survivor_reasons"]]
        print(f"baseline written to {BASELINE.relative_to(REPO)}")
        if missing:
            print(f"{len(missing)} survivor(s) need a written reason before the gate passes:")
            for s in missing:
                print(f"    {s}")
            return 1
        return 0

    reasons = baseline.get("survivor_reasons", {})
    for s in survivors:
        print(f"  SURVIVED {s}\n           reason: {reasons.get(s, '(none)')}")
    failures = verdict(results, baseline)
    if failures:
        print("\nMUTATION GATE FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1
    _, _, floor = _score(baseline["mutants"])
    print(f"\nMUTATION GATE PASSED  (floor {floor:.4f} derived from the baseline records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
