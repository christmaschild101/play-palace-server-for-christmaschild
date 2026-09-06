"""
Regression tests for per-game localization keys.

Every registered game must define its ``game-name-{type}`` key (and its
``category-*`` key) in the English locale files. Missing keys fall back to
English at runtime; when the key is absent there too, users see the literal
``[game-name-motostrike]``-style string (see Mile by Mile / Moto Strike).

These tests discover games via AST so they run without framework deps.
"""

import ast
from pathlib import Path

import pytest

GAMES_DIR = Path(__file__).parent.parent / "games"
LOCALES_EN = Path(__file__).parent.parent / "locales" / "en"


def _module_tree(game_dir: Path) -> ast.Module | None:
    """Parse a game's game.py, returning None when absent."""
    src = game_dir / "game.py"
    if not src.exists():
        return None
    return ast.parse(src.read_text(encoding="utf-8"))


def _static_return_of_method(tree: ast.Module, method_name: str) -> str | None:
    """Return the constant string a zero-arg method returns, if discoverable."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != method_name:
            continue
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                value = stmt.value.value
                if isinstance(value, str):
                    return value
    return None


def _registered_games() -> dict[str, dict[str, str | None]]:
    """Map game_type -> {"category": key, "dir": games/<dir>} via AST."""
    games: dict[str, dict[str, str | None]] = {}
    for game_dir in sorted(GAMES_DIR.iterdir()):
        if not game_dir.is_dir() or game_dir.name.startswith("_"):
            continue
        tree = _module_tree(game_dir)
        if tree is None:
            continue
        game_type = _static_return_of_method(tree, "get_type")
        if not game_type:
            continue
        games[game_type] = {
            "category": _static_return_of_method(tree, "get_category"),
            "dir": game_dir.name,
        }
    return games


def _en_keys() -> set[str]:
    keys: set[str] = set()
    for ftl in LOCALES_EN.glob("*.ftl"):
        for line in ftl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and (" " in line or "=" in line):
                key = line.split("=", 1)[0].strip() if "=" in line else line.split(" ", 1)[0]
                keys.add(key)
    return keys


def test_games_discovered() -> None:
    """Sanity: the AST scan actually finds the well-known games."""
    games = _registered_games()
    assert "milebymile" in games
    assert "monopoly" in games
    assert "motostrike" in games
    assert len(games) >= 30


def test_every_game_has_name_key() -> None:
    """Each game must define game-name-{type} in the English locale."""
    keys = _en_keys()
    missing = [
        f"game-name-{gtype} (games/{info['dir']})"
        for gtype, info in _registered_games().items()
        if f"game-name-{gtype}" not in keys
    ]
    assert not missing, "Missing game name keys in locales/en:\n  " + "\n  ".join(missing)


def test_every_game_has_category_key() -> None:
    """Each game's get_category() key must exist in the English locale."""
    keys = _en_keys()
    missing = []
    for gtype, info in _registered_games().items():
        category = info["category"]
        if category and category not in keys:
            missing.append(f"{category} (games/{info['dir']}, game {gtype})")
    assert not missing, "Missing category keys in locales/en:\n  " + "\n  ".join(missing)


def test_all_locale_dirs_have_game_files() -> None:
    """Every non-English locale dir must carry the same game .ftl files."""
    locales_dir = LOCALES_EN.parent
    en_files = {p.name for p in LOCALES_EN.glob("*.ftl")}
    for locale_dir in locales_dir.iterdir():
        if not locale_dir.is_dir() or locale_dir.name == "en":
            continue
        files = {p.name for p in locale_dir.glob("*.ftl")}
        missing = en_files - files
        assert not missing, f"Locale '{locale_dir.name}' missing files: {sorted(missing)}"


def test_motostrike_name_key_value() -> None:
    """The original bug: Moto Strike must render its TableEx name."""
    ftl = LOCALES_EN / "motostrike.ftl"
    text = ftl.read_text(encoding="utf-8")
    assert "game-name-motostrike = Moto Strike" in text
