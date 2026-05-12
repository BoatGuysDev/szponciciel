"""Central logging configuration for szponciciel.

Call ``setup_logging()`` once at every application entry point (CLI scripts,
alembic migrations, etc.).  Library code — nodes, models, providers — should
only ever call ``logging.getLogger(__name__)``; they must *not* call this
function so that the root logger configuration stays in one place.

Format selection:
  - Explicit ``LOG_FORMAT`` env var ("json" | "console") takes precedence.
  - When unset, ``RUN_MODE=production`` defaults to JSON; everything else
    (development, test, …) defaults to console.

The function is idempotent: calling it more than once is safe and has no
effect after the first call.
"""

import logging
import logging.config

from config import LOG_FORMAT, LOG_LEVEL

_CONFIGURED = False

_CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def setup_logging() -> None:
    """Configure the root logger once.

    Subsequent calls are no-ops so that importing from multiple entry points
    (e.g. a test conftest *and* the module under test) is harmless.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if LOG_FORMAT == "json":
        # By default python-json-logger omits several stdlib LogRecord fields
        # (they're in RESERVED_ATTRS).  We want levelname and name in the
        # output so we can rename them; remove them from the exclusion list.
        from pythonjsonlogger import core as _pjl_core  # noqa: PLC0415

        _reserved = [
            a for a in _pjl_core.RESERVED_ATTRS if a not in ("levelname", "name")
        ]

        formatters: dict = {
            "default": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                # Expose levelname/name so rename_fields can act on them.
                "reserved_attrs": _reserved,
                # Rename to the field names described in the spec.
                "rename_fields": {
                    "levelname": "level",
                    "name": "logger",
                },
                # timestamp=True causes python-json-logger to add an ISO-8601
                # "timestamp" field automatically.
                "timestamp": True,
            }
        }
    else:
        formatters = {
            "default": {
                "format": _CONSOLE_FORMAT,
                "datefmt": _DATE_FORMAT,
            }
        }

    logging.config.dictConfig(
        {
            "version": 1,
            # False means existing loggers created before this call (e.g. from
            # early imports) are *updated* rather than silently discarded.
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
            },
        }
    )

    _CONFIGURED = True
