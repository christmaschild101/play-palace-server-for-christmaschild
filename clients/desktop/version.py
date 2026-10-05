"""The client's own version.

This is the single source of truth for the desktop client's version. It is
deliberately *not* read from the server: the connection banner reports what
this client is, so it keeps saying 12 even when connecting to an older server
that still reports its own version as 11.

``tests/test_version.py`` asserts this matches ``pyproject.toml``, which is the
only other place the version is written down, so the two cannot drift apart.
"""

CLIENT_VERSION = "12.0.0"

#: Numeric parts, sent to the server in the authorize packet.
CLIENT_VERSION_PARTS = tuple(int(part) for part in CLIENT_VERSION.split("."))
CLIENT_VERSION_MAJOR, CLIENT_VERSION_MINOR, CLIENT_VERSION_PATCH = CLIENT_VERSION_PARTS


def version_dict() -> dict:
    """The version as the authorize packet spells it."""
    return {
        "major": CLIENT_VERSION_MAJOR,
        "minor": CLIENT_VERSION_MINOR,
        "patch": CLIENT_VERSION_PATCH,
    }