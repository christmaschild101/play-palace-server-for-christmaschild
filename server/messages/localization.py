"""Localization system using Mozilla Fluent."""

import base64
import hashlib
import json
import logging
import marshal
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from babel.lists import format_list
from fluent_compiler.bundle import FluentBundle
from fluent_compiler.compiler import compile_messages
from fluent_compiler.resource import FtlResource

if TYPE_CHECKING:
    from fluent_compiler.compiler import CompiledFtl


LOG = logging.getLogger("playpalace.localization")


class Localization:
    """
    Localization system using Mozilla Fluent via fluent-compiler.

    Loads .ftl files from the locales directory and provides message
    rendering with variable substitution.
    """

    _bundles: dict[str, FluentBundle] = {}
    _locales_dir: Path | None = None
    _cache_dir: Path | None = None
    _cache_enabled: bool = True
    _warmup_active: bool = False
    _CACHE_VERSION = "2"
    _CACHE_DISABLE_ENV = "PLAYPALACE_DISABLE_LOCALE_CACHE"
    _CACHE_DIR_ENV = "PLAYPALACE_LOCALE_CACHE_DIR"
    _enabled_locales: set[str] | None = None  # None = all locales
    _missing_key_fallback_warnings: set[tuple[str, str]] = set()

    @classmethod
    def set_warmup_active(cls, active: bool) -> None:
        cls._warmup_active = active

    @classmethod
    def is_warmup_active(cls) -> bool:
        return cls._warmup_active

    @classmethod
    def init(cls, locales_dir: Path | str, *, enabled_locales: list[str] | None = None) -> None:
        """Initialize the localization system with a locales directory.

        Args:
            locales_dir: Path to the locales directory.
            enabled_locales: If set, only load these locales (plus ``en`` as
                fallback).  ``None`` loads all locales.
        """
        cls._locales_dir = Path(locales_dir)
        cls._bundles = {}
        cls._missing_key_fallback_warnings = set()
        disable_cache = os.environ.get(cls._CACHE_DISABLE_ENV, "").strip().lower()
        cls._cache_enabled = disable_cache not in {"1", "true", "yes", "on"}
        cls._cache_dir = None
        if enabled_locales is not None:
            cls._enabled_locales = {*enabled_locales, "en"}
        else:
            cls._enabled_locales = None

    @classmethod
    def reload(cls, *, force: bool = False) -> int:
        """Reload locale bundles from disk, dropping cached compiled artifacts.

        Clears the in-memory bundle cache (and, when ``force`` is True, the
        on-disk compiled cache) so the next :meth:`_get_bundle`/warmup rebuilds
        from source. Returns the number of locale directories reloaded.

        Safe to call while the server is running: bundles are rebuilt lazily as
        they are next requested. A following :meth:`preload_bundles` call will
        rebuild every locale synchronously.

        Args:
            force: When True, also wipe the on-disk compiled cache so every
                locale recompiles from its ``.ftl`` source.
        """
        cls._bundles = {}
        cls._missing_key_fallback_warnings = set()
        if force:
            cache_root = cls._resolve_cache_dir()
            if cache_root is not None:
                import shutil

                for entry in cache_root.iterdir():
                    if entry.is_dir():
                        shutil.rmtree(entry, ignore_errors=True)
                cls._cache_dir = None
        if cls._locales_dir is None:
            return 0
        return sum(1 for d in cls._locales_dir.iterdir() if d.is_dir())

    @classmethod
    def preload_bundles(cls) -> None:
        """Pre-load all locale bundles at startup."""
        if cls._locales_dir is None:
            print("ERROR: Localization directory is not configured.", file=sys.stderr)
            raise SystemExit(1)

        if not cls._locales_dir.exists() or not cls._locales_dir.is_dir():
            print(
                f"ERROR: Localization directory '{cls._locales_dir}' is missing or not a directory.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        found_locale = False
        for locale_dir in cls._locales_dir.iterdir():
            if not locale_dir.is_dir():
                continue
            if cls._enabled_locales is not None and locale_dir.name not in cls._enabled_locales:
                continue
            found_locale = True
            try:
                cls._get_bundle(locale_dir.name)
            except RuntimeError as exc:
                print(
                    f"ERROR: Failed to load localization bundle for '{locale_dir.name}': {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(1) from exc

        if not found_locale:
            print(
                f"ERROR: Localization directory '{cls._locales_dir}' does not contain any locale bundles.",
                file=sys.stderr,
            )
            raise SystemExit(1)

    @classmethod
    def _get_bundle(cls, locale: str) -> FluentBundle:
        """Get or create a bundle for a locale."""
        if locale in cls._bundles:
            return cls._bundles[locale]

        if cls._locales_dir is None:
            print("ERROR: Localization directory is not configured.", file=sys.stderr)
            raise SystemExit(1)

        locale_dir = cls._locales_dir / locale
        actual_locale = locale
        if not locale_dir.exists():
            # Fall back to English
            locale_dir = cls._locales_dir / "en"
            actual_locale = "en"
            if not locale_dir.exists():
                print(
                    f"ERROR: No localization files found for '{locale}' or fallback 'en'.",
                    file=sys.stderr,
                )
                raise SystemExit(1)

        payloads, fingerprint = cls._load_locale_payloads(locale_dir, actual_locale)
        bundle = cls._load_bundle_from_cache(actual_locale, fingerprint)
        if bundle is None:
            bundle = cls._compile_bundle(actual_locale, payloads, fingerprint)
        cls._bundles[locale] = bundle
        return bundle

    @classmethod
    def _load_locale_payloads(cls, locale_dir: Path, actual_locale: str) -> tuple[list[str], str]:
        """Read locale files and compute a content fingerprint."""
        ftl_files = sorted(locale_dir.glob("*.ftl"))
        if not ftl_files:
            print(
                f"ERROR: No .ftl localization files found in {locale_dir}.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        digest = hashlib.sha256()
        digest.update(cls._CACHE_VERSION.encode("utf-8"))
        digest.update(actual_locale.encode("utf-8"))
        # Compiled code objects are only valid for the exact Python and
        # fluent-compiler versions that produced them.
        digest.update(sys.version_info.major.to_bytes(4, "big", signed=False))
        digest.update(sys.version_info.minor.to_bytes(4, "big", signed=False))
        try:
            from importlib import metadata as _metadata

            digest.update(_metadata.version("fluent-compiler").encode("utf-8"))
        except Exception:  # noqa: BLE001 - best-effort version pinning
            pass

        payloads: list[str] = []
        for ftl_file in ftl_files:
            text = ftl_file.read_text(encoding="utf-8")
            payloads.append(text)
            encoded = text.encode("utf-8")
            digest.update(ftl_file.name.encode("utf-8"))
            digest.update(len(encoded).to_bytes(8, "big", signed=False))
            digest.update(hashlib.sha256(encoded).digest())

        return payloads, digest.hexdigest()

    @classmethod
    def _load_bundle_from_cache(cls, actual_locale: str, fingerprint: str) -> FluentBundle | None:
        """Load a cached bundle when available."""
        cache_root = cls._resolve_cache_dir()
        if cache_root is None:
            return None

        cache_path = cache_root / actual_locale / f"{fingerprint}.json"
        if not cache_path.exists():
            return None

        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("version") != cls._CACHE_VERSION:
                raise ValueError("Cache version mismatch")
            if payload.get("fingerprint") != fingerprint:
                raise ValueError("Cache fingerprint mismatch")
            if payload.get("locale") != actual_locale:
                raise ValueError("Cache locale mismatch")
            if not isinstance(payload.get("code"), str):
                raise ValueError("Cache code missing")
            if not isinstance(payload.get("mapping"), dict):
                raise ValueError("Cache mapping missing")
        except Exception:
            LOG.debug("Discarding corrupt locale cache for '%s'", actual_locale, exc_info=True)
            try:
                cache_path.unlink()
            except FileNotFoundError:
                pass
            return None

        try:
            return cls._rebuild_bundle_from_cache(actual_locale, payload)
        except Exception:
            LOG.debug(
                "Discarding unrebuildable locale cache for '%s'", actual_locale, exc_info=True
            )
            try:
                cache_path.unlink()
            except FileNotFoundError:
                pass
            return None

    @classmethod
    def _rebuild_bundle_from_cache(cls, actual_locale: str, payload: dict) -> FluentBundle:
        """Rebuild a compiled bundle from cached code objects (no recompilation).

        The cached ``code`` is a base64-encoded :mod:`marshal` dump of the
        generated Python module that ``compile_messages`` produces. We rebuild
        the exact module globals seed it expects — the fluent_compiler runtime
        helpers, builtins, the babel locale, and the tiny plural-form closure —
        then exec the code object and wire up the message-id -> function map.
        Any failure here is caught by the caller and falls back to a normal
        compile.
        """
        from fluent_compiler import runtime as _fc_runtime
        import babel as _babel
        import builtins as _builtins

        code_bytes = base64.b64decode(payload["code"])
        code_obj = marshal.loads(code_bytes)

        # Same seed as fluent_compiler.compiler.messages_to_module builds:
        # runtime helpers + builtins + locale + plural-form function.
        module_globals: dict = {k: getattr(_fc_runtime, k) for k in _fc_runtime.__all__}
        module_globals.update(_builtins.__dict__)
        babel_locale = _babel.Locale.parse(actual_locale.replace("-", "_"))
        module_globals["locale"] = babel_locale

        plural_main = _babel.plural.to_python(babel_locale.plural_form)

        def plural_form_for_number(number):
            try:
                return plural_main(number)
            except TypeError:
                # This function can legitimately be passed strings if we
                # incorrectly guessed a CLDR category.
                return None

        module_globals["plural_form_for_number"] = plural_form_for_number
        module_globals["__builtins__"] = _builtins.__dict__

        exec(code_obj, module_globals)

        message_functions = {
            str(message_id): module_globals[name]
            for message_id, name in payload["mapping"].items()
        }
        bundle = object.__new__(FluentBundle)
        bundle.locale = actual_locale
        bundle._compiled_messages = message_functions
        bundle._compilation_errors = []
        return bundle

    @classmethod
    def _compile_bundle(
        cls,
        actual_locale: str,
        payloads: list[str],
        fingerprint: str,
        *,
        write_cache: bool = True,
    ) -> FluentBundle:
        """Compile locale files and persist cache entry."""
        resources = [FtlResource.from_string(text) for text in payloads]
        compiled = compile_messages(actual_locale, resources)
        bundle = object.__new__(FluentBundle)
        bundle.locale = actual_locale
        bundle._compiled_messages = compiled.message_functions
        bundle._compilation_errors = compiled.errors
        if write_cache:
            cls._write_cache_entry(actual_locale, fingerprint, compiled)
        return bundle

    @classmethod
    def _resolve_cache_dir(cls) -> Path | None:
        """Resolve (or create) the cache directory."""
        if not cls._cache_enabled:
            return None
        if cls._cache_dir is not None:
            return cls._cache_dir
        base = os.environ.get(cls._CACHE_DIR_ENV)
        if base:
            path = Path(base)
        elif cls._locales_dir is not None:
            path = cls._locales_dir.parent / ".cache" / "locales"
        else:
            return None
        path.mkdir(parents=True, exist_ok=True)
        cls._cache_dir = path
        return cls._cache_dir

    @classmethod
    def _write_cache_entry(
        cls, actual_locale: str, fingerprint: str, compiled: "CompiledFtl"
    ) -> None:
        """Persist compiled bundle artifacts for reuse."""
        cache_root = cls._resolve_cache_dir()
        if cache_root is None:
            return
        entry_dir = cache_root / actual_locale
        entry_dir.mkdir(parents=True, exist_ok=True)
        module_ast = getattr(compiled, "module_ast", None)
        if module_ast is None:
            return  # Nothing to serialize; skip caching this locale.
        code_bytes = marshal.dumps(compile(module_ast, "<string>", "exec"))
        mapping = {
            str(message_id): fn.__name__
            for message_id, fn in compiled.message_functions.items()
        }
        payload = {
            "version": cls._CACHE_VERSION,
            "fingerprint": fingerprint,
            "locale": actual_locale,
            "code": base64.b64encode(code_bytes).decode("ascii"),
            "mapping": mapping,
        }
        tmp_path = entry_dir / f"{fingerprint}.tmp"
        final_path = entry_dir / f"{fingerprint}.json"
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp_path, final_path)
        for cached in entry_dir.glob("*.json"):
            if cached == final_path:
                continue
            try:
                cached.unlink()
            except OSError:
                pass
        # Clean up stale temp files left by an interrupted compile (atomic
        # replace already guarantees the .json is never corrupt, but sweeps
        # orphaned temps so they don't accumulate).
        for stale in entry_dir.glob("*.tmp"):
            if stale == tmp_path:
                continue
            try:
                stale.unlink()
            except OSError:
                pass

    # Unicode bidi isolation characters that Fluent adds around variables
    _BIDI_CHARS = "\u2068\u2069"  # FIRST STRONG ISOLATE, POP DIRECTIONAL ISOLATE

    @classmethod
    def _format_message(cls, locale: str, message_id: str, kwargs: dict[str, object]) -> str:
        """Format a message from a specific locale bundle."""
        bundle = cls._get_bundle(locale)
        result, errors = bundle.format(message_id, kwargs)
        if errors:
            LOG.warning(
                "Fluent formatting errors for '%s' [%s]: %s",
                message_id, locale, errors,
            )
        for char in cls._BIDI_CHARS:
            result = result.replace(char, "")
        return result

    @classmethod
    def get(cls, locale: str, message_id: str, **kwargs) -> str:
        """
        Get a localized message.

        Args:
            locale: The locale code (e.g., 'en', 'es').
            message_id: The message ID from the .ftl file.
            **kwargs: Variables to substitute into the message.

        Returns:
            The formatted message string.
        """
        try:
            return cls._format_message(locale, message_id, kwargs)
        except Exception:
            if locale != "en":
                try:
                    fallback = cls._format_message("en", message_id, kwargs)
                except Exception:
                    pass
                else:
                    warning_key = (locale, message_id)
                    if warning_key not in cls._missing_key_fallback_warnings:
                        cls._missing_key_fallback_warnings.add(warning_key)
                        LOG.warning(
                            "Missing localized message '%s' for locale '%s'; falling back to English.",
                            message_id, locale,
                        )
                    return fallback
            LOG.exception(
                "Failed to format message '%s' for locale '%s'",
                message_id, locale,
            )
            return f"[{message_id}]"

    @classmethod
    def format_list_and(cls, locale: str, items: list[str]) -> str:
        """
        Format a list with 'and' conjunction using Babel.

        Args:
            locale: The locale code.
            items: List of items to format.

        Returns:
            Formatted list string (e.g., "A, B, and C").
        """
        return format_list(items, style="standard", locale=locale)

    @classmethod
    def format_list_or(cls, locale: str, items: list[str]) -> str:
        """
        Format a list with 'or' conjunction using Babel.

        Args:
            locale: The locale code.
            items: List of items to format.

        Returns:
            Formatted list string (e.g., "A, B, or C").
        """
        return format_list(items, style="or", locale=locale)

    @classmethod
    def get_available_locale_codes(cls) -> list[str]:
        """Return sorted language codes from the locales directory.

        Only returns locales that are enabled in the server configuration.
        Unlike :meth:`get_available_languages`, this only scans the
        filesystem and never triggers bundle compilation, so it is safe
        to call during warmup.
        """
        if cls._locales_dir is None:
            raise RuntimeError("Localization not initialized. Call Localization.init() first.")
        return sorted(
            locale_dir.name
            for locale_dir in cls._locales_dir.iterdir()
            if locale_dir.is_dir()
            and (cls._enabled_locales is None or locale_dir.name in cls._enabled_locales)
        )

    @classmethod
    def get_available_languages(
        cls, display_language: str = "", *, fallback: str = "en"
    ) -> dict[str, str]:
        """
        Get a dictionary of available languages.

        Args:
            display_language: The locale to use for displaying language names.
                              If empty, each language name is shown in its own
                              language (e.g., "English" for en, "中文" for zh).
            fallback: The locale to use if a language name is not found
                             in the display language. Defaults to "en".

        Returns:
            Dictionary mapping language codes to language names.
        """
        if cls._locales_dir is None:
            raise RuntimeError("Localization not initialized. Call Localization.init() first.")

        result = {}

        # Get list of valid locale directories (filtered by enabled_locales)
        locales = [
            locale_dir.name
            for locale_dir in cls._locales_dir.iterdir()
            if locale_dir.is_dir()
            and (cls._enabled_locales is None or locale_dir.name in cls._enabled_locales)
        ]

        for locale_code in sorted(locales):
            message_id = f"language-{locale_code}"
            if display_language:
                # Use the display language's bundle for all names
                name = cls.get(display_language, message_id)
            else:
                # Use each locale's own bundle for its name
                name = cls.get(locale_code, message_id)

            # If translation not found, try fallback locale
            if name in (message_id, f"[{message_id}]") and fallback != display_language:
                name = cls.get(fallback, message_id)

            # If fallback is not "en" and still not found, try "en"
            if name in (message_id, f"[{message_id}]") and fallback != "en":
                name = cls.get("en", message_id)

            result[locale_code] = name

        return result


def get_message(locale: str, message_id: str, **kwargs) -> str:
    """Convenience function to get a localized message."""
    return Localization.get(locale, message_id, **kwargs)
