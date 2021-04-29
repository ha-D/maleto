import fnmatch
import logging

from telegram import ext

BASE_FORMAT = "%(asctime)s - %(levelname)5s - %(message)s"


def init_logging(log_file, log_level):
    log_args = {"filename": log_file, "filemode": "a"} if log_file else {}
    log_level = logging.getLevelName(log_level.upper())

    lib_loggers = (
        ("telegram.*", logging.INFO),
        ("apscheduler.*", logging.INFO),
        ("PYMONGOIM*", logging.WARNING),
    )

    for logger_name in logging.root.manager.loggerDict:
        for match_with, level in lib_loggers:
            if fnmatch.fnmatch(logger_name, match_with):
                logging.getLogger(logger_name).setLevel(max(level, log_level))
    logging.getLogger("apscheduler.scheduler").setLevel(max(logging.INFO, log_level))

    handler = logging.StreamHandler()
    handler.setFormatter(Formatter(BASE_FORMAT))
    logging.basicConfig(
        level=log_level,
        handlers=[handler],
        **log_args,
    )


class Formatter(logging.Formatter):
    def __init__(self, fmt):
        super().__init__(fmt)

        from sentry_sdk.integrations.logging import COMMON_RECORD_ATTRS

        self.commons = set(COMMON_RECORD_ATTRS)
        self.commons.add("asctime")

    def formatMessage(self, record):
        msg = super().formatMessage(record)
        extras = " ".join(
            [
                f"{k}:{record.__dict__[k]}"
                for k in record.__dict__
                if k not in self.commons
            ]
        )
        if not extras:
            return msg
        return f"{msg} | {extras}"
