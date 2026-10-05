"""Tests for the client's own version data.

The client used to hardcode its version in several places: the login window
read "PlayPalace 11." as a literal, and the authorize packet carried a
separate major/minor/patch triple. Those drifted apart. ``version.py`` is now
the single source, and these tests keep it honest.
"""

from pathlib import Path

from version import (
    CLIENT_VERSION,
    CLIENT_VERSION_MAJOR,
    CLIENT_VERSION_MINOR,
    CLIENT_VERSION_PATCH,
    version_dict,
)

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pyproject_version() -> str:
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise AssertionError("no version found in pyproject.toml")


def test_the_client_reports_twelve():
    assert CLIENT_VERSION == "12.0.0"


def test_version_matches_pyproject():
    """The one place the version is also written down must agree."""
    assert CLIENT_VERSION == _pyproject_version(), (
        "version.py and pyproject.toml disagree; update both when bumping"
    )


def test_numeric_parts_match_the_string():
    assert CLIENT_VERSION_MAJOR == 12
    assert CLIENT_VERSION_MINOR == 0
    assert CLIENT_VERSION_PATCH == 0


def test_version_dict_is_what_the_authorize_packet_sends():
    assert version_dict() == {"major": 12, "minor": 0, "patch": 0}