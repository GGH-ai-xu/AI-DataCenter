from __future__ import annotations

import logging


DEFAULT_LOG_LEVEL = logging.INFO
NOISY_LOGGERS = ("asyncssh",)


def configure_application_logging() -> None:
    logging.basicConfig(level=DEFAULT_LOG_LEVEL)
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
