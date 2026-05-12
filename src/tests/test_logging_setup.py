"""Tests for src/logging_setup.py.

Each test patches the environment, reloads config and logging_setup so that
module-level globals reflect the patched values, then asserts the expected
behaviour.  After each test the modules are reset so that the next test starts
fresh (idempotency guard included).
"""

import importlib
import io
import json
import logging

import pytest


def _reload_modules(monkeypatch, env: dict[str, str | None]):
    """Patch env, reload config + logging_setup, and reset the idempotency flag.

    Returns the freshly-imported logging_setup module so tests can call
    setup_logging() directly.
    """
    # Apply environment overrides.  Use monkeypatch so they are automatically
    # reverted after the test.
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    # Force reload of config so module-level globals pick up the new env.
    config_mod = importlib.import_module("config")
    importlib.reload(config_mod)

    # Force reload of logging_setup so it picks up the freshly-loaded config
    # and resets its _CONFIGURED guard.
    ls_mod = importlib.import_module("logging_setup")
    importlib.reload(ls_mod)

    return ls_mod


def _capture_handler(stream: io.StringIO) -> logging.StreamHandler:
    handler = logging.StreamHandler(stream)
    return handler


class TestLoggingSetup:
    """Tests for setup_logging()."""

    @pytest.fixture(autouse=True)
    def cleanup_root_handlers(self):
        """Remove any handlers added by setup_logging() after each test."""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        yield
        root.handlers[:] = original_handlers
        root.level = original_level

    # ------------------------------------------------------------------
    # 1. Default format in RUN_MODE=test is console
    # ------------------------------------------------------------------
    def test_default_format_is_console_in_test_mode(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "test",
                "LOG_FORMAT": None,  # unset so we get the default
                "LOG_LEVEL": "INFO",
            },
        )

        assert ls.LOG_FORMAT == "console"

    # ------------------------------------------------------------------
    # 2. Default format in development mode is console
    # ------------------------------------------------------------------
    def test_default_format_is_console_in_development_mode(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "development",
                "LOG_FORMAT": None,
                "LOG_LEVEL": "INFO",
            },
        )

        assert ls.LOG_FORMAT == "console"

    # ------------------------------------------------------------------
    # 3. Default format in production mode is json
    # ------------------------------------------------------------------
    def test_default_format_is_json_in_production_mode(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "production",
                "LOG_FORMAT": None,
                "LOG_LEVEL": "INFO",
            },
        )

        assert ls.LOG_FORMAT == "json"

    # ------------------------------------------------------------------
    # 4. Explicit LOG_FORMAT=json overrides the default and produces
    #    parseable JSON even in test/dev mode
    # ------------------------------------------------------------------
    def test_explicit_json_format_produces_parseable_json(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "test",
                "LOG_FORMAT": "json",
                "LOG_LEVEL": "DEBUG",
            },
        )

        assert ls.LOG_FORMAT == "json"

        ls.setup_logging()

        # Attach a capturing handler *after* setup_logging so we can inspect
        # output without depending on stderr.
        stream = io.StringIO()
        capture = logging.StreamHandler(stream)
        # Use the same formatter that setup_logging installed on the root.
        root = logging.getLogger()
        capture.setFormatter(root.handlers[-1].formatter)

        test_logger = logging.getLogger("test.json.output")
        test_logger.addHandler(capture)
        test_logger.setLevel(logging.DEBUG)
        try:
            test_logger.info("hello json", extra={"foo": "bar"})
        finally:
            test_logger.removeHandler(capture)

        line = stream.getvalue().strip()
        assert line, "No output captured"

        parsed = json.loads(line)
        # Required keys from the spec
        assert "message" in parsed or "msg" in parsed
        assert "level" in parsed or "levelname" in parsed

    # ------------------------------------------------------------------
    # 5. setup_logging() is idempotent — calling twice doesn't duplicate
    #    handlers on the root logger
    # ------------------------------------------------------------------
    def test_idempotent_no_duplicate_handlers(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "development",
                "LOG_FORMAT": "console",
                "LOG_LEVEL": "INFO",
            },
        )

        root = logging.getLogger()

        ls.setup_logging()
        after_first_call = len(root.handlers)

        ls.setup_logging()
        after_second_call = len(root.handlers)

        # dictConfig replaces all handlers; after the first call there should
        # be exactly one handler ("console").
        assert after_first_call == 1
        # Second call must not add another handler.
        assert after_second_call == after_first_call

    # ------------------------------------------------------------------
    # 6. LOG_LEVEL env override is respected
    # ------------------------------------------------------------------
    def test_log_level_env_override_is_respected(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "development",
                "LOG_FORMAT": "console",
                "LOG_LEVEL": "WARNING",
            },
        )

        assert ls.LOG_LEVEL == "WARNING"

        ls.setup_logging()

        root = logging.getLogger()
        assert root.level == logging.WARNING

    # ------------------------------------------------------------------
    # 7. Explicit LOG_FORMAT=console overrides production default
    # ------------------------------------------------------------------
    def test_explicit_console_format_overrides_production_default(self, monkeypatch):
        ls = _reload_modules(
            monkeypatch,
            {
                "RUN_MODE": "production",
                "LOG_FORMAT": "console",
                "LOG_LEVEL": "INFO",
            },
        )

        assert ls.LOG_FORMAT == "console"
