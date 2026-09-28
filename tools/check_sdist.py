#!/usr/bin/env python3
"""Gate: the source distribution is complete and its own test suite passes.

The published 0.2.1 sdist shipped without tests/conftest.py, so 52 of its 53
tests errored with "fixture 'sample_deal' not found" (methodology audit §3.5).
This gate builds (or takes) an sdist, installs it into a fresh venv, and runs
THE SUITE THAT SHIPPED INSIDE THE TARBALL against the installed package.

It fails when any of these holds:
  1. a required file is missing from the tarball;
  2. a test module in the checkout is missing from the tarball (nested-aware);
  3. the installed package does not resolve out of site-packages during the run;
  4. any shipped test fails or errors;
  5. the set of test IDs the sdist ran differs from the set collected from the
     CHECKOUT (the derived minimum: the count comes from outside the thing it
     guards, so a truncated tarball cannot lower its own bar);
  6. fewer than --min-tests tests passed (an optional extra floor; it can only
     raise the bar, and it fails if set above the derived count).

Without --sdist the tarball is built from `git archive HEAD`, never from the
working tree: a stale gitignored *.egg-info/SOURCES.txt lists conftest.py and
produces a correct-looking sdist locally while CI ships a broken one.

Usage
    python tools/check_sdist.py                      # build from HEAD, check it
    python tools/check_sdist.py --sdist dist/X.tar.gz
    python tools/check_sdist.py --min-tests 300
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = "nmtccalc"
REQUIRED = ("tests/conftest.py", "LICENSE", "README.md", "pyproject.toml", "CHANGELOG.md")

# Run inside the venv from a neutral directory, so neither the unpacked source
# nor the repo is on sys.path. The plugin records where the package came from.
RUNNER = r'''
import sys, pytest
ORIGIN = {}
class Probe:
    def pytest_sessionfinish(self, session):
        mod = sys.modules.get("%(pkg)s")
        ORIGIN["file"] = getattr(mod, "__file__", None)
args = sys.argv[1:]
rc = pytest.main(args, plugins=[Probe()])
f = ORIGIN.get("file") or ""
print("CHECK_SDIST_ORIGIN=" + f)
if "site-packages" not in f:
    print("CHECK_SDIST: package did not resolve out of site-packages", file=sys.stderr)
    sys.exit(97)
sys.exit(int(rc))
''' % {"pkg": PACKAGE}


class GateError(SystemExit):
    pass


def fail(msg: str):
    raise GateError(f"check_sdist: FAIL — {msg}")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


def build_from_head(out: Path) -> Path:
    src = out / "src"
    src.mkdir()
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=REPO,
                             check=True, capture_output=True).stdout
    with tarfile.open(fileobj=__import__("io").BytesIO(archive)) as t:
        t.extractall(src)
    if any(src.glob("*.egg-info")):
        fail("git archive produced an egg-info directory; refusing a seeded build")
    run([sys.executable, "-m", "build", "--sdist", "-o", str(out / "dist"), str(src)])
    tarballs = list((out / "dist").glob("*.tar.gz"))
    if len(tarballs) != 1:
        fail(f"expected one sdist, built {len(tarballs)}")
    return tarballs[0]


def tarball_members(sdist: Path) -> set:
    with tarfile.open(sdist) as t:
        # strip the leading "<name>-<version>/" component
        return {n.split("/", 1)[1] for n in t.getnames() if "/" in n}


def checkout_test_modules() -> set:
    return {p.relative_to(REPO).as_posix() for p in (REPO / "tests").rglob("test_*.py")}


def junit_ids(xml_path: Path) -> tuple:
    root = ET.parse(xml_path).getroot()
    suites = root.iter("testsuite")
    passed, failed, skipped, ids = 0, 0, 0, set()
    for suite in suites:
        for case in suite.iter("testcase"):
            ids.add(f"{case.get('classname')}::{case.get('name')}")
            if case.find("failure") is not None or case.find("error") is not None:
                failed += 1
            elif case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1
    return passed, failed, skipped, ids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sdist", help="path to an existing sdist (default: build from git HEAD)")
    ap.add_argument("--min-tests", type=int, default=None,
                    help="extra floor on passed tests; may only raise the derived bar")
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="check-sdist-") as tmp:
        tmp = Path(tmp)
        sdist = Path(args.sdist).resolve() if args.sdist else build_from_head(tmp)
        print(f"sdist: {sdist.name}")

        members = tarball_members(sdist)
        missing = [f for f in REQUIRED if f not in members]
        if missing:
            fail(f"required file(s) missing from the tarball: {missing}")
        repo_mods = checkout_test_modules()
        sdist_mods = {m for m in members if m.startswith("tests/") and Path(m).name.startswith("test_")
                      and m.endswith(".py")}
        if not sdist_mods:
            fail("the tarball ships no test modules")
        if repo_mods - sdist_mods:
            fail(f"test modules in the checkout missing from the tarball: {sorted(repo_mods - sdist_mods)}")
        print(f"required files present; test modules: checkout {len(repo_mods)}, sdist {len(sdist_mods)}")

        unpack = tmp / "unpacked"
        with tarfile.open(sdist) as t:
            t.extractall(unpack)
        (root,) = [p for p in unpack.iterdir() if p.is_dir()]

        venv = tmp / "venv"
        run([sys.executable, "-m", "venv", str(venv)])
        vpy = venv / ("Scripts" if os.name == "nt" else "bin") / "python"
        run([str(vpy), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([str(vpy), "-m", "pip", "install", "-q", str(sdist), "pytest>=7"])

        neutral = tmp / "neutral"
        neutral.mkdir()
        runner = neutral / "run_shipped_suite.py"
        runner.write_text(RUNNER)

        # Derived minimum: collect the CHECKOUT's suite against the installed package.
        co = subprocess.run([str(vpy), str(runner), str(REPO / "tests"), "--collect-only", "-q",
                             "-p", "no:cacheprovider", "--import-mode=importlib",
                             f"--rootdir={REPO}"],
                            cwd=neutral, capture_output=True, text=True)
        checkout_ids = set()
        for line in co.stdout.splitlines():
            if "::" in line:
                checkout_ids.add(line.strip().split("tests/", 1)[-1])
        if not checkout_ids:
            fail(f"collected zero tests from the checkout:\n{co.stdout}\n{co.stderr}")

        xml = tmp / "sdist.xml"
        proc = subprocess.run([str(vpy), str(runner), str(root / "tests"), "-q", "-rs",
                               "-p", "no:cacheprovider", "--import-mode=importlib",
                               f"--rootdir={root}", f"--junitxml={xml}"],
                              cwd=neutral, capture_output=True, text=True)
        tail = "\n".join(proc.stdout.strip().splitlines()[-6:])
        print(tail)
        if proc.returncode == 97:
            fail("the shipped suite did not import the package from site-packages")
        passed, failed, skipped, _ = junit_ids(xml)
        sdist_co = subprocess.run([str(vpy), str(runner), str(root / "tests"), "--collect-only", "-q",
                                   "-p", "no:cacheprovider", "--import-mode=importlib",
                                   f"--rootdir={root}"],
                                  cwd=neutral, capture_output=True, text=True)
        sdist_ids = {line.strip().split("tests/", 1)[-1] for line in sdist_co.stdout.splitlines() if "::" in line}

        print(f"derived minimum (collected from the checkout): {len(checkout_ids)}")
        print(f"sdist ran: {passed} passed, {skipped} skipped, {failed} failed/errored")
        if proc.returncode != 0 or failed:
            fail(f"the shipped suite did not pass (exit {proc.returncode}, {failed} failed/errored)")
        if sdist_ids != checkout_ids:
            fail(f"the sdist's test set differs from the checkout's: "
                 f"missing {sorted(checkout_ids - sdist_ids)[:10]}, extra {sorted(sdist_ids - checkout_ids)[:10]}")
        if args.min_tests is not None:
            if args.min_tests > len(checkout_ids):
                fail(f"--min-tests {args.min_tests} exceeds the {len(checkout_ids)} tests the checkout has")
            if passed < args.min_tests:
                fail(f"{passed} passed < --min-tests {args.min_tests}")
        print(f"check_sdist: PASS — {passed} passed, {skipped} skipped from the shipped suite; "
              f"test set identical to the checkout ({len(checkout_ids)})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GateError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
