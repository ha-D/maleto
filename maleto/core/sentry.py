import logging
from collections import defaultdict

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger

logger = logging.getLogger(__name__)
sentry_enabled = False
seen_events = defaultdict(lambda: 0)
duplicate_event_limit = 100


def init_sentry(dsn, version, ignore_loggers):
    global sentry_enabled
    if dsn:
        logger.debug("Initializing sentry")
        sentry_enabled = True

        sentry_logging = LoggingIntegration(
            level=logging.INFO, event_level=logging.ERROR
        )
        for name in ignore_loggers:
            ignore_logger(name)
        sentry_sdk.init(
            dsn,
            traces_sample_rate=0.5,
            before_send=filter_event,
            integrations=[sentry_logging],
            release=version,
        )


def set_user(user):
    sentry_sdk.set_user({"id": user.id, "username": user.username})


def if_sentry_enabled(f):
    def inner(*args, **kwargs):
        global sentry_enabled
        if sentry_enabled:
            return f(*args, **kwargs)

    return inner


@if_sentry_enabled
def on_error(update, context):
    sentry_sdk.capture_exception(context.error)


def filter_event(event, hint):
    try:
        e = event["exception"]["values"][0]
        k = f"{e['type']}#{e['value']}".__hash__()
        seen_events[k] += 1
        if seen_events[k] > duplicate_event_limit:
            return None
    except (KeyError, IndexError):
        pass
    return event


def transaction(f):
    name = f"{f.__module__}:{f.__qualname__}"

    def inner(*args, **kwargs):
        global sentry_enabled
        if not sentry_enabled:
            return f(*args, **kwargs)
        with sentry_sdk.start_transaction(op="task", name=name):
            return f(*args, **kwargs)

    return inner


def span(f):
    name = f"{f.__module__}:{f.__qualname__}"

    def inner(*args, **kwargs):
        global sentry_enabled
        if not sentry_enabled:
            return f(*args, **kwargs)
        with sentry_sdk.start_span(op=name, description=""):
            return f(*args, **kwargs)

    return inner


@if_sentry_enabled
def set_span_tag(key, val):
    span = sentry_sdk.Hub.current.scope.span
    if span == None:
        logger.warning("Attempting to set tag on non-existing sentry span")
        return
    span.set_tag(key, val)


@if_sentry_enabled
def set_span_data(key, val):
    span = sentry_sdk.Hub.current.scope.span
    if span == None:
        logger.warning("Attempting to set data on non-existing sentry span")
        return
    span.set_data(key, val)


@if_sentry_enabled
def set_span_status(val):
    span = sentry_sdk.Hub.current.scope.span
    if span == None:
        logger.warning("Attempting to set status on non-existing sentry span")
        return
    span.set_status(val)
