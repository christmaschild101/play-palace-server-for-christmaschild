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


def test_localization_cache_rebuild_formats_identically(tmp_path, monkeypatch):
    """A bundle rebuilt from the compiled-code cache formats messages the same
    as a freshly compiled bundle, including variable substitution."""
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("PLAYPALACE_DISABLE_LOCALE_CACHE", raising=False)

    locale_dir = locales_dir / "en"
    locale_dir.mkdir(parents=True, exist_ok=True)
    (locale_dir / "main.ftl").write_text(
        "hello = Hello { $name }!\ncount = { $n ->\n    [one] One item\n   *[other] { $n } items\n}\n",
        encoding="utf-8",
    )

    # First init: fresh compile.
    Localization.init(locales_dir)
    assert Localization.get("en", "hello", name="Zed") == "Hello Zed!"
    assert Localization.get("en", "count", n=3) == "3 items"
    assert len(list((cache_dir / "en").glob("*.json"))) == 1

    # Second init: bundle must be rebuilt from the compiled-code cache.
    Localization.init(locales_dir)
    assert Localization.get("en", "hello", name="Zed") == "Hello Zed!"
    assert Localization.get("en", "count", n=1) == "One item"


def test_localization_cache_falls_back_on_corrupt_entry(tmp_path, monkeypatch):
    """A corrupt cache entry is discarded and the locale recompiles."""
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("PLAYPALACE_DISABLE_LOCALE_CACHE", raising=False)

    _write_locale(locales_dir, "Hi")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"
    cache_file = next((cache_dir / "en").glob("*.json"))

    cache_file.write_text("{not json at all", encoding="utf-8")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"
    # Rebuilt and a valid single cache entry remains.
    assert len(list((cache_dir / "en").glob("*.json"))) == 1


def test_localization_cache_falls_back_on_corrupt_code(tmp_path, monkeypatch):
    """A JSON-valid cache with garbage code bytes is discarded and recompiled."""
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("PLAYPALACE_DISABLE_LOCALE_CACHE", raising=False)

    _write_locale(locales_dir, "Hi")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"
    cache_file = next((cache_dir / "en").glob("*.json"))

    import json as _json

    payload = _json.loads(cache_file.read_text(encoding="utf-8"))
    payload["code"] = "bm90LWNvZGU="  # base64 of "not-code" -> marshal.loads fails
    cache_file.write_text(_json.dumps(payload), encoding="utf-8")

    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"
    assert len(list((cache_dir / "en").glob("*.json"))) == 1


def test_localization_cache_fingerprint_tracks_python_version(tmp_path, monkeypatch):
    """Changing the Python minor version invalidates the cache fingerprint."""
    locales_dir = tmp_path / "locales"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("PLAYPALACE_DISABLE_LOCALE_CACHE", raising=False)

    from types import SimpleNamespace

    import server.messages.localization as localization_module

    _write_locale(locales_dir, "Hi")
    Localization.init(locales_dir)
    assert Localization.get("en", "hello") == "Hi"  # triggers compile + cache write
    cache_file = next((cache_dir / "en").glob("*.json"))
    first_name = cache_file.name

    # Fake a different Python minor version and re-init: the fingerprint must
    # differ so the stale cache is ignored and a fresh one is written.
    fake_version = SimpleNamespace(major=3, minor=999)
    monkeypatch.setattr(localization_module.sys, "version_info", fake_version)
    _write_locale(locales_dir, "Hi")  # same content -> content digest identical
    Localization.init(locales_dir)

    assert Localization.get("en", "hello") == "Hi"
    cache_files = list((cache_dir / "en").glob("*.json"))
    assert len(cache_files) == 1
    assert cache_files[0].name != first_name


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


def test_reload_clears_bundles_and_counts_locales(tmp_path):
    from server.messages.localization import Localization

    (tmp_path / "en").mkdir()
    (tmp_path / "pt").mkdir()
    (tmp_path / "en" / "main.ftl").write_text("k = v\n", encoding="utf-8")
    (tmp_path / "pt" / "main.ftl").write_text("k = v\n", encoding="utf-8")

    Localization.init(tmp_path)
    Localization._bundles["en"] = object()  # simula bundle carregado

    count = Localization.reload()
    assert count == 2
    assert "en" not in Localization._bundles


def test_reload_force_wipes_disk_cache(tmp_path, monkeypatch):
    import json

    from server.messages.localization import Localization

    (tmp_path / "en").mkdir()
    (tmp_path / "en" / "main.ftl").write_text("k = v\n", encoding="utf-8")
    cache_dir = tmp_path / "cache" / "en"
    cache_dir.mkdir(parents=True)
    (cache_dir / "abc.json").write_text(json.dumps({"x": 1}), encoding="utf-8")

    monkeypatch.setenv("PLAYPALACE_LOCALE_CACHE_DIR", str(tmp_path / "cache"))
    Localization.init(tmp_path)
    Localization.reload(force=True)

    assert not (tmp_path / "cache" / "en" / "abc.json").exists()
