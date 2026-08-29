import asyncio
from pathlib import Path

import pytest

import server.core.server as core_server
from server.core.server import Server
from server.messages.localization import Localization


def _write_locale(locale_root: Path, content: str) -> None:
    locale_dir = locale_root / "en"
    locale_dir.mkdir(parents=True, exist_ok=True)
    (locale_dir / "main.ftl").write_text(
        "hello = " + content + "\n",
        encoding="utf-8",
    )


def test_localization_cache_refreshes_on_file_change(tmp_path, monkeypatch):
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("PLAYPALACE_DISABLE_LOCALE_CACHE", raising=False)

    _write_locale(locales_dir, "Hi")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"
    cache_files = list((cache_dir / "en").glob("*.json"))
    assert len(cache_files) == 1
    first_cache = cache_files[0].name

    _write_locale(locales_dir, "Hello again")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hello again"
    cache_files = list((cache_dir / "en").glob("*.json"))
    assert len(cache_files) == 1
    assert cache_files[0].name != first_cache


def test_localization_cache_preserves_stale_tmp_on_interrupt(tmp_path, monkeypatch):
    """A compile interrupted before atomic replace leaves an old *.tmp file;
    a subsequent write sweeps it while never serving a corrupt .json."""
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("PLAYPALACE_DISABLE_LOCALE_CACHE", raising=False)

    _write_locale(locales_dir, "Hi")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"
    en_dir = cache_dir / "en"
    json_files = list(en_dir.glob("*.json"))
    assert len(json_files) == 1

    # Simulate an earlier compile that was killed mid-write: orphan a .tmp file.
    orphan = en_dir / "orphaned.tmp"
    orphan.write_text("partial garbage", encoding="utf-8")
    (en_dir / "corrupt.tmp").write_text("more garbage", encoding="utf-8")

    # A fresh compile (new content -> new fingerprint) writes a cache entry and
    # sweeps the stale temp files, while still serving only a valid .json.
    _write_locale(locales_dir, "Hello again")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hello again"
    assert list(en_dir.glob("*.tmp")) == []
    assert len(list(en_dir.glob("*.json"))) == 1


def test_localization_cache_can_be_disabled(tmp_path, monkeypatch):
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("PLAYPALACE_DISABLE_LOCALE_CACHE", "true")

    _write_locale(locales_dir, "Hi")
    Localization.init(locales_dir)
    Localization.get("en", "hello")

    assert not cache_dir.exists()


def test_localization_missing_key_falls_back_to_english(tmp_path):
    locales_dir = tmp_path / "locales"
    (locales_dir / "en").mkdir(parents=True, exist_ok=True)
    (locales_dir / "es").mkdir(parents=True, exist_ok=True)
    (locales_dir / "en" / "main.ftl").write_text("hello = Hello\n", encoding="utf-8")
    (locales_dir / "es" / "main.ftl").write_text("goodbye = Adios\n", encoding="utf-8")

    Localization.init(locales_dir)

    assert Localization.get("es", "hello") == "Hello"


@pytest.mark.asyncio
async def test_localization_background_warmup_logs(monkeypatch, capsys):
    calls: list[str] = []

    def fake_preload():
        calls.append("preload")

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(core_server.Localization, "preload_bundles", fake_preload)
    monkeypatch.setattr(core_server.asyncio, "to_thread", immediate_to_thread)

    server = Server(host="::1", port=9002, preload_locales=False)
    server._start_localization_warmup()
    assert server._localization_warmup_task is not None
    await asyncio.wait_for(server._localization_warmup_task, timeout=1)

    captured = capsys.readouterr()
    assert "Localization bundles compiling in background" in captured.out
    assert "Localization bundles compiled." in captured.out
    assert calls == ["preload"]


@pytest.mark.asyncio
async def test_localization_preload_flag_blocks(monkeypatch):
    calls: list[str] = []

    def fake_preload():
        calls.append("preload")

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(core_server.Localization, "preload_bundles", fake_preload)
    monkeypatch.setattr(core_server.asyncio, "to_thread", immediate_to_thread)

    blocking_server = Server(host="::1", port=9003, preload_locales=True)
    await blocking_server._preload_locales_if_requested()
    assert calls == ["preload"]

    nonblocking_server = Server(host="::1", port=9004, preload_locales=False)
    await nonblocking_server._preload_locales_if_requested()
    assert calls == ["preload"]
