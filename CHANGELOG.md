# Changelog

All notable changes to nmtc-calc are documented here.
Prior release history predates this file.

## [0.2.1] — 2026-06-23

### Changed
- **`__version__` is now derived from installed package metadata** via
  `importlib.metadata.version("nmtc-calc")` instead of a hardcoded string.
  This fixes a drift where the shipped wheel reported `__version__ == "0.1.0"`
  while the distribution had been bumped to `0.2.0` — `pyproject.toml` is now
  the single authoritative source of the version.

### Added
- **CI / release infrastructure** — `ci.yml` (test matrix on Python 3.9–3.12,
  all actions SHA-pinned) and a tag-triggered `release.yml` that verifies the
  tag matches `pyproject.toml`, builds the wheel, tests the installed wheel in a
  fresh venv, and publishes to PyPI via an OIDC Trusted Publisher (no API token).

No behavioral or API change — this is a hygiene-only release.
