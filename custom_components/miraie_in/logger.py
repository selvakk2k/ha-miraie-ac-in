"""Custom logger for Miraie."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .const import PACKAGE_NAME

LOGGER: logging.Logger = logging.getLogger(PACKAGE_NAME)

_FILE_HANDLER: RotatingFileHandler | None = None


def _get_log_path(config_dir: str) -> Path:
    return Path(config_dir) / "custom_components" / "miraie_in" / "miraie.log"


def enable_file_logger(config_dir: str) -> None:
    """Attach a rotating file handler to the integration logger.

    Idempotent — does nothing if the handler is already attached.
    """
    global _FILE_HANDLER
    if _FILE_HANDLER is not None:
        return

    log_path = _get_log_path(config_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _FILE_HANDLER = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3  # 5 MB × 3 rotations
    )
    _FILE_HANDLER.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    LOGGER.addHandler(_FILE_HANDLER)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.info("Diagnostics file logging enabled: %s", log_path)


def disable_file_logger() -> None:
    """Remove and close the file handler. Idempotent."""
    global _FILE_HANDLER
    if _FILE_HANDLER is None:
        return

    LOGGER.info("Diagnostics file logging disabled.")
    LOGGER.removeHandler(_FILE_HANDLER)
    _FILE_HANDLER.close()
    _FILE_HANDLER = None


def is_file_logging_enabled() -> bool:
    """Return whether the file handler is currently active."""
    return _FILE_HANDLER is not None